"""
Base data structures and abstract base class for all planning agents.

All agents produce typed Claim objects with evidence, confidence scores,
spatial scope, and temporal validity constraints. The NegotiationAgent
aggregates claims from all agents to produce ranked recommendations.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class ClaimType(str, Enum):
    """Enumeration of all valid claim types an agent can produce."""
    THERMAL_ZONE = "thermal_zone"
    RIDGE_LIFT = "ridge_lift"
    SINK_ZONE = "sink_zone"
    CAUTION = "caution"
    LAUNCH_WINDOW = "launch_window"
    ROTOR_RISK = "rotor_risk"


class ConfidenceLevel(str, Enum):
    """Categorical confidence bands for human-readable reporting."""
    HIGH = "high"       # > 0.75
    MEDIUM = "medium"   # 0.45 - 0.75
    LOW = "low"         # < 0.45
    UNKNOWN = "unknown"


@dataclass
class Evidence:
    """
    A single piece of evidence supporting a claim.

    source: machine-readable identifier, e.g. "open_meteo_forecast", "pilot_interview_2024"
    description: human-readable explanation of what this evidence shows
    data_ref: structured data snippet (forecast hour dict, heuristic id, etc.)
    """
    source: str
    description: str
    data_ref: dict[str, Any] = field(default_factory=dict)


@dataclass
class SpatialScope:
    """
    Describes the geographic area to which a claim applies.

    feature_name: name of a named terrain feature (e.g. "South Bowl")
    geojson: GeoJSON dict for the polygon/line/point if available
    elevation_range_m: (min, max) altitude range in meters
    """
    feature_name: str | None = None
    geojson: dict | None = None
    elevation_range_m: tuple[float, float] | None = None


@dataclass
class TemporalValidity:
    """
    Describes the time window during which a claim is expected to hold.

    valid_from_hour: local hour of day when condition typically begins (e.g. 10)
    valid_to_hour: local hour of day when condition typically ends (e.g. 15)
    seasonal_constraint: "summer", "spring", "fall", "winter", or None for year-round
    notes: any additional temporal caveats
    """
    valid_from_hour: int | None = None
    valid_to_hour: int | None = None
    seasonal_constraint: str | None = None
    notes: str = ""


@dataclass
class Claim:
    """
    A typed, evidence-backed assertion produced by one agent.

    Each claim has:
    - A unique ID for tracing through the negotiation pipeline
    - The name of the producing agent
    - A claim type from ClaimType enum
    - A free-text description
    - A list of Evidence objects
    - A confidence score 0.0–1.0
    - A list of assumptions the agent made
    - Spatial and temporal scope constraints
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    agent_name: str = ""
    claim_type: ClaimType = ClaimType.THERMAL_ZONE
    claim_text: str = ""
    evidence: list[Evidence] = field(default_factory=list)
    confidence: float = 0.5
    assumptions: list[str] = field(default_factory=list)
    spatial_scope: SpatialScope = field(default_factory=SpatialScope)
    temporal_validity: TemporalValidity = field(default_factory=TemporalValidity)
    created_at: datetime = field(default_factory=datetime.utcnow)

    def confidence_level(self) -> ConfidenceLevel:
        """Return the categorical confidence band for this claim."""
        return _confidence_to_level(self.confidence)

    def to_dict(self) -> dict[str, Any]:
        """Serialize claim to a JSON-compatible dict."""
        return {
            "id": self.id,
            "agent_name": self.agent_name,
            "claim_type": self.claim_type.value,
            "claim_text": self.claim_text,
            "confidence": self.confidence,
            "confidence_level": self.confidence_level().value,
            "evidence": [
                {"source": e.source, "description": e.description, "data_ref": e.data_ref}
                for e in self.evidence
            ],
            "assumptions": self.assumptions,
            "spatial_scope": {
                "feature_name": self.spatial_scope.feature_name,
                "elevation_range_m": list(self.spatial_scope.elevation_range_m) if self.spatial_scope.elevation_range_m else None,
            },
            "temporal_validity": {
                "valid_from_hour": self.temporal_validity.valid_from_hour,
                "valid_to_hour": self.temporal_validity.valid_to_hour,
                "seasonal_constraint": self.temporal_validity.seasonal_constraint,
                "notes": self.temporal_validity.notes,
            },
            "created_at": self.created_at.isoformat(),
        }


def _confidence_to_level(score: float) -> ConfidenceLevel:
    """Map a raw confidence score to a categorical ConfidenceLevel."""
    if score > 0.75:
        return ConfidenceLevel.HIGH
    if score >= 0.45:
        return ConfidenceLevel.MEDIUM
    if score >= 0.0:
        return ConfidenceLevel.LOW
    return ConfidenceLevel.UNKNOWN


class AgentBase:
    """
    Abstract base class for all planning agents.

    Subclasses must implement run() to produce a list of Claim objects.
    Agents should be stateless: all inputs come through the context dict.
    """
    name: str = "base_agent"

    async def run(self, context: dict[str, Any]) -> list[Claim]:
        """
        Execute the agent with the provided context dict.

        Expected context keys vary by agent type. Each agent documents
        its expected inputs in its docstring.

        Returns a list of Claim objects. An empty list is valid (no claims
        to make) and is not an error.
        """
        raise NotImplementedError(f"{self.__class__.__name__} must implement run()")

    def _confidence_level(self, score: float) -> ConfidenceLevel:
        """Utility method for subclasses."""
        return _confidence_to_level(score)

    def _make_claim(
        self,
        claim_type: ClaimType,
        claim_text: str,
        confidence: float,
        evidence: list[Evidence] | None = None,
        assumptions: list[str] | None = None,
        spatial_scope: SpatialScope | None = None,
        temporal_validity: TemporalValidity | None = None,
    ) -> Claim:
        """Convenience factory for creating a Claim with this agent's name."""
        return Claim(
            agent_name=self.name,
            claim_type=claim_type,
            claim_text=claim_text,
            confidence=max(0.0, min(1.0, confidence)),
            evidence=evidence or [],
            assumptions=assumptions or [],
            spatial_scope=spatial_scope or SpatialScope(),
            temporal_validity=temporal_validity or TemporalValidity(),
        )
