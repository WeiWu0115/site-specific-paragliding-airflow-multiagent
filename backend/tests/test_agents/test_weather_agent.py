"""
Tests for WeatherAgent in paraglide-backend.
"""

import pytest
from datetime import datetime, timezone

from agents.base import ClaimType
from agents.weather_agent import WeatherAgent
from data_ingestion.weather.provider_base import WeatherHour


def _make_hour(
    hour: int = 12,
    temp_c: float = 28.0,
    dewpoint_c: float = 8.0,
    wind_speed_kmh: float = 15.0,
    wind_dir_deg: float = 225.0,
    cloud_cover_pct: float = 30.0,
    pressure_hpa: float = 1013.0,
) -> WeatherHour:
    t = datetime(2024, 7, 15, hour, 0, 0, tzinfo=timezone.utc)
    return WeatherHour(
        time=t,
        temp_c=temp_c,
        dewpoint_c=dewpoint_c,
        humidity_pct=40.0,
        wind_speed_kmh=wind_speed_kmh,
        wind_dir_deg=wind_dir_deg,
        pressure_hpa=pressure_hpa,
        cloud_cover_pct=cloud_cover_pct,
        precipitation_mm=0.0,
        weather_code=1,
    )


@pytest.fixture
def agent() -> WeatherAgent:
    return WeatherAgent()


@pytest.fixture
def good_forecast():
    """A 12-hour forecast with ideal thermal conditions at midday."""
    from data_ingestion.weather.provider_base import WeatherForecast
    hours = [
        _make_hour(h, temp_c=18 + h, dewpoint_c=8.0, wind_speed_kmh=8 + h * 0.5, cloud_cover_pct=10 + h * 2)
        for h in range(6, 18)
    ]
    return WeatherForecast(hourly=hours, provider="test")


@pytest.mark.asyncio
async def test_weather_agent_generates_launch_window_claims(agent, good_forecast):
    """Agent should identify at least one launch window in a good forecast."""
    context = {"forecast": good_forecast, "site_profile": {"location": {"lat": 35.5, "lon": -118.2}}}
    claims = await agent.run(context)
    launch_windows = [c for c in claims if c.claim_type == ClaimType.LAUNCH_WINDOW]
    assert len(launch_windows) >= 1, "Expected at least one launch window claim"


@pytest.mark.asyncio
async def test_weather_agent_generates_caution_in_high_wind(agent):
    """Agent should produce CAUTION claims when wind exceeds 25 km/h."""
    from data_ingestion.weather.provider_base import WeatherForecast
    high_wind_hours = [
        _make_hour(h, wind_speed_kmh=30.0) for h in range(8, 16)
    ]
    forecast = WeatherForecast(hourly=high_wind_hours, provider="test")
    context = {"forecast": forecast}
    claims = await agent.run(context)
    cautions = [c for c in claims if c.claim_type == ClaimType.CAUTION]
    assert len(cautions) >= 1, "Expected high wind caution claims"


@pytest.mark.asyncio
async def test_weather_agent_confidence_range(agent, good_forecast):
    """All confidence values must be in [0.0, 1.0]."""
    context = {"forecast": good_forecast}
    claims = await agent.run(context)
    for claim in claims:
        assert 0.0 <= claim.confidence <= 1.0, f"Confidence out of range: {claim.confidence}"


def test_thermal_index_score_plausible_values(agent):
    """score_hour() should return values in [0, 1] for plausible inputs."""
    test_cases = [
        _make_hour(6, temp_c=18, dewpoint_c=15, wind_speed_kmh=5, cloud_cover_pct=5),     # Morning, light
        _make_hour(12, temp_c=32, dewpoint_c=8, wind_speed_kmh=15, cloud_cover_pct=30),   # Peak midday
        _make_hour(14, temp_c=34, dewpoint_c=7, wind_speed_kmh=18, cloud_cover_pct=40),   # Afternoon ideal
        _make_hour(17, temp_c=28, dewpoint_c=12, wind_speed_kmh=20, cloud_cover_pct=55),  # Easing
        _make_hour(8, temp_c=20, dewpoint_c=16, wind_speed_kmh=32, cloud_cover_pct=80),   # High wind + overcast
    ]
    for hour_data in test_cases:
        score = agent.score_hour(hour_data)
        assert 0.0 <= score <= 1.0, f"Score {score} out of range for {hour_data}"


def test_thermal_index_peak_at_midday(agent):
    """Midday hours should score higher than early morning in otherwise identical conditions."""
    morning = _make_hour(6, temp_c=22, dewpoint_c=8, wind_speed_kmh=14, cloud_cover_pct=25)
    midday = _make_hour(13, temp_c=22, dewpoint_c=8, wind_speed_kmh=14, cloud_cover_pct=25)
    score_morning = agent.score_hour(morning)
    score_midday = agent.score_hour(midday)
    assert score_midday > score_morning, "Midday should score higher than morning"


@pytest.mark.asyncio
async def test_weather_agent_empty_forecast_returns_empty_claims(agent):
    """Agent should return empty list when forecast has no hourly data."""
    from data_ingestion.weather.provider_base import WeatherForecast
    empty_forecast = WeatherForecast(hourly=[], provider="test")
    context = {"forecast": empty_forecast}
    claims = await agent.run(context)
    assert claims == [], "Empty forecast should produce no claims"
