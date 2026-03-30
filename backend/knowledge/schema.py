"""
Pydantic models for knowledge management in paraglide-backend.

Defines request/response schemas for KnowledgeItems, ExpertInterviews,
and structured HeuristicRules extracted from interview transcripts.
"""

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field


class ConditionBlock(BaseModel):
    """Conditions under which a heuristic applies."""
    wind_dir_deg_range: list[float] | None = None       # [min, max] degrees
    wind_speed_kmh_range: list[float] | None = None     # [min, max] km/h
    wind_speed_kmh_min: float | None = None
    wind_speed_kmh_max: float | None = None
    time_local: str | None = None                        # e.g. "10:00-14:00"
    season: str | list[str] | None = None               # "summer" or ["summer", "fall"]
    sky: str | None = None                               # "clear", "partly_cloudy", etc.
    temp_c_min: float | None = None
    cloud_type: str | None = None
    cloud_base_m_range: list[float] | None = None


class HeuristicRule(BaseModel):
    """
    A structured heuristic rule parsed from expert text.

    Represents an if-then rule about site conditions and expected behavior.
    """
    statement: str
    condition: ConditionBlock | None = None
    exception: str | None = None
    risk_note: str | None = None
    sub_region: str | None = None
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    source: str | None = None


class ConditionActionHeuristic(BaseModel):
    """
    A fuller representation linking conditions to actions/observations.

    Used for structured heuristics extracted from expert interviews.
    """
    condition: str           # When/if description
    action: str              # Recommended action or expected behavior
    exceptions: list[str] = Field(default_factory=list)
    risk_note: str | None = None
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    provenance: dict[str, Any] = Field(default_factory=dict)


class KnowledgeItemCreate(BaseModel):
    """Request body for creating a new knowledge item."""
    site_id: str
    sub_region: str | None = None
    wind_condition: str | None = None
    time_of_day: str | None = None
    season: str | None = None
    cloud_condition: str | None = None
    statement: str
    exception_statement: str | None = None
    risk_note: str | None = None
    source_expert: str | None = None
    source_date: date | None = None
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class KnowledgeItemRead(KnowledgeItemCreate):
    """Response schema for a knowledge item including DB-assigned fields."""
    id: int
    created_at: datetime

    model_config = {"from_attributes": True}


class ExpertInterviewCreate(BaseModel):
    """Request body for importing an expert interview."""
    site_id: str
    expert_name: str
    interview_date: date | None = None
    raw_transcript: str
    notes: str | None = None


class ExpertInterviewRead(ExpertInterviewCreate):
    """Response schema for an expert interview."""
    id: int
    processed_at: datetime | None = None
    extracted_heuristic_count: int = 0

    model_config = {"from_attributes": True}
