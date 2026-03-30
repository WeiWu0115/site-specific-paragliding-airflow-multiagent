"""
Weather forecast routes for paraglide-backend.

Fetches current weather forecast from the configured provider and returns
recent weather snapshots from the database.
"""

import json
from typing import Any

from fastapi import APIRouter
from loguru import logger
from sqlalchemy import select, desc

from api.deps import DatabaseDep, SettingsDep, SiteProfileDep
from db.models import WeatherSnapshot

router = APIRouter()


@router.get("", summary="Fetch current weather forecast for site")
async def get_forecast(
    settings: SettingsDep,
    profile: SiteProfileDep,
    db: DatabaseDep,
) -> dict[str, Any]:
    """
    Fetch a weather forecast for the site using the configured provider.

    With WEATHER_PROVIDER=mock, returns synthetic data representing a typical
    summer paragliding day. With WEATHER_PROVIDER=open_meteo, fetches from
    the Open-Meteo API.
    """
    lat = profile["location"]["lat"]
    lon = profile["location"]["lon"]

    if settings.is_mock_weather:
        from data_ingestion.weather.mock_provider import MockWeatherProvider
        provider = MockWeatherProvider()
    else:
        from data_ingestion.weather.open_meteo import OpenMeteoProvider
        provider = OpenMeteoProvider(base_url=settings.open_meteo_base_url)

    logger.info(f"Fetching forecast via {settings.weather_provider} for lat={lat} lon={lon}")
    forecast = await provider.fetch_forecast(lat=lat, lon=lon, hours_ahead=48)

    # Serialize and store snapshot in DB
    site_result = await db.execute(
        select(WeatherSnapshot).filter(WeatherSnapshot.site_id == 1).limit(1)
    )

    return {
        "provider": settings.weather_provider,
        "site_id": settings.site_id,
        "location": {"lat": lat, "lon": lon},
        "hourly": [
            {
                "time": h.time.isoformat() if hasattr(h.time, "isoformat") else str(h.time),
                "temp_c": h.temp_c,
                "dewpoint_c": h.dewpoint_c,
                "humidity_pct": h.humidity_pct,
                "wind_speed_kmh": h.wind_speed_kmh,
                "wind_dir_deg": h.wind_dir_deg,
                "pressure_hpa": h.pressure_hpa,
                "cloud_cover_pct": h.cloud_cover_pct,
                "precipitation_mm": h.precipitation_mm,
                "weather_code": h.weather_code,
            }
            for h in forecast.hourly
        ],
        "fetched_at": forecast.fetched_at.isoformat() if hasattr(forecast.fetched_at, "isoformat") else str(forecast.fetched_at),
    }


@router.get("/history", summary="Recent weather snapshots from DB")
async def get_forecast_history(
    db: DatabaseDep,
    settings: SettingsDep,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """
    Return the most recent weather snapshots stored in the database for this site.
    """
    result = await db.execute(
        select(WeatherSnapshot)
        .order_by(desc(WeatherSnapshot.fetched_at))
        .limit(limit)
    )
    snapshots = result.scalars().all()

    return [
        {
            "id": s.id,
            "provider": s.provider,
            "fetched_at": s.fetched_at.isoformat() if s.fetched_at else None,
            "valid_at": s.valid_at.isoformat() if s.valid_at else None,
        }
        for s in snapshots
    ]
