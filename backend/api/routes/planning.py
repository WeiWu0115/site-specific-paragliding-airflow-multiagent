"""
Planning session routes for paraglide-backend.

Runs the full multi-agent planning pipeline and returns recommendations
with full provenance and uncertainty information.
"""

from datetime import date, datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from loguru import logger
from pydantic import BaseModel
from sqlalchemy import select

from api.deps import DatabaseDep, SettingsDep
from db.models import NegotiationSession

router = APIRouter()


class PlanningRequest(BaseModel):
    """Request body for a planning session."""
    site_id: str
    target_date: date | None = None
    target_time_utc: str | None = None  # e.g. "11:00"


@router.post("", summary="Run full planning pipeline and return recommendations")
async def run_planning(
    request: PlanningRequest,
    settings: SettingsDep,
    db: DatabaseDep,
) -> dict[str, Any]:
    """
    Execute the full multi-agent planning pipeline:

    1. Load site profile
    2. Fetch weather forecast
    3. Fetch cloud observation
    4. Load terrain features
    5. Load matching knowledge items
    6. Load recent flight history
    7. Run all agents (weather, terrain, cloud, local_knowledge, flight_history)
    8. Run RiskAgent on all claims
    9. Run NegotiationAgent — produce ranked recommendations
    10. Store session + claims + recommendations in DB
    11. Return NegotiationResult with full evidence traces

    All recommendations are advisory only.
    """
    logger.info(f"Planning session requested for site={request.site_id} date={request.target_date}")

    from services.planning_service import PlanningService

    service = PlanningService()
    result = await service.run_planning_session(
        site_id=request.site_id or settings.site_id,
        target_date=request.target_date or date.today(),
        db=db,
    )

    return {
        "session_id": result.session_id,
        "site_id": request.site_id or settings.site_id,
        "generated_at": datetime.utcnow().isoformat(),
        "status": "complete",
        "launch_windows": result.ranked_launch_windows,
        "trigger_zones": result.ranked_trigger_zones,
        "ridge_corridors": result.ranked_ridge_corridors,
        "caution_zones": result.caution_zones,
        "evidence_traces": result.evidence_traces,
        "uncertainty_summary": result.uncertainty_summary,
        "agent_disagreements": result.agent_disagreements,
        "advisory_disclaimer": (
            "All recommendations are advisory only. Not a safety instrument. "
            "Do not rely on this output for flight decisions."
        ),
    }


@router.get("/{session_id}", summary="Get a previous planning session result")
async def get_planning_session(
    session_id: int,
    db: DatabaseDep,
) -> dict[str, Any]:
    """
    Retrieve a previously completed planning session by its ID.

    Returns session status, inputs, and outputs including all recommendations.
    """
    result = await db.execute(
        select(NegotiationSession).where(NegotiationSession.id == session_id)
    )
    session = result.scalar_one_or_none()

    if session is None:
        raise HTTPException(status_code=404, detail=f"Planning session {session_id} not found")

    import json
    return {
        "session_id": session.id,
        "site_id": session.site_id,
        "requested_at": session.requested_at.isoformat() if session.requested_at else None,
        "status": session.status,
        "inputs": json.loads(session.inputs_json) if session.inputs_json else {},
        "outputs": json.loads(session.outputs_json) if session.outputs_json else {},
    }
