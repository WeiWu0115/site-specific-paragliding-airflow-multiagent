"""
IGC import CLI script for paraglide-backend.

Parses and imports IGC flight files into the database.

Usage:
    cd backend
    python ../scripts/import_igc.py --file /path/to/flight.igc --site eagle_ridge
    python ../scripts/import_igc.py --dir /path/to/igc_folder --site eagle_ridge
"""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://paraglide:paraglide@localhost:5432/paraglide_db"
)


async def import_single_igc(
    igc_path: Path,
    site_id: int,
    session: AsyncSession,
) -> dict:
    """Import a single IGC file. Returns summary dict."""
    from data_ingestion.flights.igc_parser import IGCParser
    from db.models import FlightSegment, HistoricalFlightTrack

    content = igc_path.read_text(encoding="utf-8", errors="replace")
    parser = IGCParser()
    parsed = parser.parse(content)

    if not parsed.fixes:
        logger.warning(f"  No fixes found in {igc_path.name}")
        return {"filename": igc_path.name, "status": "no_fixes", "fix_count": 0}

    # Build GeoJSON track
    track_geojson = {
        "type": "LineString",
        "coordinates": [
            [fix.lon, fix.lat, fix.altitude_gps_m]
            for fix in parsed.fixes
            if fix.lat and fix.lon
        ],
    }

    track = HistoricalFlightTrack(
        site_id=site_id,
        source_format="igc",
        filename=igc_path.name,
        pilot_name=parsed.pilot_name,
        flight_date=parsed.flight_date,
        track_geojson=json.dumps(track_geojson),
        metadata_json=json.dumps({
            "glider": parsed.glider,
            "fix_count": len(parsed.fixes),
            "segment_count": len(parsed.segments),
        }),
    )
    session.add(track)
    await session.flush()
    await session.refresh(track)

    climb_count = 0
    sink_count = 0
    for seg in parsed.segments:
        start_fix = seg.fixes[0] if seg.fixes else None
        end_fix = seg.fixes[-1] if seg.fixes else None
        path_geojson = {
            "type": "LineString",
            "coordinates": [[f.lon, f.lat, f.altitude_gps_m] for f in seg.fixes],
        }
        segment = FlightSegment(
            track_id=track.id,
            segment_type=seg.segment_type,
            start_time=start_fix.time if start_fix else None,
            end_time=end_fix.time if end_fix else None,
            avg_vario_ms=seg.avg_vario_ms,
            max_altitude_m=max((f.altitude_gps_m for f in seg.fixes), default=None),
            path_geojson=json.dumps(path_geojson),
        )
        session.add(segment)
        if seg.segment_type == "climb":
            climb_count += 1
        elif seg.segment_type == "sink":
            sink_count += 1

    await session.flush()

    logger.info(
        f"  Imported: {igc_path.name} | pilot={parsed.pilot_name} | "
        f"fixes={len(parsed.fixes)} | climbs={climb_count} sinks={sink_count}"
    )
    return {
        "filename": igc_path.name,
        "status": "imported",
        "track_id": track.id,
        "fix_count": len(parsed.fixes),
        "segment_count": len(parsed.segments),
        "climb_count": climb_count,
        "sink_count": sink_count,
    }


async def main() -> None:
    parser = argparse.ArgumentParser(description="Import IGC flight files into paraglide DB")
    parser.add_argument("--file", type=str, help="Path to a single IGC file")
    parser.add_argument("--dir", type=str, help="Path to a directory of IGC files")
    parser.add_argument("--site", type=str, default="eagle_ridge", help="Site slug (default: eagle_ridge)")
    args = parser.parse_args()

    if not args.file and not args.dir:
        parser.error("Provide --file or --dir")

    igc_files: list[Path] = []
    if args.file:
        igc_files.append(Path(args.file))
    if args.dir:
        dir_path = Path(args.dir)
        igc_files.extend(dir_path.glob("*.igc"))
        igc_files.extend(dir_path.glob("*.IGC"))

    if not igc_files:
        logger.error("No IGC files found")
        sys.exit(1)

    logger.info(f"Found {len(igc_files)} IGC files to import")

    engine = create_async_engine(DATABASE_URL, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        # Look up site ID
        from db.models import SiteProfile
        site_result = await session.execute(
            select(SiteProfile).where(SiteProfile.slug == args.site)
        )
        site = site_result.scalar_one_or_none()
        if site is None:
            logger.error(f"Site '{args.site}' not found in DB. Run seed_site.py first.")
            sys.exit(1)

        results = []
        for igc_path in igc_files:
            try:
                result = await import_single_igc(igc_path, site.id, session)
                results.append(result)
            except Exception as e:
                logger.error(f"Failed to import {igc_path.name}: {e}")
                results.append({"filename": igc_path.name, "status": "error", "error": str(e)})

        await session.commit()

    await engine.dispose()

    # Summary
    imported = [r for r in results if r["status"] == "imported"]
    total_climbs = sum(r.get("climb_count", 0) for r in imported)
    total_sinks = sum(r.get("sink_count", 0) for r in imported)
    total_segments = sum(r.get("segment_count", 0) for r in imported)

    logger.info("=" * 50)
    logger.info(f"Import complete: {len(imported)}/{len(results)} tracks imported")
    logger.info(f"Total segments: {total_segments} ({total_climbs} climbs, {total_sinks} sinks)")
    errors = [r for r in results if r["status"] == "error"]
    if errors:
        logger.warning(f"Errors: {len(errors)} files failed")


if __name__ == "__main__":
    asyncio.run(main())
