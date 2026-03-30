"""
Agent execution routes for paraglide-backend.

Allows running individual agents by name and retrieving all claims
produced during a specific planning session.
"""

import json
from typing import Any

from fastapi import APIRouter, HTTPException
from loguru import logger
from pydantic import BaseModel
from sqlalchemy import select

from api.deps import DatabaseDep, SettingsDep, SiteProfileDep
from db.models import AgentClaim

router = APIRouter()

AVAILABLE_AGENTS = {
    "weather_agent",
    "terrain_agent",
    "cloud_agent",
    "local_knowledge_agent",
    "flight_history_agent",
    "risk_agent",
}


class AgentRunRequest(BaseModel):
    """Request body for running a specific agent."""
    agent_name: str
    inputs: dict[str, Any] = {}


@router.post("/run", summary="Run a specific agent by name")
async def run_agent(
    request: AgentRunRequest,
    settings: SettingsDep,
    profile: SiteProfileDep,
    db: DatabaseDep,
) -> dict[str, Any]:
    """
    Run a single named agent and return its claims.

    Useful for debugging individual agent behavior or exploring claim outputs
    without running the full planning pipeline.
    """
    if request.agent_name not in AVAILABLE_AGENTS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown agent '{request.agent_name}'. Available: {sorted(AVAILABLE_AGENTS)}",
        )

    logger.info(f"Running single agent: {request.agent_name}")
    context = {
        "site_profile": profile,
        "site_id": settings.site_id,
        **request.inputs,
    }

    claims = await _run_agent_by_name(request.agent_name, context, settings, db)

    return {
        "agent_name": request.agent_name,
        "claim_count": len(claims),
        "claims": [
            {
                "id": c.id,
                "claim_type": c.claim_type.value if hasattr(c.claim_type, "value") else str(c.claim_type),
                "claim_text": c.claim_text,
                "confidence": c.confidence,
                "evidence": [{"source": e.source, "description": e.description} for e in c.evidence],
                "assumptions": c.assumptions,
                "spatial_scope": {
                    "feature_name": c.spatial_scope.feature_name,
                } if c.spatial_scope else None,
                "temporal_validity": {
                    "valid_from_hour": c.temporal_validity.valid_from_hour,
                    "valid_to_hour": c.temporal_validity.valid_to_hour,
                    "seasonal_constraint": c.temporal_validity.seasonal_constraint,
                } if c.temporal_validity else None,
            }
            for c in claims
        ],
    }


@router.get("/claims/{session_id}", summary="Get all agent claims for a session")
async def get_claims_for_session(
    session_id: int,
    db: DatabaseDep,
) -> list[dict[str, Any]]:
    """
    Return all agent claims produced during a specific planning session.

    Claims are ordered by agent name and confidence (descending).
    """
    result = await db.execute(
        select(AgentClaim)
        .where(AgentClaim.session_id == session_id)
        .order_by(AgentClaim.agent_name, AgentClaim.confidence.desc())
    )
    claims = result.scalars().all()

    if not claims:
        raise HTTPException(
            status_code=404,
            detail=f"No claims found for session {session_id}",
        )

    return [
        {
            "id": c.id,
            "agent_name": c.agent_name,
            "claim_type": c.claim_type,
            "claim_text": c.claim_text,
            "confidence": c.confidence,
            "evidence": json.loads(c.evidence_json) if c.evidence_json else [],
            "assumptions": json.loads(c.assumptions_json) if c.assumptions_json else [],
            "spatial_scope": json.loads(c.spatial_scope_json) if c.spatial_scope_json else None,
            "temporal_validity": json.loads(c.temporal_validity_json) if c.temporal_validity_json else None,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }
        for c in claims
    ]


async def _run_agent_by_name(
    agent_name: str,
    context: dict[str, Any],
    settings: Any,
    db: Any,
) -> list:
    """Instantiate and run an agent by name, returning its claims."""
    if agent_name == "weather_agent":
        from agents.weather_agent import WeatherAgent
        from data_ingestion.weather.mock_provider import MockWeatherProvider
        provider = MockWeatherProvider()
        lat = context["site_profile"]["location"]["lat"]
        lon = context["site_profile"]["location"]["lon"]
        forecast = await provider.fetch_forecast(lat, lon)
        context["forecast"] = forecast
        return await WeatherAgent().run(context)

    elif agent_name == "terrain_agent":
        from agents.terrain_agent import TerrainAgent
        return await TerrainAgent().run(context)

    elif agent_name == "cloud_agent":
        from agents.cloud_agent import CloudAgent
        from data_ingestion.clouds.mock_cloud_provider import MockCloudProvider
        provider = MockCloudProvider()
        lat = context["site_profile"]["location"]["lat"]
        lon = context["site_profile"]["location"]["lon"]
        obs = await provider.fetch_observation(lat, lon)
        context["cloud_observation"] = obs
        return await CloudAgent().run(context)

    elif agent_name == "local_knowledge_agent":
        from agents.local_knowledge_agent import LocalKnowledgeAgent
        return await LocalKnowledgeAgent().run(context)

    elif agent_name == "flight_history_agent":
        from agents.flight_history_agent import FlightHistoryAgent
        context.setdefault("flight_segments", [])
        return await FlightHistoryAgent().run(context)

    elif agent_name == "risk_agent":
        from agents.risk_agent import RiskAgent
        context.setdefault("prior_claims", [])
        return await RiskAgent().run(context)

    return []
