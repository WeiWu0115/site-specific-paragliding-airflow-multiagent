"""
Replay service for paraglide-backend.

Supports creating and retrieving replay sessions that link a historical
flight track to a weather snapshot for post-flight analysis.
"""

import json
from datetime import datetime, timezone
from typing import Any

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class ReplayService:
    """
    Manages replay sessions for post-flight analysis.

    A replay session links:
    - A historical flight track (with GPS fixes and segments)
    - The closest available weather snapshot to the flight date
    - Planning session output (agent claims, recommendations)

    This allows comparing what the system would have predicted against
    what the pilot actually experienced.
    """

    async def create_replay_session(
        self,
        track_id: int,
        db: AsyncSession,
        weather_snapshot_id: int | None = None,
    ) -> dict[str, Any]:
        """
        Create a replay session for a historical flight track.

        Finds the closest weather snapshot to the flight date if not specified.

        Args:
            track_id: ID of the HistoricalFlightTrack to replay
            db: Async SQLAlchemy session
            weather_snapshot_id: Optional specific weather snapshot to use

        Returns:
            Dict with session creation summary
        """
        from db.models import HistoricalFlightTrack, NegotiationSession, WeatherSnapshot

        # Load track
        track_result = await db.execute(
            select(HistoricalFlightTrack).where(HistoricalFlightTrack.id == track_id)
        )
        track = track_result.scalar_one_or_none()
        if track is None:
            raise ValueError(f"Track {track_id} not found")

        logger.info(f"Creating replay session for track_id={track_id} pilot={track.pilot_name}")

        # Find closest weather snapshot if not specified
        snap_id = weather_snapshot_id
        if snap_id is None and track.flight_date:
            snap_result = await db.execute(
                select(WeatherSnapshot)
                .where(WeatherSnapshot.site_id == track.site_id)
                .order_by(WeatherSnapshot.fetched_at.desc())
                .limit(1)
            )
            snap = snap_result.scalar_one_or_none()
            if snap:
                snap_id = snap.id
                logger.info(f"Using weather snapshot id={snap_id}")

        # Create a negotiation session record for the replay
        session = NegotiationSession(
            site_id=track.site_id,
            weather_snapshot_id=snap_id,
            status="complete",
            inputs_json=json.dumps({
                "track_id": track_id,
                "replay": True,
                "flight_date": str(track.flight_date) if track.flight_date else None,
            }),
            outputs_json=json.dumps({
                "track_id": track_id,
                "replay": True,
                "pilot_name": track.pilot_name,
                "flight_date": str(track.flight_date) if track.flight_date else None,
            }),
        )
        db.add(session)
        await db.flush()
        await db.refresh(session)

        logger.info(f"Replay session created: id={session.id}")

        return {
            "session_id": session.id,
            "track_id": track_id,
            "pilot_name": track.pilot_name,
            "flight_date": str(track.flight_date) if track.flight_date else None,
            "weather_snapshot_id": snap_id,
        }

    async def get_replay_data(
        self,
        session_id: int,
        db: AsyncSession,
    ) -> dict[str, Any]:
        """
        Retrieve replay data for a session.

        Returns the track GeoJSON, agent claims (if any), and recommendations
        ordered for time-based playback.

        Args:
            session_id: Negotiation session ID
            db: Async SQLAlchemy session

        Returns:
            Replay data dict with track, claims, and recommendations
        """
        from db.models import (
            AgentClaim,
            FlightSegment,
            HistoricalFlightTrack,
            NegotiationSession,
            Recommendation,
        )

        session_result = await db.execute(
            select(NegotiationSession).where(NegotiationSession.id == session_id)
        )
        session = session_result.scalar_one_or_none()
        if session is None:
            raise ValueError(f"Session {session_id} not found")

        outputs = json.loads(session.outputs_json) if session.outputs_json else {}
        track_id = outputs.get("track_id")

        # Load track + segments
        track_data = None
        segment_data = []
        if track_id:
            track_result = await db.execute(
                select(HistoricalFlightTrack).where(HistoricalFlightTrack.id == track_id)
            )
            track = track_result.scalar_one_or_none()
            if track:
                track_data = {
                    "id": track.id,
                    "pilot_name": track.pilot_name,
                    "flight_date": str(track.flight_date) if track.flight_date else None,
                    "track_geojson": json.loads(track.track_geojson) if track.track_geojson else None,
                }

                segs_result = await db.execute(
                    select(FlightSegment)
                    .where(FlightSegment.track_id == track_id)
                    .order_by(FlightSegment.start_time)
                )
                segments = segs_result.scalars().all()
                segment_data = [
                    {
                        "id": s.id,
                        "type": s.segment_type,
                        "start_time": s.start_time.isoformat() if s.start_time else None,
                        "end_time": s.end_time.isoformat() if s.end_time else None,
                        "avg_vario_ms": s.avg_vario_ms,
                        "max_altitude_m": s.max_altitude_m,
                    }
                    for s in segments
                ]

        # Load claims and recommendations
        claims_result = await db.execute(
            select(AgentClaim).where(AgentClaim.session_id == session_id)
        )
        claims = claims_result.scalars().all()

        recs_result = await db.execute(
            select(Recommendation).where(Recommendation.session_id == session_id)
            .order_by(Recommendation.rank)
        )
        recommendations = recs_result.scalars().all()

        return {
            "session_id": session_id,
            "track": track_data,
            "segments": segment_data,
            "claims": [
                {
                    "agent_name": c.agent_name,
                    "claim_type": c.claim_type,
                    "confidence": c.confidence,
                    "spatial_scope": json.loads(c.spatial_scope_json) if c.spatial_scope_json else None,
                    "temporal_validity": json.loads(c.temporal_validity_json) if c.temporal_validity_json else None,
                }
                for c in claims
            ],
            "recommendations": [
                {
                    "rank": r.rank,
                    "type": r.rec_type,
                    "title": r.title,
                    "confidence": r.confidence,
                }
                for r in recommendations
            ],
        }
