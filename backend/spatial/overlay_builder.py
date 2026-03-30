"""
Unity overlay builder for paraglide-backend.

Converts NegotiationResult and DB session data into the UnityOverlayPayload
format consumed by the Unity 3D visualization client.
"""

import json
from datetime import datetime, timedelta, timezone
from typing import Any

from loguru import logger

ADVISORY_DISCLAIMER = (
    "This output is advisory only. Not a safety system. "
    "All zones and recommendations are estimates based on incomplete data. "
    "Do not rely on this for flight decisions."
)

# Confidence → render color mapping
def _confidence_to_color(confidence: float) -> str:
    """Map confidence level to hex color for Unity rendering hints."""
    if confidence >= 0.75:
        return "#00AA44"  # Green — high confidence
    elif confidence >= 0.50:
        return "#FFAA00"  # Amber — medium confidence
    elif confidence >= 0.30:
        return "#FF6600"  # Orange — low-medium
    else:
        return "#CC2200"  # Red — low/uncertain


def _confidence_to_opacity(confidence: float) -> float:
    """Map confidence to opacity for Unity material (0.2–0.85)."""
    return round(0.2 + 0.65 * confidence, 2)


class UnityOverlayBuilder:
    """
    Builds the full UnityOverlayPayload from planning session data.

    The payload is consumed by the Unity C# client to render:
    - Thermal zone volumes (semi-transparent rising volumes)
    - Ridge corridors (arrow flows)
    - Caution zones (red/orange volumes)
    - Climb hotspots (point clouds from history)
    - Recommendations (floating annotation cards)
    - Per-agent claim layers (toggleable in Unity)
    """

    def __init__(self, site_profile: dict[str, Any]) -> None:
        self.site_profile = site_profile

    def build_from_db_session(
        self,
        session: Any,
        claims: list[Any],
        recommendations: list[Any],
    ) -> dict[str, Any]:
        """
        Build overlay payload from DB session, claims, and recommendations.

        Args:
            session: NegotiationSession ORM object
            claims: List of AgentClaim ORM objects
            recommendations: List of Recommendation ORM objects (sorted by rank)

        Returns:
            Full UnityOverlayPayload dict
        """
        now = datetime.now(tz=timezone.utc)
        site_id = self.site_profile.get("id", "unknown")

        # Group claims by agent
        agent_layers = self._build_agent_layers(claims)

        # Build zone types from claims
        thermal_zones = self._build_thermal_zones_from_claims(claims)
        ridge_corridors = self._build_ridge_corridors_from_claims(claims)
        caution_zones = self._build_caution_zones_from_claims(claims)
        climb_hotspots = self._build_climb_hotspots_from_claims(claims)

        # Build recommendations
        rec_overlays = self._build_recommendation_overlays(recommendations)

        # Time range (next 12 hours)
        time_from = now
        time_to = now + timedelta(hours=12)

        outputs = {}
        if session.outputs_json:
            try:
                outputs = json.loads(session.outputs_json)
            except json.JSONDecodeError:
                pass

        return {
            "site_id": site_id,
            "session_id": session.id,
            "generated_at": now.isoformat(),
            "coordinate_system": "WGS84",
            "time_range": {
                "from": time_from.isoformat(),
                "to": time_to.isoformat(),
            },
            "terrain": self._build_terrain_section(),
            "thermal_zones": thermal_zones,
            "ridge_corridors": ridge_corridors,
            "caution_zones": caution_zones,
            "climb_hotspots": climb_hotspots,
            "recommendations": rec_overlays,
            "agent_layers": agent_layers,
            "uncertainty_summary": outputs.get("uncertainty_summary", ""),
            "advisory_disclaimer": ADVISORY_DISCLAIMER,
        }

    def build_static_overlay(self) -> dict[str, Any]:
        """
        Build a basic overlay from site profile alone (no planning session).

        Returns terrain data and static site features without agent claims.
        """
        now = datetime.now(tz=timezone.utc)
        site_id = self.site_profile.get("id", "unknown")

        return {
            "site_id": site_id,
            "session_id": None,
            "generated_at": now.isoformat(),
            "coordinate_system": "WGS84",
            "time_range": {
                "from": now.isoformat(),
                "to": (now + timedelta(hours=12)).isoformat(),
            },
            "terrain": self._build_terrain_section(),
            "thermal_zones": [],
            "ridge_corridors": [],
            "caution_zones": [],
            "climb_hotspots": [],
            "recommendations": [],
            "agent_layers": {},
            "uncertainty_summary": "No planning session available. Run POST /planning to generate recommendations.",
            "advisory_disclaimer": ADVISORY_DISCLAIMER,
        }

    def _build_terrain_section(self) -> dict[str, Any]:
        """Build the terrain section with launches, landings, and features."""
        return {
            "launches": self.site_profile.get("launches", []),
            "landings": self.site_profile.get("landings", []),
            "features": self.site_profile.get("terrain_features", []),
            "terrain_mesh_url": None,  # Phase 4: Unity terrain import
        }

    def _build_thermal_zones_from_claims(
        self,
        claims: list[Any],
    ) -> list[dict[str, Any]]:
        """Convert THERMAL_ZONE claims to Unity thermal zone objects."""
        zones = []
        thermal_claims = [
            c for c in claims
            if getattr(c, "claim_type", "") == "thermal_zone"
            or c.claim_type == "thermal_zone"
        ]

        for i, claim in enumerate(thermal_claims):
            spatial = json.loads(claim.spatial_scope_json) if claim.spatial_scope_json else {}
            temporal = json.loads(claim.temporal_validity_json) if claim.temporal_validity_json else {}
            evidence = json.loads(claim.evidence_json) if claim.evidence_json else []

            valid_hours = []
            if temporal.get("valid_from_hour") and temporal.get("valid_to_hour"):
                valid_hours = list(range(
                    temporal["valid_from_hour"],
                    temporal["valid_to_hour"] + 1
                ))

            zones.append({
                "id": f"tz_{claim.id}_{i:03d}",
                "name": spatial.get("feature_name", f"Thermal Zone {i+1}"),
                "confidence": claim.confidence,
                "uncertainty": round(1.0 - claim.confidence, 2),
                "evidence_count": len(evidence),
                "evidence_sources": [e.get("source", "") for e in evidence[:3]],
                "polygon_geojson": spatial.get("geojson"),
                "elevation_center_m": None,
                "valid_hours": valid_hours,
                "agent_sources": [claim.agent_name],
                "notes": claim.claim_text[:200] if claim.claim_text else "",
                "render_hints": {
                    "color": _confidence_to_color(claim.confidence),
                    "opacity": _confidence_to_opacity(claim.confidence),
                    "particle_density": "high" if claim.confidence > 0.70 else "medium",
                },
            })

        return zones

    def _build_ridge_corridors_from_claims(
        self,
        claims: list[Any],
    ) -> list[dict[str, Any]]:
        """Convert RIDGE_LIFT claims to Unity ridge corridor objects."""
        corridors = []
        ridge_claims = [
            c for c in claims
            if getattr(c, "claim_type", "") in ("ridge_lift",)
            or c.claim_type == "ridge_lift"
        ]

        for i, claim in enumerate(ridge_claims):
            spatial = json.loads(claim.spatial_scope_json) if claim.spatial_scope_json else {}
            corridors.append({
                "id": f"rc_{claim.id}_{i:03d}",
                "name": spatial.get("feature_name", f"Ridge Corridor {i+1}"),
                "confidence": claim.confidence,
                "uncertainty": round(1.0 - claim.confidence, 2),
                "evidence_count": 1,
                "line_geojson": spatial.get("geojson"),
                "elevation_m": None,
                "valid_hours": [],
                "agent_sources": [claim.agent_name],
                "notes": claim.claim_text[:200] if claim.claim_text else "",
                "render_hints": {
                    "color": _confidence_to_color(claim.confidence),
                    "opacity": _confidence_to_opacity(claim.confidence),
                    "arrow_density": "high" if claim.confidence > 0.70 else "low",
                },
            })

        return corridors

    def _build_caution_zones_from_claims(
        self,
        claims: list[Any],
    ) -> list[dict[str, Any]]:
        """Convert CAUTION/ROTOR_RISK/SINK_ZONE claims to Unity caution zone objects."""
        caution_type_set = {"caution", "rotor_risk", "sink_zone"}
        caution_claims = [
            c for c in claims
            if (getattr(c, "claim_type", "") in caution_type_set
                or c.claim_type in caution_type_set)
        ]

        zones = []
        for i, claim in enumerate(caution_claims):
            spatial = json.loads(claim.spatial_scope_json) if claim.spatial_scope_json else {}
            zones.append({
                "id": f"cz_{claim.id}_{i:03d}",
                "name": spatial.get("feature_name", f"Caution Zone {i+1}"),
                "caution_type": claim.claim_type,
                "confidence": claim.confidence,
                "polygon_geojson": spatial.get("geojson"),
                "description": claim.claim_text[:200] if claim.claim_text else "",
                "conflict_description": (
                    claim.claim_text if "DISAGREEMENT" in (claim.claim_text or "") else None
                ),
                "render_hints": {
                    "color": "#CC2200",
                    "opacity": _confidence_to_opacity(claim.confidence),
                    "hazard_marker": True,
                },
            })

        return zones

    def _build_climb_hotspots_from_claims(
        self,
        claims: list[Any],
    ) -> list[dict[str, Any]]:
        """Extract historical climb hotspot data from flight_history_agent claims."""
        hotspot_claims = [
            c for c in claims
            if getattr(c, "agent_name", "") == "flight_history_agent"
        ]

        hotspots = []
        for claim in hotspot_claims:
            spatial = json.loads(claim.spatial_scope_json) if claim.spatial_scope_json else {}
            evidence = json.loads(claim.evidence_json) if claim.evidence_json else []
            flight_count = 0
            avg_vario = 0.0
            for ev in evidence:
                data = ev.get("data_ref", {})
                flight_count = data.get("flight_count", 0)
                avg_vario = data.get("avg_vario_ms", 0.0)

            hotspots.append({
                "id": f"ch_{claim.id}",
                "polygon_geojson": spatial.get("geojson"),
                "flight_count": flight_count,
                "avg_vario_ms": avg_vario,
                "confidence": claim.confidence,
                "notes": claim.claim_text[:200] if claim.claim_text else "",
                "render_hints": {
                    "color": "#0066FF",
                    "opacity": 0.4,
                    "point_cloud": True,
                },
            })

        return hotspots

    def _build_recommendation_overlays(
        self,
        recommendations: list[Any],
    ) -> list[dict[str, Any]]:
        """Convert DB Recommendation objects to Unity overlay dicts."""
        overlays = []
        for rec in recommendations:
            evidence_summary = []
            if rec.evidence_summary_json:
                try:
                    evidence_summary = json.loads(rec.evidence_summary_json)
                    if isinstance(evidence_summary, str):
                        evidence_summary = [evidence_summary]
                except json.JSONDecodeError:
                    evidence_summary = [rec.evidence_summary_json]

            overlays.append({
                "rank": rec.rank,
                "type": rec.rec_type,
                "title": rec.title,
                "description": rec.description or "",
                "confidence": rec.confidence,
                "uncertainty_note": rec.uncertainty_note or "",
                "evidence_summary": evidence_summary,
                "spatial_ref": json.loads(rec.spatial_ref_json) if rec.spatial_ref_json else None,
                "valid_from": rec.valid_from.isoformat() if rec.valid_from else None,
                "valid_until": rec.valid_until.isoformat() if rec.valid_until else None,
            })

        return overlays

    def _build_agent_layers(
        self,
        claims: list[Any],
    ) -> dict[str, dict[str, Any]]:
        """Build per-agent layer data for Unity layer toggles."""
        agent_claims: dict[str, list[Any]] = {}
        for claim in claims:
            name = getattr(claim, "agent_name", "unknown")
            if name not in agent_claims:
                agent_claims[name] = []
            agent_claims[name].append(claim)

        layers = {}
        for agent_name, agent_claim_list in agent_claims.items():
            layers[agent_name] = {
                "active": True,
                "claim_count": len(agent_claim_list),
                "claims": [
                    {
                        "claim_type": c.claim_type,
                        "claim_text": (c.claim_text or "")[:100],
                        "confidence": c.confidence,
                    }
                    for c in agent_claim_list[:10]  # Limit to 10 for payload size
                ],
            }

        return layers
