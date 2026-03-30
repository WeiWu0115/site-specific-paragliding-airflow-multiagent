"""
CloudAgent for paraglide-backend.

Analyzes cloud observation data to assess thermal development potential,
overdevelopment risk, and suppression conditions.
"""

from datetime import datetime
from typing import Any

from loguru import logger

from agents.base import AgentBase, Claim, ClaimType, Evidence, SpatialScope, TemporalValidity


class CloudAgent(AgentBase):
    """
    Reasons about cloud cover data to assess thermal conditions.

    Expected context keys:
        cloud_observation: CloudObservation dataclass from data_ingestion.clouds.cloud_provider_base
        site_profile: site profile dict (optional, used for context)

    Cloud cover interpretation:
        < 10%: strong solar heating, thermals likely punchy and uncapped
        10-30%: excellent conditions, cumulus beginning
        30-60%: optimal — cloud markers present, organized development
        60-75%: transition zone — thermal cycles becoming irregular
        > 75%: suppression — shading significantly reduces thermal development
        Rapidly increasing: overdevelopment caution
    """

    name = "cloud_agent"
    reliability_weight: float = 0.65  # Lower than weather — cloud data often coarser

    async def run(self, context: dict[str, Any]) -> list[Claim]:
        """
        Analyze cloud observation and produce claims about thermal potential.
        """
        observation = context.get("cloud_observation")
        if observation is None:
            logger.warning("CloudAgent: no cloud_observation in context")
            return []

        cover_pct: float = getattr(observation, "cover_pct", 30.0) or 30.0
        cloud_base_m: float | None = getattr(observation, "cloud_base_m", None)
        cloud_type_hint: str | None = getattr(observation, "cloud_type_hint", None)
        observed_at: datetime | None = getattr(observation, "observed_at", None)
        confidence: float = getattr(observation, "confidence", 0.5) or 0.5

        logger.info(
            f"CloudAgent analyzing: {cover_pct:.0f}% cover, "
            f"base {cloud_base_m}m, type={cloud_type_hint}"
        )

        claims: list[Claim] = []

        base_evidence = Evidence(
            source="cloud_observation",
            description=f"Cloud cover {cover_pct:.0f}%, base {cloud_base_m}m, type: {cloud_type_hint}",
            data_ref={
                "cover_pct": cover_pct,
                "cloud_base_m": cloud_base_m,
                "cloud_type_hint": cloud_type_hint,
                "observed_at": observed_at.isoformat() if observed_at else None,
                "data_confidence": confidence,
            },
        )

        if cover_pct < 10:
            claims.append(self._build_clear_sky_claim(cover_pct, cloud_base_m, base_evidence, confidence))

        elif cover_pct <= 60:
            if cloud_type_hint and any(t in cloud_type_hint.lower() for t in ["cumulus", "cu", "fair"]):
                claims.append(self._build_cumulus_development_claim(cover_pct, cloud_base_m, base_evidence, confidence))
            else:
                claims.append(self._build_partial_cloud_claim(cover_pct, cloud_base_m, base_evidence, confidence))

        else:
            claims.append(self._build_suppression_claim(cover_pct, cloud_base_m, base_evidence, confidence))

        # High base = thermals can go high
        if cloud_base_m and cloud_base_m > 2500:
            claims.append(
                self._make_claim(
                    claim_type=ClaimType.THERMAL_ZONE,
                    claim_text=(
                        f"Cloud base {cloud_base_m:.0f}m indicates thermals can reach high altitude "
                        f"before triggering — excellent XC potential if base stays consistent."
                    ),
                    confidence=0.60 * confidence,
                    evidence=[base_evidence],
                    assumptions=["Cloud base from observation, not radiosonde"],
                    temporal_validity=TemporalValidity(
                        valid_from_hour=10,
                        valid_to_hour=16,
                        notes="High base conditions typically persist midday",
                    ),
                )
            )

        # Low base = overdevelopment risk
        if cloud_base_m and cloud_base_m < 1800 and cover_pct > 50:
            claims.append(
                self._make_claim(
                    claim_type=ClaimType.CAUTION,
                    claim_text=(
                        f"Low cloud base ({cloud_base_m:.0f}m) combined with {cover_pct:.0f}% cover "
                        f"suggests overdevelopment potential. Thermal tops may be limited and "
                        f"conditions may deteriorate rapidly."
                    ),
                    confidence=0.70 * confidence,
                    evidence=[base_evidence],
                )
            )

        logger.info(f"CloudAgent produced {len(claims)} claims")
        return claims

    def _build_clear_sky_claim(
        self,
        cover_pct: float,
        cloud_base_m: float | None,
        evidence: Evidence,
        data_confidence: float,
    ) -> Claim:
        return self._make_claim(
            claim_type=ClaimType.THERMAL_ZONE,
            claim_text=(
                f"Clear sky ({cover_pct:.0f}% cover): strong solar heating expected. "
                f"Thermals likely punchy and narrow without cloud markers to identify cores. "
                f"Expect fast, violent thermals in early afternoon. "
                f"Wing load and active flying technique recommended."
            ),
            confidence=0.72 * data_confidence,
            evidence=[evidence],
            assumptions=["No cloud markers — thermal identification requires active scanning"],
            temporal_validity=TemporalValidity(
                valid_from_hour=10,
                valid_to_hour=16,
                notes="Clear sky thermals typically peak 12-14:00",
            ),
        )

    def _build_cumulus_development_claim(
        self,
        cover_pct: float,
        cloud_base_m: float | None,
        evidence: Evidence,
        data_confidence: float,
    ) -> Claim:
        base_desc = f" at {cloud_base_m:.0f}m" if cloud_base_m else ""
        return self._make_claim(
            claim_type=ClaimType.THERMAL_ZONE,
            claim_text=(
                f"Cumulus development ({cover_pct:.0f}% cover{base_desc}): thermal markers visible. "
                f"Organized thermal streets may form. Use cloud shadows and building cumulus "
                f"to navigate thermal sources. Excellent conditions for XC flight."
            ),
            confidence=0.82 * data_confidence,
            evidence=[evidence],
            temporal_validity=TemporalValidity(
                valid_from_hour=10,
                valid_to_hour=15,
                notes="Cumulus-supported thermals peak 11:00-14:00",
            ),
        )

    def _build_partial_cloud_claim(
        self,
        cover_pct: float,
        cloud_base_m: float | None,
        evidence: Evidence,
        data_confidence: float,
    ) -> Claim:
        return self._make_claim(
            claim_type=ClaimType.THERMAL_ZONE,
            claim_text=(
                f"Partly cloudy ({cover_pct:.0f}% cover): thermal cycles present but shading "
                f"between cloud patches may create irregular intervals. "
                f"Watch for darkening between thermal cycles indicating suppression."
            ),
            confidence=0.62 * data_confidence,
            evidence=[evidence],
            temporal_validity=TemporalValidity(valid_from_hour=10, valid_to_hour=15),
        )

    def _build_suppression_claim(
        self,
        cover_pct: float,
        cloud_base_m: float | None,
        evidence: Evidence,
        data_confidence: float,
    ) -> Claim:
        return self._make_claim(
            claim_type=ClaimType.CAUTION,
            claim_text=(
                f"Heavy cloud cover ({cover_pct:.0f}%): thermal development significantly suppressed. "
                f"Solar insolation reduced — thermals weak and unreliable. "
                f"Ridge soaring may still be viable if wind is favorable."
            ),
            confidence=0.78 * data_confidence,
            evidence=[evidence],
        )
