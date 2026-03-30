"""
Spatial queries for terrain features.

Provides helpers for proximity queries, thermal candidate retrieval,
and risk zone lookups. PostGIS deferred to Phase 4 — currently uses
simple DB queries without spatial indexing.
"""

import json
from typing import Any

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import TerrainFeature


class SpatialQueries:
    """
    Terrain feature query helpers.

    Phase 1: simple attribute-based queries (no PostGIS).
    Phase 4: upgrade to PostGIS ST_ functions for spatial indexing.
    """

    @staticmethod
    async def get_features_near(
        lat: float,
        lon: float,
        radius_m: float,
        db: AsyncSession,
    ) -> list[dict[str, Any]]:
        """
        Return terrain features near the given lat/lon.

        Phase 1: returns all features (spatial filtering deferred to Phase 4).
        """
        result = await db.execute(select(TerrainFeature))
        features = result.scalars().all()
        logger.debug(f"SpatialQueries.get_features_near: {len(features)} features (spatial filter deferred)")
        return _features_to_dicts(features)

    @staticmethod
    async def get_thermal_candidates(
        site_id: int,
        db: AsyncSession,
    ) -> list[dict[str, Any]]:
        """
        Return terrain features that are candidates for thermal generation.

        Includes: ridge, bowl, riverbed (south-facing terrain + heating surfaces).
        """
        result = await db.execute(
            select(TerrainFeature).where(
                TerrainFeature.site_id == site_id,
                TerrainFeature.feature_type.in_(["ridge", "bowl", "riverbed"]),
            )
        )
        features = result.scalars().all()
        logger.debug(f"SpatialQueries.get_thermal_candidates: {len(features)} candidates for site_id={site_id}")
        return _features_to_dicts(features)

    @staticmethod
    async def get_risk_zones(
        site_id: int,
        db: AsyncSession,
    ) -> list[dict[str, Any]]:
        """
        Return terrain features classified as hazardous zones.

        Includes: rotor_zone, sink_zone, tree_line.
        """
        result = await db.execute(
            select(TerrainFeature).where(
                TerrainFeature.site_id == site_id,
                TerrainFeature.feature_type.in_(["rotor_zone", "sink_zone", "tree_line"]),
            )
        )
        features = result.scalars().all()
        logger.debug(f"SpatialQueries.get_risk_zones: {len(features)} risk zones for site_id={site_id}")
        return _features_to_dicts(features)


def _features_to_dicts(features: list[TerrainFeature]) -> list[dict[str, Any]]:
    """Convert ORM TerrainFeature objects to serializable dicts."""
    result = []
    for f in features:
        d = {
            "id": f.id,
            "site_id": f.site_id,
            "feature_type": f.feature_type,
            "name": f.name,
            "notes": f.notes,
            "attributes": json.loads(f.attributes_json) if f.attributes_json else {},
        }
        result.append(d)
    return result
