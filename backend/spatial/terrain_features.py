"""
Spatial queries for terrain features using PostGIS and SQLAlchemy.

Provides helpers for proximity queries, thermal candidate retrieval,
and risk zone lookups using GeoAlchemy2 + PostGIS ST_ functions.
"""

from typing import Any

from geoalchemy2.functions import ST_DWithin, ST_MakePoint, ST_SetSRID
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import TerrainFeature


class SpatialQueries:
    """
    PostGIS-backed spatial query helpers for terrain feature retrieval.

    All methods return dicts (not ORM objects) for easy JSON serialization.
    """

    @staticmethod
    async def get_features_near(
        lat: float,
        lon: float,
        radius_m: float,
        db: AsyncSession,
    ) -> list[dict[str, Any]]:
        """
        Return terrain features within radius_m meters of the given lat/lon.

        Uses PostGIS ST_DWithin for efficient spatial indexing.

        Args:
            lat: Search center latitude
            lon: Search center longitude
            radius_m: Search radius in meters
            db: Async SQLAlchemy session

        Returns:
            List of terrain feature dicts with spatial data
        """
        # Convert radius from meters to degrees (approximate, valid at mid-latitudes)
        # 1 degree ≈ 111,000m
        radius_deg = radius_m / 111000.0

        point = ST_SetSRID(ST_MakePoint(lon, lat), 4326)

        result = await db.execute(
            select(TerrainFeature).where(
                ST_DWithin(TerrainFeature.geom, point, radius_deg)
            )
        )
        features = result.scalars().all()

        logger.debug(f"SpatialQueries.get_features_near: {len(features)} features within {radius_m}m of ({lat},{lon})")
        return _features_to_dicts(features)

    @staticmethod
    async def get_thermal_candidates(
        site_id: int,
        db: AsyncSession,
    ) -> list[dict[str, Any]]:
        """
        Return terrain features that are candidates for thermal generation.

        Includes: ridge, bowl, riverbed (south-facing terrain + heating surfaces).

        Args:
            site_id: DB site profile ID
            db: Async SQLAlchemy session

        Returns:
            List of terrain feature dicts
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

        Args:
            site_id: DB site profile ID
            db: Async SQLAlchemy session

        Returns:
            List of terrain feature dicts
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
    import json
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
