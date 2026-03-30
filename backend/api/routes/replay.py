"""
Historical replay routes for paraglide-backend.

Supports creating and retrieving replay sessions that combine a historical
flight track with weather snapshots and agent annotations for post-flight analysis.
"""

import json
from typing import Any

from fastapi import APIRouter, HTTPException
from loguru import logger
from pydantic import BaseModel
from sqlalchemy import select

from api.deps import DatabaseDep, SettingsDep

router = APIRouter()


class ReplayCreateRequest(BaseModel):
    """Request body for creating a replay session."""
    track_id: int
    weather_snapshot_id: int | None = None
    notes: str | None = None


@router.get("/{session_id}", summary="Return replay data for a session")
async def get_replay(
    session_id: int,
    db: DatabaseDep,
) -> dict[str, Any]:
    """
    Return replay data for a completed planning session.

    Includes: track GeoJSON with timestamps, agent claims indexed by time,
    and recommendations overlaid on the flight path.
    """
    from db.models import AgentClaim, FlightSegment, HistoricalFlightTrack, NegotiationSession, Recommendation

    session_result = await db.execute(
        select(NegotiationSession).where(NegotiationSession.id == session_id)
    )
    session = session_result.scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    # Load claims
    claims_result = await db.execute(
        select(AgentClaim).where(AgentClaim.session_id == session_id)
    )
    claims = claims_result.scalars().all()

    # Load recommendations
    rec_result = await db.execute(
        select(Recommendation).where(Recommendation.session_id == session_id)
        .order_by(Recommendation.rank)
    )
    recommendations = rec_result.scalars().all()

    outputs = json.loads(session.outputs_json) if session.outputs_json else {}
    track_id = outputs.get("track_id")

    track_data = None
    if track_id:
        track_result = await db.execute(
            select(HistoricalFlightTrack).where(HistoricalFlightTrack.id == track_id)
        )
        track = track_result.scalar_one_or_none()
        if track:
            track_data = {
                "id": track.id,
                "pilot_name": track.pilot_name,
                "flight_date": track.flight_date.isoformat() if track.flight_date else None,
                "track_geojson": json.loads(track.track_geojson) if track.track_geojson else None,
            }

    return {
        "session_id": session_id,
        "status": session.status,
        "requested_at": session.requested_at.isoformat() if session.requested_at else None,
        "track": track_data,
        "claims": [
            {
                "agent_name": c.agent_name,
                "claim_type": c.claim_type,
                "claim_text": c.claim_text,
                "confidence": c.confidence,
                "spatial_scope": json.loads(c.spatial_scope_json) if c.spatial_scope_json else None,
                "temporal_validity": json.loads(c.temporal_validity_json) if c.temporal_validity_json else None,
            }
            for c in claims
        ],
        "recommendations": [
            {
                "rank": r.rank,
                "type": r.rec_type,
                "title": r.title,
                "description": r.description,
                "confidence": r.confidence,
                "uncertainty_note": r.uncertainty_note,
                "valid_from": r.valid_from.isoformat() if r.valid_from else None,
                "valid_until": r.valid_until.isoformat() if r.valid_until else None,
            }
            for r in recommendations
        ],
    }


@router.post("/create", summary="Create a replay session from a historical flight", status_code=201)
async def create_replay_session(
    request: ReplayCreateRequest,
    settings: SettingsDep,
    db: DatabaseDep,
) -> dict[str, Any]:
    """
    Create a replay session linking a historical flight track to a weather snapshot.

    This enables post-flight analysis: comparing agent predictions against
    what actually happened in the recorded flight.
    """
    from services.replay_service import ReplayService

    service = ReplayService()
    session = await service.create_replay_session(
        track_id=request.track_id,
        db=db,
        weather_snapshot_id=request.weather_snapshot_id,
    )

    logger.info(f"Replay session created: {session}")

    return {
        "session_id": session.get("session_id"),
        "track_id": request.track_id,
        "status": "created",
        "message": "Replay session ready. Use GET /replay/{session_id} to retrieve data.",
    }
