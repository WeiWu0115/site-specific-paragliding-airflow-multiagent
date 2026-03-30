"""
RiskAgent for paraglide-backend.

Runs after all other agents. Detects conflicts between agent claims,
identifies low-confidence regions, flags high-wind threshold violations,
and produces Caution claims with clear conflict descriptions.
"""

from typing import Any

from loguru import logger

from agents.base import AgentBase, Claim, ClaimType, Evidence, SpatialScope, TemporalValidity


# Claim types that conflict with each other
CONFLICTING_PAIRS = [
    (ClaimType.RIDGE_LIFT, ClaimType.SINK_ZONE),
    (ClaimType.RIDGE_LIFT, ClaimType.ROTOR_RISK),
    (ClaimType.THERMAL_ZONE, ClaimType.SINK_ZONE),
    (ClaimType.THERMAL_ZONE, ClaimType.CAUTION),
    (ClaimType.LAUNCH_WINDOW, ClaimType.CAUTION),
]

# Minimum confidence for a claim to be trusted without a review
TRUST_THRESHOLD = 0.40

# Wind speed (km/h) above which automatic caution is escalated
HIGH_WIND_THRESHOLD = 25.0


class RiskAgent(AgentBase):
    """
    Post-processing agent that reviews all claims for conflicts and risks.

    Expected context keys:
        prior_claims: list[Claim] — all claims from previous agents
        site_profile: site profile dict (for risk_notes)

    Produces additional Caution claims when:
    1. Two agents make contradictory claims about the same region
    2. An area has no claims above TRUST_THRESHOLD (unknown zone)
    3. Wind speed in any prior claim implies > HIGH_WIND_THRESHOLD
    4. A pre-defined site risk zone is activated by current conditions
    """

    name = "risk_agent"
    reliability_weight: float = 0.90  # Risk agent is high-reliability by design

    async def run(self, context: dict[str, Any]) -> list[Claim]:
        """
        Review all prior claims for conflicts and risk conditions.
        """
        prior_claims: list[Claim] = context.get("prior_claims", [])
        site_profile = context.get("site_profile", {})
        wind_speed_kmh: float = float(context.get("wind_speed_kmh", 0.0))

        if not prior_claims and wind_speed_kmh < HIGH_WIND_THRESHOLD:
            logger.info("RiskAgent: no prior claims and no high wind — nothing to assess")
            return []

        logger.info(f"RiskAgent reviewing {len(prior_claims)} claims")

        risk_claims: list[Claim] = []

        # 1. Detect conflicting claims between agents
        conflict_claims = self.detect_conflicts(prior_claims)
        risk_claims.extend(conflict_claims)

        # 2. Detect low-confidence regions
        low_conf_claims = self._detect_low_confidence_zones(prior_claims)
        risk_claims.extend(low_conf_claims)

        # 3. High wind escalation
        if wind_speed_kmh > HIGH_WIND_THRESHOLD:
            risk_claims.append(self._build_high_wind_caution(wind_speed_kmh, prior_claims))

        # 4. Flag site risk notes that were not already covered
        site_risk_notes = site_profile.get("risk_notes", [])
        for risk_note in site_risk_notes:
            if "rotor" in risk_note.lower() or "incident" in risk_note.lower():
                if not any("incident" in c.claim_text.lower() for c in prior_claims):
                    risk_claims.append(
                        self._make_claim(
                            claim_type=ClaimType.CAUTION,
                            claim_text=f"SITE RISK NOTE: {risk_note}",
                            confidence=0.92,
                            evidence=[
                                Evidence(
                                    source="site_profile_risk_notes",
                                    description="From site profile risk_notes section",
                                    data_ref={"note": risk_note},
                                )
                            ],
                        )
                    )

        logger.info(f"RiskAgent produced {len(risk_claims)} risk claims")
        return risk_claims

    def detect_conflicts(self, claims: list[Claim]) -> list[Claim]:
        """
        Find pairs of claims from different agents that contradict each other
        for the same spatial region.

        Returns Caution claims describing each detected conflict.
        """
        conflict_claims: list[Claim] = []
        seen_conflicts: set[frozenset] = set()

        for i, claim_a in enumerate(claims):
            for j, claim_b in enumerate(claims):
                if i >= j:
                    continue
                if claim_a.agent_name == claim_b.agent_name:
                    continue  # Same agent — not an inter-agent conflict

                # Check if this is a conflicting pair
                pair = (claim_a.claim_type, claim_b.claim_type)
                reverse_pair = (claim_b.claim_type, claim_a.claim_type)

                is_conflicting = (
                    tuple(pair) in [(a.value, b.value) for a, b in CONFLICTING_PAIRS]
                    or tuple(reverse_pair) in [(a.value, b.value) for a, b in CONFLICTING_PAIRS]
                )

                if not is_conflicting:
                    continue

                # Check spatial overlap (same feature name or both have no spatial scope)
                region_a = claim_a.spatial_scope.feature_name if claim_a.spatial_scope else None
                region_b = claim_b.spatial_scope.feature_name if claim_b.spatial_scope else None

                # Consider overlapping if both name the same feature, or both are site-wide
                spatially_related = (
                    (region_a and region_b and region_a == region_b)
                    or (region_a is None and region_b is None)
                    or (region_a and region_b and (region_a in region_b or region_b in region_a))
                )

                if not spatially_related:
                    continue

                # Avoid duplicate conflict notices
                conflict_key = frozenset([claim_a.id, claim_b.id])
                if conflict_key in seen_conflicts:
                    continue
                seen_conflicts.add(conflict_key)

                # Build conflict description
                region_name = region_a or region_b or "this area"
                conflict_confidence = max(0.60, (claim_a.confidence + claim_b.confidence) / 2)

                conflict_claims.append(
                    self._make_claim(
                        claim_type=ClaimType.CAUTION,
                        claim_text=(
                            f"AGENT DISAGREEMENT: {claim_a.agent_name} says '{claim_a.claim_type.value}' "
                            f"at {region_name}, but {claim_b.agent_name} says '{claim_b.claim_type.value}'. "
                            f"Confidence scores: {claim_a.confidence:.2f} vs {claim_b.confidence:.2f}. "
                            f"Do not over-trust either recommendation for this zone."
                        ),
                        confidence=conflict_confidence,
                        evidence=[
                            Evidence(
                                source=f"conflict_detection",
                                description=(
                                    f"Detected contradiction between "
                                    f"{claim_a.agent_name}({claim_a.claim_type.value}) and "
                                    f"{claim_b.agent_name}({claim_b.claim_type.value})"
                                ),
                                data_ref={
                                    "claim_a_id": claim_a.id,
                                    "claim_b_id": claim_b.id,
                                    "claim_a_agent": claim_a.agent_name,
                                    "claim_b_agent": claim_b.agent_name,
                                    "region": region_name,
                                },
                            )
                        ],
                        assumptions=[
                            "Conflict detected based on claim types and feature names",
                            "Spatial overlap not verified with geometry — feature name matching only",
                        ],
                        spatial_scope=SpatialScope(feature_name=region_name),
                    )
                )

        return conflict_claims

    def _detect_low_confidence_zones(self, claims: list[Claim]) -> list[Claim]:
        """
        Identify spatial regions where all claims have low confidence.

        Returns a Caution claim for each low-confidence region.
        """
        risk_claims: list[Claim] = []

        # Group claims by feature region
        region_claims: dict[str, list[Claim]] = {}
        for claim in claims:
            region = (
                claim.spatial_scope.feature_name
                if claim.spatial_scope and claim.spatial_scope.feature_name
                else "site-wide"
            )
            if region not in region_claims:
                region_claims[region] = []
            region_claims[region].append(claim)

        for region, region_claim_list in region_claims.items():
            if not region_claim_list:
                continue

            max_confidence = max(c.confidence for c in region_claim_list)
            avg_confidence = sum(c.confidence for c in region_claim_list) / len(region_claim_list)
            agent_count = len(set(c.agent_name for c in region_claim_list))

            if max_confidence < TRUST_THRESHOLD and agent_count <= 1:
                risk_claims.append(
                    self._make_claim(
                        claim_type=ClaimType.CAUTION,
                        claim_text=(
                            f"LOW CONFIDENCE ZONE: All claims for '{region}' are below "
                            f"trust threshold (max confidence: {max_confidence:.2f}, "
                            f"avg: {avg_confidence:.2f}). "
                            f"Only {agent_count} agent(s) have assessed this area. "
                            f"Treat this zone as unknown — do not assume safe or flyable."
                        ),
                        confidence=0.70,
                        evidence=[
                            Evidence(
                                source="risk_agent_confidence_review",
                                description=f"Low-confidence zone: max={max_confidence:.2f}",
                                data_ref={
                                    "region": region,
                                    "max_confidence": max_confidence,
                                    "avg_confidence": round(avg_confidence, 3),
                                    "agent_count": agent_count,
                                },
                            )
                        ],
                        spatial_scope=SpatialScope(feature_name=region),
                    )
                )

        return risk_claims

    def _build_high_wind_caution(
        self,
        wind_speed_kmh: float,
        prior_claims: list[Claim],
    ) -> Claim:
        """Build a site-wide high wind caution claim."""
        # Find any launch window claims to explicitly contradict
        launch_window_claims = [c for c in prior_claims if c.claim_type == ClaimType.LAUNCH_WINDOW]
        launch_note = ""
        if launch_window_claims:
            launch_note = (
                f" NOTE: {len(launch_window_claims)} launch window claim(s) exist — "
                f"re-evaluate them given wind speed."
            )

        return self._make_claim(
            claim_type=ClaimType.CAUTION,
            claim_text=(
                f"HIGH WIND ALERT: wind speed {wind_speed_kmh:.0f} km/h exceeds "
                f"safe threshold ({HIGH_WIND_THRESHOLD:.0f} km/h). "
                f"Rotor risk near all ridges and tree lines is elevated. "
                f"Turbulence likely in lee zones. Re-evaluate all lift recommendations.{launch_note}"
            ),
            confidence=0.90,
            evidence=[
                Evidence(
                    source="risk_agent_wind_threshold",
                    description=f"Wind {wind_speed_kmh:.0f} km/h > {HIGH_WIND_THRESHOLD:.0f} km/h threshold",
                    data_ref={"wind_speed_kmh": wind_speed_kmh, "threshold_kmh": HIGH_WIND_THRESHOLD},
                )
            ],
            assumptions=["Wind speed from weather forecast — actual conditions may vary"],
        )
