"""
Planning service for paraglide-backend.

Orchestrates the full multi-agent planning pipeline:
load site -> fetch weather -> fetch clouds -> load terrain/knowledge/history
-> run all agents -> risk check -> negotiate -> store -> return result.
"""

import asyncio
import json
from datetime import date, datetime, timezone
from typing import Any

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from agents.negotiation_agent import NegotiationAgent, NegotiationResult
from agents.base import Claim


class PlanningService:
    """
    Orchestrates the full multi-agent planning pipeline.

    All agents run concurrently via asyncio.gather() after their inputs
    are prepared. The RiskAgent and NegotiationAgent run sequentially
    after all primary agents complete.
    """

    async def run_planning_session(
        self,
        site_id: str,
        target_date: date,
        db: AsyncSession,
    ) -> NegotiationResult:
        """
        Execute a complete planning session and store results in DB.

        Steps:
        1. Load site profile
        2. Fetch weather forecast
        3. Fetch cloud observation
        4. Load terrain features (DB or site profile fallback)
        5. Load matching knowledge items
        6. Load recent flight segments
        7. Run all agents concurrently
        8. Run RiskAgent
        9. Run NegotiationAgent
        10. Store session + claims + recommendations in DB
        11. Return NegotiationResult

        Args:
            site_id: Site slug (e.g. "eagle_ridge")
            target_date: Date for the planning session
            db: Async SQLAlchemy session

        Returns:
            NegotiationResult with ranked recommendations
        """
        logger.info(f"PlanningService: starting session for site={site_id} date={target_date}")
        session_start = datetime.now(tz=timezone.utc)

        # ------------------------------------------------------------------ #
        # 1. Load site profile
        # ------------------------------------------------------------------ #
        import os
        from config.settings import get_settings
        settings = get_settings()
        profile_path = settings.site_profile_path
        try:
            with open(profile_path) as f:
                site_profile = json.load(f)
            logger.info(f"Site profile loaded: {site_profile.get('name')}")
        except FileNotFoundError:
            logger.error(f"Site profile not found: {profile_path}")
            raise ValueError(f"Site profile not found for site_id={site_id}")

        # ------------------------------------------------------------------ #
        # 2. Create DB negotiation session record
        # ------------------------------------------------------------------ #
        from db.models import SiteProfile, NegotiationSession
        site_result = await db.execute(
            __import__("sqlalchemy").select(SiteProfile).where(SiteProfile.slug == site_id)
        )
        site_db = site_result.scalar_one_or_none()
        site_db_id = site_db.id if site_db else 1  # Fallback to 1 if not seeded

        session_record = NegotiationSession(
            site_id=site_db_id,
            status="running",
            inputs_json=json.dumps({"site_id": site_id, "target_date": str(target_date)}),
        )
        db.add(session_record)
        await db.flush()
        await db.refresh(session_record)
        logger.info(f"Planning session created: id={session_record.id}")

        try:
            # -------------------------------------------------------------- #
            # 3. Fetch weather
            # -------------------------------------------------------------- #
            if settings.is_mock_weather:
                from data_ingestion.weather.mock_provider import MockWeatherProvider
                weather_provider = MockWeatherProvider()
            else:
                from data_ingestion.weather.open_meteo import OpenMeteoProvider
                weather_provider = OpenMeteoProvider(base_url=settings.open_meteo_base_url)

            lat = site_profile["location"]["lat"]
            lon = site_profile["location"]["lon"]
            forecast = await weather_provider.fetch_forecast(lat, lon)
            logger.info(f"Weather fetched: {len(forecast.hourly)} hourly records")

            # -------------------------------------------------------------- #
            # 4. Fetch cloud observation
            # -------------------------------------------------------------- #
            from data_ingestion.clouds.mock_cloud_provider import MockCloudProvider
            cloud_obs = await MockCloudProvider().fetch_observation(lat, lon)
            logger.info(f"Cloud observation: {cloud_obs.cover_pct:.0f}%")

            # -------------------------------------------------------------- #
            # 5. Load terrain features
            # -------------------------------------------------------------- #
            terrain_features = site_profile.get("terrain_features", [])
            logger.info(f"Terrain features loaded: {len(terrain_features)} from site profile")

            # -------------------------------------------------------------- #
            # 6. Load knowledge items
            # -------------------------------------------------------------- #
            from db.models import KnowledgeItem
            import sqlalchemy
            ki_result = await db.execute(
                sqlalchemy.select(KnowledgeItem).where(KnowledgeItem.site_id == site_db_id).limit(50)
            )
            knowledge_items = ki_result.scalars().all()
            logger.info(f"Knowledge items loaded: {len(knowledge_items)} from DB")

            # -------------------------------------------------------------- #
            # 7. Load recent flight segments
            # -------------------------------------------------------------- #
            from db.models import FlightSegment, HistoricalFlightTrack
            tracks_result = await db.execute(
                sqlalchemy.select(HistoricalFlightTrack.id)
                .where(HistoricalFlightTrack.site_id == site_db_id)
                .limit(20)
            )
            track_ids = [row[0] for row in tracks_result.fetchall()]

            flight_segments = []
            if track_ids:
                segs_result = await db.execute(
                    sqlalchemy.select(FlightSegment)
                    .where(
                        FlightSegment.track_id.in_(track_ids),
                        FlightSegment.segment_type == "climb",
                    )
                    .limit(200)
                )
                flight_segments = segs_result.scalars().all()
            logger.info(f"Flight segments loaded: {len(flight_segments)} climbs")

            # -------------------------------------------------------------- #
            # 8. Determine wind context from forecast
            # -------------------------------------------------------------- #
            # Use the midday hour (12:00) as representative wind
            midday_hour = forecast.get_hour(12) or (forecast.hourly[len(forecast.hourly)//2] if forecast.hourly else None)
            wind_dir_deg = getattr(midday_hour, "wind_dir_deg", 225.0) if midday_hour else 225.0
            wind_speed_kmh = getattr(midday_hour, "wind_speed_kmh", 15.0) if midday_hour else 15.0
            cloud_cover = getattr(midday_hour, "cloud_cover_pct", 30.0) if midday_hour else 30.0

            # Determine season
            month = target_date.month
            season = (
                "spring" if 3 <= month <= 5
                else "summer" if 6 <= month <= 8
                else "fall" if 9 <= month <= 11
                else "winter"
            )

            context = {
                "site_profile": site_profile,
                "forecast": forecast,
                "cloud_observation": cloud_obs,
                "terrain_features": terrain_features,
                "knowledge_items": knowledge_items,
                "flight_segments": flight_segments,
                "wind_dir_deg": wind_dir_deg,
                "wind_speed_kmh": wind_speed_kmh,
                "time_of_day_hour": 12,  # Planning for midday window
                "season": season,
                "cloud_condition": "partly_cloudy" if 20 <= cloud_cover <= 60 else "clear" if cloud_cover < 20 else "overcast",
            }

            # -------------------------------------------------------------- #
            # 9. Run all primary agents concurrently
            # -------------------------------------------------------------- #
            from agents.weather_agent import WeatherAgent
            from agents.terrain_agent import TerrainAgent
            from agents.cloud_agent import CloudAgent
            from agents.local_knowledge_agent import LocalKnowledgeAgent
            from agents.flight_history_agent import FlightHistoryAgent

            logger.info("Running primary agents concurrently...")
            results = await asyncio.gather(
                WeatherAgent().run(context),
                TerrainAgent().run(context),
                CloudAgent().run(context),
                LocalKnowledgeAgent().run(context),
                FlightHistoryAgent().run(context),
                return_exceptions=True,
            )

            all_claims: list[Claim] = []
            agent_names = ["weather_agent", "terrain_agent", "cloud_agent", "local_knowledge_agent", "flight_history_agent"]
            for agent_name, result in zip(agent_names, results):
                if isinstance(result, Exception):
                    logger.error(f"Agent {agent_name} failed: {result}")
                else:
                    logger.info(f"Agent {agent_name}: {len(result)} claims")
                    all_claims.extend(result)

            logger.info(f"All primary agents complete: {len(all_claims)} total claims")

            # -------------------------------------------------------------- #
            # 10. Run RiskAgent
            # -------------------------------------------------------------- #
            from agents.risk_agent import RiskAgent
            risk_context = {**context, "prior_claims": all_claims}
            risk_claims = await RiskAgent().run(risk_context)
            all_claims.extend(risk_claims)
            logger.info(f"RiskAgent produced {len(risk_claims)} additional claims")

            # -------------------------------------------------------------- #
            # 11. Run NegotiationAgent
            # -------------------------------------------------------------- #
            result = await NegotiationAgent().arbitrate(all_claims)
            result.session_id = session_record.id
            logger.info(f"Negotiation complete: {len(result.ranked_launch_windows)} windows, "
                       f"{len(result.ranked_trigger_zones)} trigger zones")

            # -------------------------------------------------------------- #
            # 12. Store claims in DB
            # -------------------------------------------------------------- #
            from db.models import AgentClaim, Recommendation
            for claim in all_claims:
                db_claim = AgentClaim(
                    session_id=session_record.id,
                    agent_name=claim.agent_name,
                    claim_type=claim.claim_type.value if hasattr(claim.claim_type, "value") else str(claim.claim_type),
                    claim_text=claim.claim_text[:2000] if claim.claim_text else "",
                    confidence=claim.confidence,
                    evidence_json=json.dumps([
                        {"source": e.source, "description": e.description, "data_ref": e.data_ref}
                        for e in claim.evidence
                    ]),
                    assumptions_json=json.dumps(claim.assumptions),
                    spatial_scope_json=json.dumps({
                        "feature_name": claim.spatial_scope.feature_name,
                        "geojson": claim.spatial_scope.geojson,
                        "elevation_range_m": list(claim.spatial_scope.elevation_range_m) if claim.spatial_scope.elevation_range_m else None,
                    }) if claim.spatial_scope else None,
                    temporal_validity_json=json.dumps({
                        "valid_from_hour": claim.temporal_validity.valid_from_hour,
                        "valid_to_hour": claim.temporal_validity.valid_to_hour,
                        "seasonal_constraint": claim.temporal_validity.seasonal_constraint,
                        "notes": claim.temporal_validity.notes,
                    }) if claim.temporal_validity else None,
                )
                db.add(db_claim)

            # Store recommendations
            rank = 1
            for window in result.ranked_launch_windows:
                db.add(Recommendation(
                    session_id=session_record.id,
                    rec_type="launch_window",
                    rank=rank,
                    title=window.title,
                    description=window.description,
                    confidence=window.confidence,
                    uncertainty_note=window.uncertainty_note,
                    evidence_summary_json=json.dumps(window.evidence_summary),
                ))
                rank += 1

            for zone in result.ranked_trigger_zones:
                db.add(Recommendation(
                    session_id=session_record.id,
                    rec_type="trigger_zone",
                    rank=rank,
                    title=zone.title,
                    description=zone.description,
                    confidence=zone.confidence,
                    uncertainty_note=zone.uncertainty_note,
                    evidence_summary_json=json.dumps(zone.evidence_summary),
                    spatial_ref_json=json.dumps({"feature_name": zone.feature_name}) if zone.feature_name else None,
                ))
                rank += 1

            for corridor in result.ranked_ridge_corridors:
                db.add(Recommendation(
                    session_id=session_record.id,
                    rec_type="ridge_corridor",
                    rank=rank,
                    title=corridor.title,
                    description=corridor.description,
                    confidence=corridor.confidence,
                    uncertainty_note=corridor.uncertainty_note,
                    evidence_summary_json=json.dumps(corridor.evidence_summary),
                ))
                rank += 1

            for caution in result.caution_zones:
                db.add(Recommendation(
                    session_id=session_record.id,
                    rec_type="caution_zone",
                    rank=rank,
                    title=caution.title,
                    description=caution.description,
                    confidence=caution.confidence,
                    uncertainty_note="",
                ))
                rank += 1

            # Update session status
            session_record.status = "complete"
            session_record.outputs_json = json.dumps(result.to_dict())
            await db.flush()

            duration_s = (datetime.now(tz=timezone.utc) - session_start).total_seconds()
            logger.info(f"Planning session {session_record.id} complete in {duration_s:.1f}s")

            return result

        except Exception as e:
            logger.error(f"Planning session failed: {e}")
            session_record.status = "failed"
            await db.flush()
            raise
