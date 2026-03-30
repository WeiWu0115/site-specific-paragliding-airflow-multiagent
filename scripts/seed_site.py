"""
Seed script for Eagle Ridge Flying Site.

Loads eagle_ridge.json and populates the database with:
- site_profiles row
- launches rows
- landings rows
- terrain_features rows with PostGIS geometry
- initial knowledge_items from known_heuristics

Idempotent: skips records that already exist.

Usage:
    cd backend
    python ../scripts/seed_site.py
"""

import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://paraglide:paraglide@localhost:5432/paraglide_db"
)

PROFILE_PATH = os.path.join(
    os.path.dirname(__file__), "..", "backend", "config", "site_profiles", "eagle_ridge.json"
)


def _make_point_wkt(lon: float, lat: float) -> str:
    """Build WKT POINT string from lon/lat."""
    return f"SRID=4326;POINT({lon} {lat})"


def _make_geometry_wkt(geom: dict) -> str | None:
    """Convert GeoJSON geometry to WKT with SRID prefix."""
    if not geom:
        return None
    geom_type = geom.get("type", "")
    coords = geom.get("coordinates")

    if geom_type == "Point":
        return f"SRID=4326;POINT({coords[0]} {coords[1]})"
    elif geom_type == "LineString":
        coord_str = ", ".join(f"{c[0]} {c[1]}" for c in coords)
        return f"SRID=4326;LINESTRING({coord_str})"
    elif geom_type == "Polygon":
        outer = coords[0]
        coord_str = ", ".join(f"{c[0]} {c[1]}" for c in outer)
        return f"SRID=4326;POLYGON(({coord_str}))"
    return None


async def seed(session: AsyncSession, profile: dict) -> None:
    from db.models import (
        KnowledgeItem,
        Landing,
        Launch,
        SiteProfile,
        TerrainFeature,
    )

    # ------------------------------------------------------------------ #
    # 1. Site profile
    # ------------------------------------------------------------------ #
    existing = await session.execute(
        select(SiteProfile).where(SiteProfile.slug == profile["id"])
    )
    site = existing.scalar_one_or_none()
    if site:
        logger.info(f"Site profile already exists: slug={profile['id']}, id={site.id}")
    else:
        boundary_geojson = json.dumps(profile.get("boundary"))
        site = SiteProfile(
            slug=profile["id"],
            name=profile["name"],
            description=profile.get("description"),
            boundary_geojson=boundary_geojson,
            config_json=json.dumps({
                "location": profile.get("location"),
                "dominant_wind": profile.get("dominant_wind"),
                "seasonal_notes": profile.get("seasonal_notes"),
            }),
        )
        session.add(site)
        await session.flush()
        await session.refresh(site)
        logger.info(f"Created site profile: slug={site.slug} id={site.id}")

    site_id = site.id

    # ------------------------------------------------------------------ #
    # 2. Launches
    # ------------------------------------------------------------------ #
    for launch_data in profile.get("launches", []):
        existing_launch = await session.execute(
            select(Launch).where(
                Launch.site_id == site_id,
                Launch.name == launch_data["name"],
            )
        )
        if existing_launch.scalar_one_or_none():
            logger.info(f"  Launch already exists: {launch_data['name']}")
            continue

        point_wkt = _make_point_wkt(launch_data["lon"], launch_data["lat"])
        launch = Launch(
            site_id=site_id,
            name=launch_data["name"],
            point_geom=point_wkt,
            elevation_m=launch_data.get("elevation_m"),
            notes=launch_data.get("notes"),
        )
        session.add(launch)
        logger.info(f"  Created launch: {launch_data['name']} at {launch_data['lat']}, {launch_data['lon']}")

    await session.flush()

    # ------------------------------------------------------------------ #
    # 3. Landings
    # ------------------------------------------------------------------ #
    for lz_data in profile.get("landings", []):
        existing_lz = await session.execute(
            select(Landing).where(
                Landing.site_id == site_id,
                Landing.name == lz_data["name"],
            )
        )
        if existing_lz.scalar_one_or_none():
            logger.info(f"  Landing already exists: {lz_data['name']}")
            continue

        point_wkt = _make_point_wkt(lz_data["lon"], lz_data["lat"])
        landing = Landing(
            site_id=site_id,
            name=lz_data["name"],
            point_geom=point_wkt,
            elevation_m=lz_data.get("elevation_m"),
            notes=lz_data.get("notes"),
        )
        session.add(landing)
        logger.info(f"  Created landing: {lz_data['name']}")

    await session.flush()

    # ------------------------------------------------------------------ #
    # 4. Terrain features
    # ------------------------------------------------------------------ #
    for tf_data in profile.get("terrain_features", []):
        existing_tf = await session.execute(
            select(TerrainFeature).where(
                TerrainFeature.site_id == site_id,
                TerrainFeature.name == tf_data["name"],
            )
        )
        if existing_tf.scalar_one_or_none():
            logger.info(f"  Terrain feature already exists: {tf_data['name']}")
            continue

        geom_wkt = _make_geometry_wkt(tf_data.get("geometry"))

        tf = TerrainFeature(
            site_id=site_id,
            feature_type=tf_data["type"],
            name=tf_data["name"],
            geom=geom_wkt,
            attributes_json=json.dumps(tf_data.get("attributes", {})),
            notes=tf_data.get("description"),
        )
        session.add(tf)
        logger.info(f"  Created terrain feature: {tf_data['name']} ({tf_data['type']})")

    await session.flush()

    # ------------------------------------------------------------------ #
    # 5. Knowledge items from known_heuristics
    # ------------------------------------------------------------------ #
    from datetime import date

    for h in profile.get("known_heuristics", []):
        existing_ki = await session.execute(
            select(KnowledgeItem).where(
                KnowledgeItem.site_id == site_id,
                KnowledgeItem.statement == h["statement"],
            )
        )
        if existing_ki.scalar_one_or_none():
            logger.info(f"  Knowledge item already exists: {h['id']}")
            continue

        condition = h.get("condition", {})

        # Build wind_condition string from condition dict
        wind_condition = None
        if condition.get("wind_dir_deg_range"):
            dirs = condition["wind_dir_deg_range"]
            wind_condition = f"Wind direction {dirs[0]}-{dirs[1]}°"
        if condition.get("wind_speed_kmh_range"):
            speeds = condition["wind_speed_kmh_range"]
            wind_speed_str = f" {speeds[0]}-{speeds[1]} km/h"
            wind_condition = (wind_condition or "") + wind_speed_str

        season = condition.get("season")
        if isinstance(season, list):
            season = ",".join(season)

        time_local = condition.get("time_local")

        ki = KnowledgeItem(
            site_id=site_id,
            sub_region=h.get("sub_region"),
            wind_condition=wind_condition,
            time_of_day=time_local,
            season=season,
            statement=h["statement"],
            exception_statement=h.get("exception"),
            risk_note=h.get("risk_note"),
            source_expert=h.get("source"),
            confidence=h.get("confidence", 0.5),
            provenance_json=json.dumps({
                "heuristic_id": h.get("id"),
                "source": h.get("source"),
                "import_method": "seed_script",
            }),
        )
        session.add(ki)
        logger.info(f"  Created knowledge item: {h['id']} conf={h.get('confidence', 0.5)}")

    await session.commit()
    logger.info("Seed complete!")


async def main() -> None:
    logger.info(f"Loading site profile: {PROFILE_PATH}")
    with open(PROFILE_PATH) as f:
        profile = json.load(f)

    logger.info(f"Site: {profile['name']}")
    logger.info(f"Connecting to: {DATABASE_URL.split('@')[-1]}")

    engine = create_async_engine(DATABASE_URL, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        await seed(session, profile)

    await engine.dispose()
    logger.info("Database connection closed.")


if __name__ == "__main__":
    asyncio.run(main())
