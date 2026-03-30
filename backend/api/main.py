"""
FastAPI application entry point for paraglide-backend.

Mounts all API routers, configures CORS, registers startup/shutdown events,
and exposes a /health endpoint. All outputs are advisory only.
"""

import json
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from config.settings import get_settings
from api.routes import agents, clouds, forecast, knowledge, planning, replay, site, terrain, tracks, unity

ADVISORY_DISCLAIMER = (
    "All outputs from this API are advisory only. Paragliding is a high-risk activity. "
    "Conditions change rapidly and this system cannot observe actual air movement. "
    "Always rely on your own judgment, local site expertise, and direct observation. "
    "Do not use this system as a safety instrument."
)

tags_metadata = [
    {"name": "site", "description": "Site profile, launches, landings, and terrain configuration"},
    {"name": "forecast", "description": "Weather forecast data fetched from configured provider"},
    {"name": "terrain", "description": "Terrain feature analysis and spatial data"},
    {"name": "clouds", "description": "Cloud observation data"},
    {"name": "planning", "description": "Full multi-agent planning session execution"},
    {"name": "agents", "description": "Individual agent execution and claim retrieval"},
    {"name": "knowledge", "description": "Expert knowledge import and retrieval"},
    {"name": "tracks", "description": "Historical flight track import and segment analysis"},
    {"name": "replay", "description": "Historical flight replay with agent annotations"},
    {"name": "unity", "description": "Structured overlay payloads for Unity 3D visualization"},
]

app = FastAPI(
    title="Paragliding Airflow Planning API",
    description=(
        "Site-specific multi-agent airflow sensemaking system for paragliding pre-flight planning. "
        "Combines weather forecasts, terrain analysis, cloud observations, local expert knowledge, "
        "and historical flight data to produce explainable, uncertainty-aware recommendations.\n\n"
        f"**ADVISORY DISCLAIMER**: {ADVISORY_DISCLAIMER}"
    ),
    version="0.1.0",
    openapi_tags=tags_metadata,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ---------------------------------------------------------------------------
# CORS — permissive for local development; restrict in production
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(site.router, prefix="/site", tags=["site"])
app.include_router(forecast.router, prefix="/forecast", tags=["forecast"])
app.include_router(terrain.router, prefix="/terrain", tags=["terrain"])
app.include_router(clouds.router, prefix="/clouds", tags=["clouds"])
app.include_router(planning.router, prefix="/planning", tags=["planning"])
app.include_router(agents.router, prefix="/agents", tags=["agents"])
app.include_router(knowledge.router, prefix="/knowledge", tags=["knowledge"])
app.include_router(tracks.router, prefix="/tracks", tags=["tracks"])
app.include_router(replay.router, prefix="/replay", tags=["replay"])
app.include_router(unity.router, prefix="/unity", tags=["unity"])


# ---------------------------------------------------------------------------
# Startup / Shutdown
# ---------------------------------------------------------------------------

@app.on_event("startup")
async def startup_event() -> None:
    settings = get_settings()
    logger.info("=" * 60)
    logger.info("Paragliding Airflow Planning API starting up")
    logger.info(f"Site: {settings.site_id}")
    logger.info(f"Weather provider: {settings.weather_provider}")
    logger.info(f"Cloud provider: {settings.cloud_provider}")
    logger.info(f"Log level: {settings.log_level}")

    # Attempt to load and validate site profile
    try:
        with open(settings.site_profile_path) as f:
            profile = json.load(f)
        logger.info(f"Site profile loaded: {profile['name']}")
        logger.info(f"  Location: {profile['location']['lat']}N, {profile['location']['lon']}W")
        logger.info(f"  Launches: {len(profile.get('launches', []))}")
        logger.info(f"  Terrain features: {len(profile.get('terrain_features', []))}")
        logger.info(f"  Known heuristics: {len(profile.get('known_heuristics', []))}")
    except FileNotFoundError:
        logger.warning(f"Site profile not found at: {settings.site_profile_path}")
    except Exception as e:
        logger.error(f"Failed to load site profile: {e}")

    # Auto-seed if database is empty
    try:
        from db.session import get_session_factory
        from db.models import SiteProfile
        from sqlalchemy import select

        session_factory = get_session_factory()
        async with session_factory() as session:
            result = await session.execute(
                select(SiteProfile).where(SiteProfile.slug == settings.site_id)
            )
            if result.scalar_one_or_none() is None:
                logger.info("Database empty — running auto-seed...")
                # Import and run seed logic inline
                from services.seed import seed
                with open(settings.site_profile_path) as f:
                    profile_data = json.load(f)
                await seed(session, profile_data)
                await session.commit()
                logger.info("Auto-seed complete!")
            else:
                logger.info(f"Site '{settings.site_id}' already seeded.")
    except Exception as e:
        logger.error(f"Auto-seed failed: {e}")

    logger.info(f"API listening on {settings.api_host}:{settings.api_port}")
    logger.warning(f"ADVISORY: {ADVISORY_DISCLAIMER}")
    logger.info("=" * 60)


@app.on_event("shutdown")
async def shutdown_event() -> None:
    logger.info("Paragliding Airflow Planning API shutting down")


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/health", tags=["system"])
async def health() -> dict:
    """Basic health check endpoint."""
    settings = get_settings()
    return {
        "status": "ok",
        "site_id": settings.site_id,
        "weather_provider": settings.weather_provider,
        "cloud_provider": settings.cloud_provider,
        "advisory": ADVISORY_DISCLAIMER,
    }
