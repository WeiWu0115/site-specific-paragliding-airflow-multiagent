"""
Launch timing ranker for paraglide-backend.

Scores each hour of a weather forecast for flying suitability, combining
thermal likelihood with wind suitability to produce ranked LaunchWindow objects.
"""

import math
from dataclasses import dataclass, field
from typing import Any

from loguru import logger

from ml.thermal_scorer import ThermalScorer


@dataclass
class LaunchWindow:
    """A recommended launch time window with confidence and reasoning."""
    start_hour: int
    end_hour: int
    score: float          # Combined thermal + wind suitability score (0-1)
    confidence: float     # Calibrated confidence (0-1)
    reasons: list[str] = field(default_factory=list)


class LaunchTimingRanker:
    """
    Ranks hourly forecast entries for launch suitability.

    Combines:
    - ThermalScorer for thermal likelihood at site terrain features
    - Wind suitability: speed in range + direction aligned with launches
    - Time of day preference
    """

    # Wind speed range for comfortable flying (km/h)
    WIND_MIN_KMH = 8.0
    WIND_IDEAL_KMH = 14.0
    WIND_MAX_SAFE_KMH = 22.0

    def __init__(self, scorer: ThermalScorer | None = None) -> None:
        self._scorer = scorer or ThermalScorer()

    def rank_hours(
        self,
        hourly_weather: list[Any],
        site_profile: dict[str, Any],
    ) -> list[LaunchWindow]:
        """
        Score each forecast hour and return ranked LaunchWindow objects.

        Args:
            hourly_weather: List of WeatherHour objects
            site_profile: Site profile dict with terrain features and launches

        Returns:
            List of LaunchWindow objects sorted by score descending
        """
        if not hourly_weather:
            logger.warning("LaunchTimingRanker: no weather data provided")
            return []

        terrain_features = site_profile.get("terrain_features", [])
        launches = site_profile.get("launches", [])

        # Use primary launch optimal wind direction
        primary_launch_dir = 225.0
        if launches:
            primary_launch_dir = float(
                launches[0].get("facing_degrees", 225.0) or 225.0
            )

        scored_hours = []
        for hour_data in hourly_weather:
            score, reasons = self._score_single_hour(
                hour_data, terrain_features, primary_launch_dir
            )
            scored_hours.append((hour_data, score, reasons))

        # Build windows from scored hours
        windows = self._build_windows(scored_hours)
        windows.sort(key=lambda w: w.score, reverse=True)

        logger.info(f"LaunchTimingRanker: {len(windows)} windows from {len(hourly_weather)} forecast hours")
        return windows

    def _score_single_hour(
        self,
        hour_data: Any,
        terrain_features: list[dict],
        launch_dir_deg: float,
    ) -> tuple[float, list[str]]:
        """Score a single forecast hour. Returns (score, reasons)."""
        reasons: list[str] = []

        wind_speed = float(getattr(hour_data, "wind_speed_kmh", 15.0) or 15.0)
        wind_dir = float(getattr(hour_data, "wind_dir_deg", 225.0) or 225.0)
        temp_c = float(getattr(hour_data, "temp_c", 20.0) or 20.0)
        dewpoint_c = float(getattr(hour_data, "dewpoint_c", 10.0) or 10.0)
        cloud = float(getattr(hour_data, "cloud_cover_pct", 30.0) or 30.0)
        time = getattr(hour_data, "time", None)
        hour = time.hour if hasattr(time, "hour") else 12

        # --- Wind suitability ---
        if wind_speed < self.WIND_MIN_KMH:
            wind_suit = 0.30
            reasons.append(f"Wind {wind_speed:.0f} km/h — may be too light for clean launch")
        elif wind_speed <= self.WIND_MAX_SAFE_KMH:
            # Gaussian peak at WIND_IDEAL_KMH
            wind_suit = math.exp(-0.5 * ((wind_speed - self.WIND_IDEAL_KMH) / 5.0) ** 2)
            wind_suit = 0.60 + 0.40 * wind_suit
            reasons.append(f"Wind {wind_speed:.0f} km/h — good range")
        else:
            wind_suit = max(0.10, 1.0 - (wind_speed - self.WIND_MAX_SAFE_KMH) / 15.0)
            reasons.append(f"Wind {wind_speed:.0f} km/h — approaching upper limit")

        # --- Wind direction alignment with launch ---
        angle_diff = abs(((wind_dir - launch_dir_deg + 180) % 360) - 180)
        if angle_diff <= 30:
            dir_suit = 1.0
            reasons.append(f"Wind direction {wind_dir:.0f}° well aligned with launch ({launch_dir_deg:.0f}°)")
        elif angle_diff <= 60:
            dir_suit = 0.75
            reasons.append(f"Wind direction acceptable ({angle_diff:.0f}° off ideal)")
        else:
            dir_suit = 0.30
            reasons.append(f"Wind direction {wind_dir:.0f}° — crosswind or tailwind concern")

        # --- Thermal potential from scorer ---
        primary_terrain = next(
            (f for f in terrain_features if f.get("type") == "ridge"), {}
        ) or (terrain_features[0] if terrain_features else {"type": "ridge", "attributes": {}})

        thermal_score = self._scorer.get_rule_based_score(hour_data, primary_terrain)
        if thermal_score > 0.50:
            reasons.append(f"Thermal index {thermal_score:.2f} — thermals expected")
        elif thermal_score > 0.30:
            reasons.append(f"Thermal index {thermal_score:.2f} — light thermal activity")
        else:
            reasons.append(f"Thermal index {thermal_score:.2f} — limited thermal potential")

        # --- Time of day preference ---
        if 10 <= hour <= 15:
            time_suit = 1.0
        elif 8 <= hour <= 17:
            time_suit = 0.70
        else:
            time_suit = 0.20

        # Combined score
        combined = (
            0.35 * thermal_score
            + 0.25 * wind_suit
            + 0.25 * dir_suit
            + 0.15 * time_suit
        )

        return round(combined, 3), reasons

    def _build_windows(
        self,
        scored_hours: list[tuple[Any, float, list[str]]],
    ) -> list[LaunchWindow]:
        """Convert scored hours into contiguous LaunchWindow objects."""
        THRESHOLD = 0.35
        windows = []
        current_start: int | None = None
        current_hours = []
        current_reasons: list[str] = []

        for hour_data, score, reasons in scored_hours:
            time = getattr(hour_data, "time", None)
            hour = time.hour if hasattr(time, "hour") else 12

            if score >= THRESHOLD:
                if current_start is None:
                    current_start = hour
                current_hours.append(score)
                current_reasons.extend(reasons[:1])  # One reason per hour
            else:
                if current_start is not None and current_hours:
                    avg_score = sum(current_hours) / len(current_hours)
                    windows.append(LaunchWindow(
                        start_hour=current_start,
                        end_hour=hour - 1,
                        score=round(avg_score, 3),
                        confidence=min(0.90, avg_score + 0.05),
                        reasons=list(set(current_reasons)),
                    ))
                current_start = None
                current_hours = []
                current_reasons = []

        if current_start is not None and current_hours:
            avg_score = sum(current_hours) / len(current_hours)
            last_hour = getattr(scored_hours[-1][0], "time", None)
            last_h = last_hour.hour if hasattr(last_hour, "hour") else 23
            windows.append(LaunchWindow(
                start_hour=current_start,
                end_hour=last_h,
                score=round(avg_score, 3),
                confidence=min(0.90, avg_score + 0.05),
                reasons=list(set(current_reasons)),
            ))

        return windows
