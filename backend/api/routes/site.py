"""
Site profile routes for paraglide-backend.

Exposes the current site's configuration, terrain features, launch points,
and landing zones as JSON endpoints.
"""

from typing import Any

from fastapi import APIRouter
from loguru import logger

from api.deps import SiteProfileDep

router = APIRouter()


@router.get("", summary="Get current site profile")
async def get_site_profile(profile: SiteProfileDep) -> dict[str, Any]:
    """
    Return the full site profile for the configured site.

    Includes location, boundary, seasonal notes, known heuristics, and risk notes.
    """
    logger.debug(f"Serving site profile: {profile.get('name')}")
    return profile


@router.get("/terrain-features", summary="List terrain features for this site")
async def get_terrain_features(profile: SiteProfileDep) -> list[dict[str, Any]]:
    """
    Return all named terrain features for the site: ridges, bowls, valleys,
    riverbeds, tree lines, sink zones, and rotor zones.
    """
    features = profile.get("terrain_features", [])
    logger.debug(f"Returning {len(features)} terrain features")
    return features


@router.get("/launches", summary="List launch points for this site")
async def get_launches(profile: SiteProfileDep) -> list[dict[str, Any]]:
    """
    Return all launch points with coordinates, elevation, optimal wind conditions,
    and notes.
    """
    launches = profile.get("launches", [])
    logger.debug(f"Returning {len(launches)} launch points")
    return launches


@router.get("/landings", summary="List landing zones for this site")
async def get_landings(profile: SiteProfileDep) -> list[dict[str, Any]]:
    """
    Return all landing zones with coordinates, surface description, and notes.
    """
    landings = profile.get("landings", [])
    logger.debug(f"Returning {len(landings)} landing zones")
    return landings
