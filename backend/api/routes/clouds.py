"""
Cloud observation routes for paraglide-backend.

Returns current cloud observations and recent history from the database.
"""

import json
from typing import Any

from fastapi import APIRouter
from loguru import logger
from sqlalchemy import select, desc

from api.deps import DatabaseDep, SettingsDep, SiteProfileDep
from db.models import CloudObservation

router = APIRouter()


@router.get("", summary="Return current cloud observation")
async def get_clouds(
    settings: SettingsDep,
    profile: SiteProfileDep,
) -> dict[str, Any]:
    """
    Fetch a current cloud observation using the configured cloud provider.

    With CLOUD_PROVIDER=mock, returns synthetic midday cloud data.
    """
    if settings.is_mock_cloud:
        from data_ingestion.clouds.mock_cloud_provider import MockCloudProvider
        provider = MockCloudProvider()
    else:
        raise NotImplementedError("Only mock cloud provider is implemented in Phase 1")

    lat = profile["location"]["lat"]
    lon = profile["location"]["lon"]
    observation = await provider.fetch_observation(lat=lat, lon=lon)

    logger.info(f"Cloud observation: {observation.cover_pct}% cover, type hint: {observation.cloud_type_hint}")

    return {
        "site_id": settings.site_id,
        "provider": settings.cloud_provider,
        "cover_pct": observation.cover_pct,
        "cloud_base_m": observation.cloud_base_m,
        "cloud_type_hint": observation.cloud_type_hint,
        "satellite_url": observation.satellite_url,
        "observed_at": observation.observed_at.isoformat() if observation.observed_at else None,
        "confidence": observation.confidence,
        "interpretation": _interpret_cloud_cover(observation.cover_pct, observation.cloud_type_hint),
    }


@router.get("/history", summary="Recent cloud observations from DB")
async def get_cloud_history(
    db: DatabaseDep,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """
    Return recent cloud observations stored in the database.
    """
    result = await db.execute(
        select(CloudObservation)
        .order_by(desc(CloudObservation.observed_at))
        .limit(limit)
    )
    observations = result.scalars().all()

    return [
        {
            "id": obs.id,
            "provider": obs.provider,
            "observed_at": obs.observed_at.isoformat() if obs.observed_at else None,
            "data": json.loads(obs.data_json) if obs.data_json else {},
        }
        for obs in observations
    ]


def _interpret_cloud_cover(cover_pct: float, cloud_type_hint: str | None) -> str:
    """Human-readable interpretation of cloud cover for thermal potential."""
    if cover_pct < 10:
        return "Clear sky: strong solar heating, thermals likely punchy and narrow. No cloud streets."
    elif cover_pct < 30:
        return "Mostly clear: excellent solar heating, developing thermals. Ideal conditions."
    elif cover_pct < 60:
        if cloud_type_hint and "cumulus" in cloud_type_hint.lower():
            return "Partial cumulus: thermal markers visible, organized development. Good flying conditions."
        return "Partly cloudy: good thermal development, some shading between cycles."
    elif cover_pct < 75:
        return "Mostly cloudy: thermal suppression beginning. Cycles becoming less consistent."
    else:
        return "Heavy cloud cover: thermals significantly suppressed. Ridge soaring may still be possible."
