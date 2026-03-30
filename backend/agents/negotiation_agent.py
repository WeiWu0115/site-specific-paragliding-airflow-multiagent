"""
NegotiationAgent (ArbiterAgent) for paraglide-backend.

Receives all claims from all agents, aggregates them by spatial region and
claim type, detects disagreements, and produces a ranked NegotiationResult
with full evidence traces and uncertainty summary.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from loguru import logger

from agents.base import Claim, ClaimType

# Agent reliability weights for confidence aggregation
AGENT_WEIGHTS = {
    "weather_agent": 0.85,
    "terrain_agent": 0.80,
    "cloud_agent": 0.65,
    "local_knowledge_agent": 0.75,
    "flight_history_agent": 0.70,
    "risk_agent": 0.90,
}
DEFAULT_WEIGHT = 0.60


@dataclass
class RankedLaunchWindow:
    """A ranked launch window recommendation from the NegotiationAgent."""
    rank: int
    title: str
    description: str
    confidence: float
    uncertainty_note: str
    evidence_summary: list[str]
    supporting_claims: list[Claim] = field(default_factory=list)
    valid_from_hour: int | None = None
    valid_to_hour: int | None = None


@dataclass
class RankedZone:
    """A ranked thermal, ridge, or other zone recommendation."""
    rank: int
    zone_type: str
    title: str
    description: str
    confidence: float
    uncertainty_note: str
    evidence_summary: list[str]
    supporting_claims: list[Claim] = field(default_factory=list)
    feature_name: str | None = None
    geojson: dict | None = None


@dataclass
class CautionZone:
    """A caution zone derived from risk agent and conflict detection."""
    title: str
    description: str
    confidence: float
    caution_type: str
    conflict_description: str | None = None
    feature_name: str | None = None
    supporting_claims: list[Claim] = field(default_factory=list)


@dataclass
class AgentDisagreement:
    """A recorded disagreement between two agents."""
    region: str
    agent_a: str
    agent_b: str
    claim_type_a: str
    claim_type_b: str
    confidence_a: float
    confidence_b: float
    description: str


@dataclass
class NegotiationResult:
    """Full output of the NegotiationAgent arbitration process."""
    session_id: int | None = None
    ranked_launch_windows: list[RankedLaunchWindow] = field(default_factory=list)
    ranked_trigger_zones: list[RankedZone] = field(default_factory=list)
    ranked_ridge_corridors: list[RankedZone] = field(default_factory=list)
    caution_zones: list[CautionZone] = field(default_factory=list)
    evidence_traces: dict[str, list[str]] = field(default_factory=dict)
    uncertainty_summary: str = ""
    agent_disagreements: list[AgentDisagreement] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialize result to JSON-compatible dict."""
        return {
            "session_id": self.session_id,
            "ranked_launch_windows": [
                {
                    "rank": w.rank,
                    "title": w.title,
                    "description": w.description,
                    "confidence": w.confidence,
                    "uncertainty_note": w.uncertainty_note,
                    "evidence_summary": w.evidence_summary,
                    "valid_from_hour": w.valid_from_hour,
                    "valid_to_hour": w.valid_to_hour,
                }
                for w in self.ranked_launch_windows
            ],
            "ranked_trigger_zones": [
                {
                    "rank": z.rank,
                    "zone_type": z.zone_type,
                    "title": z.title,
                    "description": z.description,
                    "confidence": z.confidence,
                    "uncertainty_note": z.uncertainty_note,
                    "evidence_summary": z.evidence_summary,
                    "feature_name": z.feature_name,
                }
                for z in self.ranked_trigger_zones
            ],
            "ranked_ridge_corridors": [
                {
                    "rank": z.rank,
                    "zone_type": z.zone_type,
                    "title": z.title,
                    "description": z.description,
                    "confidence": z.confidence,
                    "uncertainty_note": z.uncertainty_note,
                    "evidence_summary": z.evidence_summary,
                    "feature_name": z.feature_name,
                }
                for z in self.ranked_ridge_corridors
            ],
            "caution_zones": [
                {
                    "title": c.title,
                    "description": c.description,
                    "confidence": c.confidence,
                    "caution_type": c.caution_type,
                    "conflict_description": c.conflict_description,
                    "feature_name": c.feature_name,
                }
                for c in self.caution_zones
            ],
            "evidence_traces": self.evidence_traces,
            "uncertainty_summary": self.uncertainty_summary,
            "agent_disagreements": [
                {
                    "region": d.region,
                    "agent_a": d.agent_a,
                    "agent_b": d.agent_b,
                    "claim_type_a": d.claim_type_a,
                    "claim_type_b": d.claim_type_b,
                    "description": d.description,
                }
                for d in self.agent_disagreements
            ],
        }


class NegotiationAgent:
    """
    Aggregates all agent claims into a coherent, ranked NegotiationResult.

    Process:
    1. Separate claims by type (launch_window, thermal_zone, ridge_lift, caution, etc.)
    2. Group thermal/lift claims by spatial region
    3. For each group, compute aggregated confidence using agent-weighted average
    4. Detect claim-type conflicts between agents in the same spatial region
    5. Build ranked outputs: launch windows, trigger zones, ridge corridors, caution zones
    6. Compose evidence traces and uncertainty summary
    """

    name = "negotiation_agent"

    async def arbitrate(self, claims: list[Claim]) -> NegotiationResult:
        """
        Main arbitration method. Call with all claims from all agents.

        Returns a NegotiationResult with ranked recommendations.
        """
        if not claims:
            logger.info("NegotiationAgent: no claims to arbitrate")
            return NegotiationResult(
                uncertainty_summary="No agent claims were produced. Unable to assess conditions."
            )

        logger.info(f"NegotiationAgent arbitrating {len(claims)} claims")

        # Separate by claim type
        launch_window_claims = [c for c in claims if c.claim_type == ClaimType.LAUNCH_WINDOW]
        thermal_claims = [c for c in claims if c.claim_type == ClaimType.THERMAL_ZONE]
        ridge_claims = [c for c in claims if c.claim_type == ClaimType.RIDGE_LIFT]
        caution_claims = [c for c in claims if c.claim_type in (ClaimType.CAUTION, ClaimType.ROTOR_RISK)]
        sink_claims = [c for c in claims if c.claim_type == ClaimType.SINK_ZONE]

        # Detect disagreements
        disagreements = self._detect_disagreements(claims)

        # Build outputs
        ranked_windows = self._rank_launch_windows(launch_window_claims, caution_claims)
        ranked_triggers = self._rank_thermal_zones(thermal_claims, caution_claims)
        ranked_ridges = self._rank_ridge_corridors(ridge_claims, sink_claims)
        caution_zones = self._build_caution_zones(caution_claims, sink_claims)

        # Build evidence traces
        evidence_traces = self._build_evidence_traces(
            ranked_windows, ranked_triggers, ranked_ridges, caution_zones
        )

        # Compose uncertainty summary
        uncertainty_summary = self._compose_uncertainty_summary(
            claims, disagreements, ranked_windows, ranked_triggers
        )

        result = NegotiationResult(
            ranked_launch_windows=ranked_windows,
            ranked_trigger_zones=ranked_triggers,
            ranked_ridge_corridors=ranked_ridges,
            caution_zones=caution_zones,
            evidence_traces=evidence_traces,
            uncertainty_summary=uncertainty_summary,
            agent_disagreements=disagreements,
        )

        logger.info(
            f"NegotiationAgent result: "
            f"{len(ranked_windows)} windows, {len(ranked_triggers)} trigger zones, "
            f"{len(ranked_ridges)} ridges, {len(caution_zones)} cautions, "
            f"{len(disagreements)} disagreements"
        )

        return result

    def _weighted_confidence(self, claims: list[Claim]) -> float:
        """Compute weighted average confidence across a list of claims."""
        if not claims:
            return 0.0
        total_weight = 0.0
        weighted_sum = 0.0
        for claim in claims:
            w = AGENT_WEIGHTS.get(claim.agent_name, DEFAULT_WEIGHT)
            weighted_sum += claim.confidence * w
            total_weight += w
        return weighted_sum / total_weight if total_weight > 0 else 0.0

    def _group_by_region(self, claims: list[Claim]) -> dict[str, list[Claim]]:
        """Group claims by their spatial scope feature name."""
        groups: dict[str, list[Claim]] = defaultdict(list)
        for claim in claims:
            region = (
                claim.spatial_scope.feature_name
                if claim.spatial_scope and claim.spatial_scope.feature_name
                else "site-wide"
            )
            groups[region].append(claim)
        return dict(groups)

    def _rank_launch_windows(
        self,
        window_claims: list[Claim],
        caution_claims: list[Claim],
    ) -> list[RankedLaunchWindow]:
        """Rank launch window claims by confidence, penalized by conflicting cautions."""
        if not window_claims:
            return []

        # Sort by confidence descending
        sorted_claims = sorted(window_claims, key=lambda c: c.confidence, reverse=True)

        windows = []
        for rank, claim in enumerate(sorted_claims, 1):
            # Check for conflicting high-wind cautions
            wind_cautions = [
                c for c in caution_claims
                if "wind" in c.claim_text.lower() and "high" in c.claim_text.lower()
            ]
            penalty = min(0.30, len(wind_cautions) * 0.10)
            adjusted_confidence = max(0.05, claim.confidence - penalty)

            uncertainty_note = ""
            if penalty > 0:
                uncertainty_note = f"Confidence reduced by {penalty:.2f} due to {len(wind_cautions)} high-wind caution(s)"

            evidence_summary = [e.description for e in claim.evidence[:3]]

            tv = claim.temporal_validity
            windows.append(
                RankedLaunchWindow(
                    rank=rank,
                    title=f"Launch Window #{rank}",
                    description=claim.claim_text,
                    confidence=adjusted_confidence,
                    uncertainty_note=uncertainty_note or "Based on single-agent weather assessment",
                    evidence_summary=evidence_summary,
                    supporting_claims=[claim],
                    valid_from_hour=tv.valid_from_hour if tv else None,
                    valid_to_hour=tv.valid_to_hour if tv else None,
                )
            )

        return windows

    def _rank_thermal_zones(
        self,
        thermal_claims: list[Claim],
        caution_claims: list[Claim],
    ) -> list[RankedZone]:
        """Group thermal claims by region, aggregate confidence, rank by evidence count + confidence."""
        if not thermal_claims:
            return []

        groups = self._group_by_region(thermal_claims)
        zones = []

        for region, region_claims in groups.items():
            agg_confidence = self._weighted_confidence(region_claims)
            agent_names = list(set(c.agent_name for c in region_claims))
            evidence_count = sum(len(c.evidence) for c in region_claims)

            # Check for conflicting cautions in same region
            region_cautions = [
                c for c in caution_claims
                if c.spatial_scope and c.spatial_scope.feature_name and
                region in (c.spatial_scope.feature_name or "")
            ]
            caution_penalty = min(0.25, len(region_cautions) * 0.08)
            final_confidence = max(0.05, agg_confidence - caution_penalty)

            uncertainty_parts = []
            if len(agent_names) == 1:
                uncertainty_parts.append("Only one agent assessed this zone")
            if caution_penalty > 0:
                uncertainty_parts.append(f"{len(region_cautions)} caution(s) in this region")

            evidence_summary = []
            for claim in region_claims[:3]:
                for ev in claim.evidence[:1]:
                    evidence_summary.append(f"[{claim.agent_name}] {ev.description}")

            geojson = None
            for claim in region_claims:
                if claim.spatial_scope and claim.spatial_scope.geojson:
                    geojson = claim.spatial_scope.geojson
                    break

            zones.append(
                RankedZone(
                    rank=0,  # Will be assigned after sorting
                    zone_type="trigger_zone",
                    title=f"Thermal Trigger: {region}",
                    description=region_claims[0].claim_text if region_claims else "",
                    confidence=final_confidence,
                    uncertainty_note="; ".join(uncertainty_parts) or "Multi-agent consensus",
                    evidence_summary=evidence_summary,
                    supporting_claims=region_claims,
                    feature_name=region,
                    geojson=geojson,
                )
            )

        # Sort and assign ranks
        zones.sort(key=lambda z: (-len(z.supporting_claims), -z.confidence))
        for i, zone in enumerate(zones, 1):
            zone.rank = i

        return zones

    def _rank_ridge_corridors(
        self,
        ridge_claims: list[Claim],
        sink_claims: list[Claim],
    ) -> list[RankedZone]:
        """Rank ridge lift claims, penalized by nearby sink zone claims."""
        if not ridge_claims:
            return []

        groups = self._group_by_region(ridge_claims)
        corridors = []

        for region, region_claims in groups.items():
            agg_confidence = self._weighted_confidence(region_claims)

            # Nearby sink zone on same feature reduces confidence
            region_sinks = [
                c for c in sink_claims
                if c.spatial_scope and region in (c.spatial_scope.feature_name or "")
            ]
            sink_penalty = min(0.30, len(region_sinks) * 0.15)
            final_confidence = max(0.05, agg_confidence - sink_penalty)

            uncertainty_parts = []
            if sink_penalty > 0:
                uncertainty_parts.append(
                    f"Lee-side sink zone also detected on {region} "
                    f"— ensure you're on windward face"
                )

            evidence_summary = []
            for claim in region_claims[:2]:
                for ev in claim.evidence[:1]:
                    evidence_summary.append(f"[{claim.agent_name}] {ev.description}")

            geojson = None
            for claim in region_claims:
                if claim.spatial_scope and claim.spatial_scope.geojson:
                    geojson = claim.spatial_scope.geojson
                    break

            corridors.append(
                RankedZone(
                    rank=0,
                    zone_type="ridge_corridor",
                    title=f"Ridge Corridor: {region}",
                    description=region_claims[0].claim_text if region_claims else "",
                    confidence=final_confidence,
                    uncertainty_note="; ".join(uncertainty_parts) or "Vector-based ridge analysis",
                    evidence_summary=evidence_summary,
                    supporting_claims=region_claims,
                    feature_name=region,
                    geojson=geojson,
                )
            )

        corridors.sort(key=lambda z: -z.confidence)
        for i, corridor in enumerate(corridors, 1):
            corridor.rank = i

        return corridors

    def _build_caution_zones(
        self,
        caution_claims: list[Claim],
        sink_claims: list[Claim],
    ) -> list[CautionZone]:
        """Convert caution claims into CautionZone objects."""
        all_cautions = caution_claims + sink_claims
        zones = []

        for claim in all_cautions:
            # Detect if it's a conflict-origin caution
            is_conflict = "AGENT DISAGREEMENT" in claim.claim_text

            zones.append(
                CautionZone(
                    title=claim.claim_text[:80] + "..." if len(claim.claim_text) > 80 else claim.claim_text,
                    description=claim.claim_text,
                    confidence=claim.confidence,
                    caution_type=claim.claim_type.value,
                    conflict_description=claim.claim_text if is_conflict else None,
                    feature_name=claim.spatial_scope.feature_name if claim.spatial_scope else None,
                    supporting_claims=[claim],
                )
            )

        # Sort by confidence descending (most certain cautions first)
        zones.sort(key=lambda z: -z.confidence)
        return zones

    def _build_evidence_traces(
        self,
        windows: list[RankedLaunchWindow],
        triggers: list[RankedZone],
        ridges: list[RankedZone],
        cautions: list[CautionZone],
    ) -> dict[str, list[str]]:
        """Build evidence trace map: recommendation title -> list of evidence descriptions."""
        traces: dict[str, list[str]] = {}

        for w in windows:
            key = f"launch_window_{w.rank}"
            traces[key] = w.evidence_summary + [
                f"{c.agent_name}: {e.description}"
                for c in w.supporting_claims
                for e in c.evidence
            ]

        for z in triggers:
            key = f"trigger_zone_{z.rank}_{z.feature_name}"
            traces[key] = z.evidence_summary

        for r in ridges:
            key = f"ridge_corridor_{r.rank}_{r.feature_name}"
            traces[key] = r.evidence_summary

        return traces

    def _compose_uncertainty_summary(
        self,
        all_claims: list[Claim],
        disagreements: list[AgentDisagreement],
        windows: list[RankedLaunchWindow],
        triggers: list[RankedZone],
    ) -> str:
        """Compose a human-readable uncertainty summary paragraph."""
        parts = []

        agent_names = list(set(c.agent_name for c in all_claims))
        parts.append(f"{len(agent_names)} agent(s) contributed {len(all_claims)} total claim(s).")

        if disagreements:
            parts.append(
                f"{len(disagreements)} agent disagreement(s) detected — "
                f"affected zones should be treated with extra caution."
            )

        if windows:
            best_window = windows[0]
            parts.append(
                f"Best launch window confidence: {best_window.confidence:.0%}. "
                f"Thermal index scoring is heuristic and not physically validated."
            )

        low_conf_zones = [z for z in triggers if z.confidence < 0.50]
        if low_conf_zones:
            parts.append(
                f"{len(low_conf_zones)} trigger zone(s) have confidence below 50% "
                f"and should not be relied upon without direct observation."
            )

        parts.append(
            "All recommendations are advisory only. "
            "Actual conditions can differ significantly from predictions."
        )

        return " ".join(parts)

    def _detect_disagreements(self, claims: list[Claim]) -> list[AgentDisagreement]:
        """Find inter-agent claim conflicts for reporting in NegotiationResult."""
        disagreements = []
        seen = set()

        CONFLICTING_TYPES = [
            (ClaimType.RIDGE_LIFT, ClaimType.SINK_ZONE),
            (ClaimType.RIDGE_LIFT, ClaimType.ROTOR_RISK),
            (ClaimType.THERMAL_ZONE, ClaimType.CAUTION),
        ]

        for i, ca in enumerate(claims):
            for j, cb in enumerate(claims):
                if i >= j:
                    continue
                if ca.agent_name == cb.agent_name:
                    continue

                conflict = any(
                    (ca.claim_type == a and cb.claim_type == b) or
                    (ca.claim_type == b and cb.claim_type == a)
                    for a, b in CONFLICTING_TYPES
                )
                if not conflict:
                    continue

                region_a = ca.spatial_scope.feature_name if ca.spatial_scope else "site-wide"
                region_b = cb.spatial_scope.feature_name if cb.spatial_scope else "site-wide"
                if region_a != region_b and region_a != "site-wide" and region_b != "site-wide":
                    continue

                key = frozenset([ca.id, cb.id])
                if key in seen:
                    continue
                seen.add(key)

                region = region_a if region_a != "site-wide" else region_b

                disagreements.append(
                    AgentDisagreement(
                        region=region or "site-wide",
                        agent_a=ca.agent_name,
                        agent_b=cb.agent_name,
                        claim_type_a=ca.claim_type.value,
                        claim_type_b=cb.claim_type.value,
                        confidence_a=ca.confidence,
                        confidence_b=cb.confidence,
                        description=(
                            f"{ca.agent_name} ({ca.claim_type.value}, conf={ca.confidence:.2f}) "
                            f"disagrees with {cb.agent_name} ({cb.claim_type.value}, conf={cb.confidence:.2f}) "
                            f"for region '{region}'"
                        ),
                    )
                )

        return disagreements
