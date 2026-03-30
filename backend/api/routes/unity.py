"""
Unity 3D overlay routes for paraglide-backend.

Returns structured overlay payloads for consumption by a Unity scene.
Payloads include thermal zones, ridge corridors, caution zones, climb hotspots,
and per-agent claim layers with full confidence and evidence information.
"""

from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, HTTPException
from loguru import logger
from pydantic import BaseModel
from sqlalchemy import select

from api.deps import DatabaseDep, SettingsDep, SiteProfileDep

router = APIRouter()

ADVISORY_DISCLAIMER = (
    "This output is advisory only. Not a safety system. "
    "All zones and recommendations are estimates based on incomplete data. "
    "Do not rely on this for flight decisions."
)


class ThermalZone(BaseModel):
    id: str
    name: str
    confidence: float
    uncertainty: float
    evidence_count: int
    evidence_sources: list[str]
    polygon_geojson: dict | None = None
    elevation_center_m: float | None = None
    valid_hours: list[int]
    agent_sources: list[str]
    notes: str
    render_hints: dict


class RidgeCorridor(BaseModel):
    id: str
    name: str
    confidence: float
    uncertainty: float
    evidence_count: int
    line_geojson: dict | None = None
    elevation_m: float | None = None
    valid_hours: list[int]
    agent_sources: list[str]
    notes: str
    render_hints: dict


class CautionZone(BaseModel):
    id: str
    name: str
    caution_type: str
    confidence: float
    polygon_geojson: dict | None = None
    description: str
    conflict_description: str | None = None
    render_hints: dict


class RecommendationOverlay(BaseModel):
    rank: int
    type: str
    title: str
    description: str
    confidence: float
    uncertainty_note: str | None = None
    evidence_summary: list[str]


class UnityOverlayPayload(BaseModel):
    site_id: str
    generated_at: str
    coordinate_system: str
    time_range: dict
    terrain: dict
    thermal_zones: list[ThermalZone]
    ridge_corridors: list[RidgeCorridor]
    caution_zones: list[CautionZone]
    climb_hotspots: list[dict]
    recommendations: list[RecommendationOverlay]
    agent_layers: dict
    uncertainty_summary: str
    advisory_disclaimer: str


@router.get("/overlays", summary="Return Unity overlay payload for current site state", response_model=None)
async def get_overlays(
    settings: SettingsDep,
    profile: SiteProfileDep,
    db: DatabaseDep,
) -> dict[str, Any]:
    """
    Return the current site overlay payload for Unity visualization.

    Runs a planning session with mock data if no recent session is available,
    then builds the full overlay payload.
    """
    from spatial.overlay_builder import UnityOverlayBuilder

    # Try to get the most recent completed session
    from db.models import NegotiationSession
    result = await db.execute(
        select(NegotiationSession)
        .where(NegotiationSession.status == "complete")
        .order_by(NegotiationSession.requested_at.desc())
        .limit(1)
    )
    session = result.scalar_one_or_none()

    builder = UnityOverlayBuilder(site_profile=profile)

    if session:
        import json
        from db.models import AgentClaim, Recommendation
        claims_result = await db.execute(
            select(AgentClaim).where(AgentClaim.session_id == session.id)
        )
        claims = claims_result.scalars().all()

        recs_result = await db.execute(
            select(Recommendation).where(Recommendation.session_id == session.id)
            .order_by(Recommendation.rank)
        )
        recommendations = recs_result.scalars().all()

        payload = builder.build_from_db_session(session, claims, recommendations)
    else:
        # Build a basic overlay from site profile alone (no session)
        payload = builder.build_static_overlay()

    logger.info(f"Serving Unity overlay payload for site={settings.site_id}")
    return payload


@router.get("/overlays/{session_id}", summary="Return overlay payload for a specific planning session", response_model=None)
async def get_overlays_for_session(
    session_id: int,
    settings: SettingsDep,
    profile: SiteProfileDep,
    db: DatabaseDep,
) -> dict[str, Any]:
    """
    Return the Unity overlay payload for a specific planning session.
    """
    from db.models import AgentClaim, NegotiationSession, Recommendation
    import json

    session_result = await db.execute(
        select(NegotiationSession).where(NegotiationSession.id == session_id)
    )
    session = session_result.scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    claims_result = await db.execute(
        select(AgentClaim).where(AgentClaim.session_id == session_id)
    )
    claims = claims_result.scalars().all()

    recs_result = await db.execute(
        select(Recommendation).where(Recommendation.session_id == session_id)
        .order_by(Recommendation.rank)
    )
    recommendations = recs_result.scalars().all()

    from spatial.overlay_builder import UnityOverlayBuilder
    builder = UnityOverlayBuilder(site_profile=profile)
    payload = builder.build_from_db_session(session, claims, recommendations)

    logger.info(f"Serving Unity overlay for session_id={session_id}")
    return payload
