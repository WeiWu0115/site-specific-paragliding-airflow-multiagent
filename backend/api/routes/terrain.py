"""
Terrain analysis routes for paraglide-backend.

Returns terrain features with spatial data and provides a terrain analysis
summary including slope, aspect, ridge/valley identification.
"""

import json
import math
from typing import Any

from fastapi import APIRouter
from loguru import logger
from sqlalchemy import select

from api.deps import DatabaseDep, SettingsDep, SiteProfileDep
from db.models import TerrainFeature

router = APIRouter()


@router.get("", summary="Return terrain features with spatial data")
async def get_terrain(
    profile: SiteProfileDep,
    db: DatabaseDep,
) -> dict[str, Any]:
    """
    Return all terrain features for the current site, combining the site profile
    definition with any DB-stored features.
    """
    # Try DB first
    result = await db.execute(select(TerrainFeature).limit(200))
    db_features = result.scalars().all()

    if db_features:
        features = [
            {
                "id": f.id,
                "name": f.name,
                "feature_type": f.feature_type,
                "notes": f.notes,
                "attributes": json.loads(f.attributes_json) if f.attributes_json else {},
            }
            for f in db_features
        ]
        source = "database"
    else:
        # Fall back to site profile
        features = profile.get("terrain_features", [])
        source = "site_profile"
        logger.debug("No DB terrain features found, returning from site profile")

    return {
        "site_id": profile["id"],
        "source": source,
        "count": len(features),
        "features": features,
    }


@router.get("/analysis", summary="Terrain analysis summary: slope, aspect, ridge/valley")
async def get_terrain_analysis(
    profile: SiteProfileDep,
    settings: SettingsDep,
) -> dict[str, Any]:
    """
    Return a terrain analysis summary derived from the site profile.

    In Phase 2, this will incorporate DEM data. Currently it uses the
    descriptive attributes from the site profile terrain features.
    """
    features = profile.get("terrain_features", [])

    ridges = [f for f in features if f.get("type") == "ridge"]
    bowls = [f for f in features if f.get("type") == "bowl"]
    sinks = [f for f in features if f.get("type") in ("sink_zone", "rotor_zone")]
    riverbeds = [f for f in features if f.get("type") == "riverbed"]

    # Simple aspect alignment analysis for each ridge
    ridge_analysis = []
    for r in ridges:
        attrs = r.get("attributes", {})
        aspect = attrs.get("aspect_deg", None)
        ridge_analysis.append({
            "name": r["name"],
            "aspect_deg": aspect,
            "south_facing": (aspect is not None and 135 <= aspect <= 225),
            "slope_deg_avg": attrs.get("slope_deg_avg"),
            "optimal_wind_range_kmh": attrs.get("wind_range_for_lift_kmh"),
        })

    # Thermal slope candidates: south/SE/SW facing, slope 15-35 degrees
    thermal_slope_candidates = [
        ra for ra in ridge_analysis
        if ra.get("south_facing") and ra.get("slope_deg_avg") and 15 <= ra["slope_deg_avg"] <= 40
    ]

    return {
        "site_id": profile["id"],
        "summary": {
            "total_features": len(features),
            "ridges": len(ridges),
            "bowls": len(bowls),
            "sink_rotor_zones": len(sinks),
            "riverbeds": len(riverbeds),
        },
        "ridge_analysis": ridge_analysis,
        "thermal_slope_candidates": thermal_slope_candidates,
        "risk_zones": [
            {
                "name": f["name"],
                "type": f.get("type"),
                "notes": f.get("description", ""),
                "wind_trigger": f.get("attributes", {}).get("wind_trigger_speed_kmh"),
            }
            for f in sinks
        ],
        "note": "Full DEM analysis available in Phase 2 with rasterio integration.",
    }
