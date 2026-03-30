"""
Historical flight track routes for paraglide-backend.

Supports importing IGC and GPX flight files, listing stored tracks,
and retrieving segmented analysis per track.
"""

import json
from typing import Any

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from loguru import logger
from sqlalchemy import select

from api.deps import DatabaseDep, SettingsDep
from db.models import FlightSegment, HistoricalFlightTrack

router = APIRouter()


@router.post("/import", summary="Import an IGC or GPX flight file", status_code=201)
async def import_track(
    file: UploadFile = File(...),
    site_id: str = Form(...),
    pilot_name: str | None = Form(default=None),
    db: DatabaseDep = None,
    settings: SettingsDep = None,
) -> dict[str, Any]:
    """
    Parse and store a flight track from an IGC or GPX file.

    The file is parsed into fixes, then segmented into climb/glide/sink phases.
    Segments are stored with spatial geometry for later analysis.
    """
    from db.models import SiteProfile

    site_result = await db.execute(
        select(SiteProfile).where(SiteProfile.slug == (site_id or settings.site_id))
    )
    site = site_result.scalar_one_or_none()
    if site is None:
        raise HTTPException(status_code=404, detail=f"Site '{site_id}' not found")

    content = await file.read()
    filename = file.filename or "unknown"
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if ext == "igc":
        from data_ingestion.flights.igc_parser import IGCParser
        parser = IGCParser()
        parsed = parser.parse(content.decode("utf-8", errors="replace"))
        source_format = "igc"
    elif ext == "gpx":
        from data_ingestion.flights.gpx_parser import GPXParser
        parser = GPXParser()
        parsed = parser.parse(content.decode("utf-8", errors="replace"))
        source_format = "gpx"
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported file format: .{ext}. Use .igc or .gpx")

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
        site_id=site.id,
        source_format=source_format,
        filename=filename,
        pilot_name=pilot_name or parsed.pilot_name,
        flight_date=parsed.flight_date,
        track_geojson=json.dumps(track_geojson),
        metadata_json=json.dumps({
            "glider": parsed.glider,
            "fix_count": len(parsed.fixes),
            "segment_count": len(parsed.segments),
        }),
    )
    db.add(track)
    await db.flush()
    await db.refresh(track)

    # Store segments
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
            attributes_json=json.dumps({"fix_count": len(seg.fixes)}),
        )
        db.add(segment)

    await db.flush()

    climb_count = sum(1 for s in parsed.segments if s.segment_type == "climb")
    logger.info(f"Track imported: id={track.id} pilot={track.pilot_name} segments={len(parsed.segments)} climbs={climb_count}")

    return {
        "track_id": track.id,
        "filename": filename,
        "pilot_name": track.pilot_name,
        "flight_date": track.flight_date.isoformat() if track.flight_date else None,
        "fix_count": len(parsed.fixes),
        "segment_count": len(parsed.segments),
        "climb_count": climb_count,
    }


@router.get("", summary="List historical tracks for site")
async def list_tracks(
    settings: SettingsDep,
    db: DatabaseDep,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Return stored historical flight tracks for the current site."""
    from db.models import SiteProfile
    site_result = await db.execute(
        select(SiteProfile).where(SiteProfile.slug == settings.site_id)
    )
    site = site_result.scalar_one_or_none()
    if site is None:
        return []

    result = await db.execute(
        select(HistoricalFlightTrack)
        .where(HistoricalFlightTrack.site_id == site.id)
        .order_by(HistoricalFlightTrack.flight_date.desc())
        .limit(limit)
    )
    tracks = result.scalars().all()

    return [
        {
            "id": t.id,
            "source_format": t.source_format,
            "filename": t.filename,
            "pilot_name": t.pilot_name,
            "flight_date": t.flight_date.isoformat() if t.flight_date else None,
            "metadata": json.loads(t.metadata_json) if t.metadata_json else {},
        }
        for t in tracks
    ]


@router.get("/{track_id}/segments", summary="Return flight segments for a track")
async def get_track_segments(
    track_id: int,
    db: DatabaseDep,
) -> dict[str, Any]:
    """
    Return all flight segments (climb/glide/sink) for a specific track.
    """
    result = await db.execute(
        select(FlightSegment)
        .where(FlightSegment.track_id == track_id)
        .order_by(FlightSegment.start_time)
    )
    segments = result.scalars().all()

    if not segments:
        raise HTTPException(status_code=404, detail=f"No segments for track {track_id}")

    return {
        "track_id": track_id,
        "segment_count": len(segments),
        "segments": [
            {
                "id": s.id,
                "type": s.segment_type,
                "start_time": s.start_time.isoformat() if s.start_time else None,
                "end_time": s.end_time.isoformat() if s.end_time else None,
                "avg_vario_ms": s.avg_vario_ms,
                "max_altitude_m": s.max_altitude_m,
                "path_geojson": json.loads(s.path_geojson) if s.path_geojson else None,
                "attributes": json.loads(s.attributes_json) if s.attributes_json else {},
            }
            for s in segments
        ],
    }
