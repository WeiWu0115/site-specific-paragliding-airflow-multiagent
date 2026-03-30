"""
pytest fixtures for paraglide-backend tests.

Provides: mock_weather_data, eagle_ridge_profile, sample_claims, async_client.
"""

import json
import os
from datetime import datetime, timezone
from typing import AsyncGenerator

import pytest
import pytest_asyncio

from agents.base import Claim, ClaimType, Evidence, SpatialScope, TemporalValidity


@pytest.fixture
def mock_weather_data():
    """Return a WeatherForecast from the mock provider (synchronous)."""
    import asyncio
    from data_ingestion.weather.mock_provider import MockWeatherProvider
    provider = MockWeatherProvider()
    forecast = asyncio.get_event_loop().run_until_complete(
        provider.fetch_forecast(lat=35.492, lon=-118.187, hours_ahead=24)
    )
    return forecast


@pytest.fixture
def eagle_ridge_profile():
    """Load and return the eagle_ridge.json site profile."""
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    profile_path = os.path.join(base, "config", "site_profiles", "eagle_ridge.json")
    with open(profile_path) as f:
        return json.load(f)


@pytest.fixture
def sample_claims():
    """Return a list of sample Claim objects for testing negotiation."""
    claims = [
        Claim(
            agent_name="weather_agent",
            claim_type=ClaimType.LAUNCH_WINDOW,
            claim_text="Launch window 10:00-14:00 UTC: thermal index avg 0.62",
            confidence=0.72,
            evidence=[
                Evidence(
                    source="weather_forecast_hourly",
                    description="4-hour window with thermal index > 0.35",
                    data_ref={"avg_score": 0.62, "window_hours": 4},
                )
            ],
            temporal_validity=TemporalValidity(valid_from_hour=10, valid_to_hour=14),
        ),
        Claim(
            agent_name="terrain_agent",
            claim_type=ClaimType.RIDGE_LIFT,
            claim_text="Eagle Ridge Main: ridge lift expected in SW wind at 15 km/h",
            confidence=0.85,
            evidence=[
                Evidence(
                    source="terrain_agent_vector_analysis",
                    description="Wind-to-ridge dot product 0.71",
                    data_ref={"dot_product": 0.71, "wind_dir_deg": 225},
                )
            ],
            spatial_scope=SpatialScope(feature_name="Eagle Ridge Main"),
        ),
        Claim(
            agent_name="terrain_agent",
            claim_type=ClaimType.SINK_ZONE,
            claim_text="Eagle Ridge Main LEE SIDE: sink zone in NE lee",
            confidence=0.70,
            evidence=[
                Evidence(
                    source="terrain_agent_vector_analysis",
                    description="Lee side detected",
                    data_ref={"dot_product": -0.62},
                )
            ],
            spatial_scope=SpatialScope(feature_name="Eagle Ridge Main"),
        ),
        Claim(
            agent_name="local_knowledge_agent",
            claim_type=ClaimType.THERMAL_ZONE,
            claim_text="Tehachapi Creek riverbed triggers first thermal on sunny mornings",
            confidence=0.80,
            evidence=[
                Evidence(
                    source="local_knowledge_heuristic_h01",
                    description="Site heuristic: match score 0.90",
                    data_ref={"heuristic_id": "h01", "match_score": 0.90},
                )
            ],
            spatial_scope=SpatialScope(feature_name="Tehachapi Creek Drainage"),
        ),
        Claim(
            agent_name="risk_agent",
            claim_type=ClaimType.CAUTION,
            claim_text="AGENT DISAGREEMENT: terrain_agent says ridge_lift but terrain_agent says sink_zone for Eagle Ridge Main",
            confidence=0.75,
            evidence=[
                Evidence(
                    source="conflict_detection",
                    description="Conflicting claims on same feature",
                    data_ref={"region": "Eagle Ridge Main"},
                )
            ],
            spatial_scope=SpatialScope(feature_name="Eagle Ridge Main"),
        ),
    ]
    return claims


@pytest_asyncio.fixture
async def async_client():
    """Return an async httpx test client for FastAPI testing."""
    from httpx import AsyncClient, ASGITransport
    from api.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        yield client
