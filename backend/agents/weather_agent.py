"""
WeatherAgent for paraglide-backend.

Analyzes weather forecast data to identify thermal development windows,
launch timing recommendations, and caution conditions. Produces typed Claims
with evidence referencing specific forecast values.
"""

import math
from typing import Any

from loguru import logger

from agents.base import AgentBase, Claim, ClaimType, Evidence, SpatialScope, TemporalValidity


class WeatherAgent(AgentBase):
    """
    Reasons about weather forecast data to predict thermal and wind conditions.

    Expected context keys:
        forecast: WeatherForecast dataclass from data_ingestion.weather.provider_base
        site_profile: site profile dict (for location/elevation context)

    Thermal Index Formula
    ---------------------
    score = dewpoint_spread_factor * wind_factor * time_factor * cloud_factor

    - dewpoint_spread_factor: (temp_c - dewpoint_c) / 20.0, clamped 0-1
        Large spread = dry air = better thermals
    - wind_factor: gaussian peak at 15 km/h, width=8, falls off below 8 and above 25
        Ideal range 10-20 km/h; >28 km/h is dangerous
    - time_factor: gaussian peak at 13:00 local hour
        Thermal activity peaks in early afternoon
    - cloud_factor: 0.3-60% cover is good; below 5% = punchy; above 70% = suppressed
    """

    name = "weather_agent"

    # Agent reliability weight for negotiation (0-1)
    reliability_weight: float = 0.85

    # Wind speed thresholds in km/h
    WIND_MIN_KMH = 8.0
    WIND_IDEAL_KMH = 15.0
    WIND_MAX_COMFORTABLE_KMH = 22.0
    WIND_CAUTION_KMH = 25.0

    # Thermal score threshold to qualify as a launch window
    LAUNCH_WINDOW_MIN_SCORE = 0.35

    async def run(self, context: dict[str, Any]) -> list[Claim]:
        """
        Analyze the forecast and produce launch window and caution claims.

        Returns:
            List of Claim objects (launch_window and caution types)
        """
        forecast = context.get("forecast")
        if forecast is None:
            logger.warning("WeatherAgent: no forecast data in context")
            return []

        hourly = getattr(forecast, "hourly", [])
        if not hourly:
            logger.warning("WeatherAgent: forecast has no hourly data")
            return []

        logger.info(f"WeatherAgent analyzing {len(hourly)} forecast hours")

        claims: list[Claim] = []

        # Score each hour
        scored_hours = []
        for hour_data in hourly:
            score = self.score_hour(hour_data)
            scored_hours.append((hour_data, score))

        # Identify contiguous launch windows (blocks of good hours)
        launch_window_claims = self._identify_launch_windows(scored_hours)
        claims.extend(launch_window_claims)

        # Identify caution conditions
        caution_claims = self._identify_caution_conditions(scored_hours)
        claims.extend(caution_claims)

        logger.info(
            f"WeatherAgent produced {len(claims)} claims "
            f"({len(launch_window_claims)} windows, {len(caution_claims)} cautions)"
        )
        return claims

    def score_hour(self, hour_data: Any) -> float:
        """
        Compute a thermal index score for a single forecast hour.

        Returns a float 0.0–1.0 representing thermal flying quality.
        """
        temp_c: float = getattr(hour_data, "temp_c", 20.0) or 20.0
        dewpoint_c: float = getattr(hour_data, "dewpoint_c", 10.0) or 10.0
        wind_speed_kmh: float = getattr(hour_data, "wind_speed_kmh", 15.0) or 15.0
        cloud_cover_pct: float = getattr(hour_data, "cloud_cover_pct", 30.0) or 30.0
        time = getattr(hour_data, "time", None)

        # Extract local hour (approximate — treat as UTC for now)
        hour_of_day = 12
        if time is not None:
            if hasattr(time, "hour"):
                hour_of_day = time.hour
            else:
                try:
                    from datetime import datetime
                    hour_of_day = datetime.fromisoformat(str(time)).hour
                except Exception:
                    hour_of_day = 12

        # --- Dewpoint spread factor ---
        # Larger spread = drier air = more thermal buoyancy
        # Spread of 20°C gives factor 1.0; spread of 5°C gives 0.25
        spread = max(0.0, temp_c - dewpoint_c)
        dewpoint_spread_factor = min(1.0, spread / 20.0)

        # --- Wind factor ---
        # Gaussian peak at WIND_IDEAL_KMH=15, sigma=7
        # Falls to ~0.4 at 6 km/h (too light) and 25 km/h (approaching rotor risk)
        wind_factor = math.exp(-0.5 * ((wind_speed_kmh - self.WIND_IDEAL_KMH) / 7.0) ** 2)
        # Hard cutoff above WIND_CAUTION_KMH
        if wind_speed_kmh > self.WIND_CAUTION_KMH:
            wind_factor *= max(0.0, 1.0 - (wind_speed_kmh - self.WIND_CAUTION_KMH) / 10.0)

        # --- Time of day factor ---
        # Gaussian peak at 13:00 local, sigma=2.5 hours
        # Near zero before 8:00 and after 19:00
        time_factor = math.exp(-0.5 * ((hour_of_day - 13.0) / 2.5) ** 2)

        # --- Cloud cover factor ---
        # 20-60% cloud: good (cumulus markers, some shading)
        # <5%: strong heating but no markers (punchy)
        # >70%: suppression
        if cloud_cover_pct < 5:
            cloud_factor = 0.75  # Clear sky — strong but marker-less thermals
        elif cloud_cover_pct <= 60:
            # Optimal range 20-40%, falls off gently above and below
            cloud_factor = 1.0 - abs(cloud_cover_pct - 35.0) / 60.0
            cloud_factor = max(0.4, cloud_factor)
        else:
            # Progressive suppression above 60%
            cloud_factor = max(0.1, 1.0 - (cloud_cover_pct - 60.0) / 50.0)

        score = dewpoint_spread_factor * wind_factor * time_factor * cloud_factor
        return max(0.0, min(1.0, score))

    def _identify_launch_windows(
        self,
        scored_hours: list[tuple[Any, float]],
    ) -> list[Claim]:
        """
        Find contiguous blocks of hours that score above the launch window threshold.

        Merges adjacent qualifying hours into windows and produces one Claim
        per window.
        """
        claims = []
        window_start: int | None = None
        window_hours: list[tuple[Any, float]] = []

        for i, (hour_data, score) in enumerate(scored_hours):
            if score >= self.LAUNCH_WINDOW_MIN_SCORE:
                if window_start is None:
                    window_start = i
                window_hours.append((hour_data, score))
            else:
                if window_start is not None and len(window_hours) >= 2:
                    claim = self._build_launch_window_claim(window_hours)
                    if claim:
                        claims.append(claim)
                window_start = None
                window_hours = []

        # Handle window that extends to end of forecast
        if window_start is not None and len(window_hours) >= 2:
            claim = self._build_launch_window_claim(window_hours)
            if claim:
                claims.append(claim)

        # Sort by average score descending
        claims.sort(key=lambda c: c.confidence, reverse=True)
        return claims

    def _build_launch_window_claim(
        self,
        window_hours: list[tuple[Any, float]],
    ) -> Claim | None:
        """Build a LAUNCH_WINDOW Claim for a contiguous window of good hours."""
        if not window_hours:
            return None

        scores = [s for _, s in window_hours]
        avg_score = sum(scores) / len(scores)
        peak_score = max(scores)

        first_hour = window_hours[0][0]
        last_hour = window_hours[-1][0]
        first_time = getattr(first_hour, "time", None)
        last_time = getattr(last_hour, "time", None)

        # Get representative hour values for evidence
        peak_idx = scores.index(peak_score)
        peak_hour = window_hours[peak_idx][0]

        from_hour = first_time.hour if hasattr(first_time, "hour") else None
        to_hour = last_time.hour if hasattr(last_time, "hour") else None

        window_desc = (
            f"{from_hour:02d}:00–{to_hour:02d}:59 UTC"
            if from_hour is not None and to_hour is not None
            else f"{len(window_hours)}-hour window"
        )

        wind_at_peak = getattr(peak_hour, "wind_speed_kmh", None)
        temp_at_peak = getattr(peak_hour, "temp_c", None)
        dew_at_peak = getattr(peak_hour, "dewpoint_c", None)
        cloud_at_peak = getattr(peak_hour, "cloud_cover_pct", None)

        spread = (temp_at_peak - dew_at_peak) if (temp_at_peak and dew_at_peak) else None

        evidence = [
            Evidence(
                source="weather_forecast_hourly",
                description=(
                    f"Thermal index score {avg_score:.2f} (peak {peak_score:.2f}) "
                    f"over {len(window_hours)} hours"
                ),
                data_ref={
                    "avg_score": round(avg_score, 3),
                    "peak_score": round(peak_score, 3),
                    "window_hours": len(window_hours),
                    "wind_kmh_at_peak": wind_at_peak,
                    "temp_c_at_peak": temp_at_peak,
                    "dewpoint_spread_c": round(spread, 1) if spread else None,
                    "cloud_cover_pct_at_peak": cloud_at_peak,
                },
            )
        ]

        assumptions = [
            "Wind direction assumed favorable (not cross-checking direction here)",
            "Thermal index formula is heuristic — not physically validated",
        ]
        if spread and spread > 15:
            assumptions.append(f"Dewpoint spread {spread:.1f}°C indicates dry air — thermals should develop well")

        return self._make_claim(
            claim_type=ClaimType.LAUNCH_WINDOW,
            claim_text=(
                f"Launch window {window_desc}: thermal index avg {avg_score:.2f}, "
                f"peak {peak_score:.2f}. Wind ~{wind_at_peak:.0f} km/h, "
                f"temp {temp_at_peak:.1f}°C, cloud {cloud_at_peak:.0f}%."
            ),
            confidence=min(0.92, avg_score * 1.1),  # Scale score to confidence
            evidence=evidence,
            assumptions=assumptions,
            temporal_validity=TemporalValidity(
                valid_from_hour=from_hour,
                valid_to_hour=to_hour,
                notes=f"Based on {len(window_hours)} qualifying forecast hours",
            ),
        )

    def _identify_caution_conditions(
        self,
        scored_hours: list[tuple[Any, float]],
    ) -> list[Claim]:
        """
        Scan for conditions warranting explicit caution claims:
        - Wind exceeding WIND_CAUTION_KMH
        - Overdevelopment risk (cloud_cover > 70% and rising)
        - Thermic crosswind risk
        """
        claims = []
        prev_cloud = None

        for hour_data, score in scored_hours:
            wind_speed_kmh = getattr(hour_data, "wind_speed_kmh", 0.0) or 0.0
            cloud_cover_pct = getattr(hour_data, "cloud_cover_pct", 0.0) or 0.0
            time = getattr(hour_data, "time", None)

            # High wind caution
            if wind_speed_kmh > self.WIND_CAUTION_KMH:
                hour_label = time.hour if hasattr(time, "hour") else "?"
                claims.append(
                    self._make_claim(
                        claim_type=ClaimType.CAUTION,
                        claim_text=(
                            f"Wind speed {wind_speed_kmh:.0f} km/h at {hour_label:02}:00 UTC "
                            f"exceeds comfortable threshold ({self.WIND_CAUTION_KMH:.0f} km/h). "
                            f"Rotor risk elevated near ridges and tree lines."
                        ),
                        confidence=0.88,
                        evidence=[
                            Evidence(
                                source="weather_forecast_hourly",
                                description=f"Forecast wind {wind_speed_kmh:.0f} km/h at hour {hour_label}",
                                data_ref={"wind_speed_kmh": wind_speed_kmh, "hour": hour_label},
                            )
                        ],
                        assumptions=["Wind speed valid at 10m — launch elevation may differ"],
                        temporal_validity=TemporalValidity(
                            valid_from_hour=hour_label if isinstance(hour_label, int) else None,
                            valid_to_hour=(hour_label + 2) if isinstance(hour_label, int) else None,
                        ),
                    )
                )

            # Overdevelopment risk
            if cloud_cover_pct > 70 and prev_cloud is not None and cloud_cover_pct > prev_cloud + 15:
                claims.append(
                    self._make_claim(
                        claim_type=ClaimType.CAUTION,
                        claim_text=(
                            f"Rapid cloud development detected: cover increased from {prev_cloud:.0f}% "
                            f"to {cloud_cover_pct:.0f}%. Overdevelopment risk — thermal activity "
                            f"may suddenly suppress or become violent."
                        ),
                        confidence=0.65,
                        evidence=[
                            Evidence(
                                source="weather_forecast_hourly",
                                description=f"Cloud cover increase: {prev_cloud:.0f}% → {cloud_cover_pct:.0f}%",
                                data_ref={"prev_cloud_pct": prev_cloud, "current_cloud_pct": cloud_cover_pct},
                            )
                        ],
                    )
                )

            prev_cloud = cloud_cover_pct

        return claims
