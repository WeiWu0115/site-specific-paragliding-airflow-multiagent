"""
MockWeatherProvider for paraglide-backend.

Generates a realistic synthetic 48-hour forecast for development and testing.
Simulates a typical summer paragliding day at Eagle Ridge:
- Morning calm, cool, high humidity
- Midday heating, dry air, ideal thermal wind 12-18 km/h
- Afternoon peak, stronger wind, cumulus development
- Evening cooling, wind drops, glass-off potential

Values are meteorologically consistent (temperature inversion, dewpoint spread
increasing through morning, pressure slight diurnal variation).
"""

import math
from datetime import datetime, timedelta, timezone

from loguru import logger

from data_ingestion.weather.provider_base import (
    SurfaceSummary,
    WeatherForecast,
    WeatherHour,
    WeatherProvider,
    register_provider,
)


def _gaussian(x: float, mu: float, sigma: float) -> float:
    """Standard Gaussian function."""
    return math.exp(-0.5 * ((x - mu) / sigma) ** 2)


@register_provider
class MockWeatherProvider(WeatherProvider):
    """
    Produces a synthetic weather forecast that mimics a typical summer
    paragliding day at Eagle Ridge Flying Site.

    The diurnal cycle is modeled with these characteristics:
    - Temperature: ~18°C at 06:00, peaks ~34°C at 14:00, drops to ~22°C by 21:00
    - Dewpoint: ~12°C morning, drops to ~7°C by noon (spread widens → drier)
    - Wind: ~6 km/h at 06:00, peaks ~18 km/h at 14:00, drops to ~8 km/h by 19:00
    - Wind direction: dominantly SW (225°), slight backing in afternoon
    - Cloud cover: 10% morning, rises to ~35% at 12:00, peaks ~55% at 15:00, drops to 20%
    - Pressure: gentle diurnal variation ~1015 hPa
    """

    provider_id = "mock"

    def __init__(self, seed: int | None = None) -> None:
        self.seed = seed  # For reproducibility (not currently used — deterministic)

    async def fetch_forecast(
        self,
        lat: float,
        lon: float,
        hours_ahead: int = 48,
    ) -> WeatherForecast:
        """
        Return a synthetic 48-hour forecast.

        The first 24 hours represent a classic thermal flying day.
        Hours 24-48 represent a slightly cooler, windier second day.
        """
        logger.info(f"MockWeatherProvider generating {hours_ahead}h synthetic forecast for lat={lat} lon={lon}")

        # Reference start: today at 00:00 UTC
        now = datetime.now(tz=timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

        hours: list[WeatherHour] = []
        for h in range(min(hours_ahead, 48)):
            t = now + timedelta(hours=h)
            # Day index (0=day1, 1=day2)
            day = h // 24
            hour_of_day = h % 24
            hour = self._generate_hour(t, hour_of_day, day)
            hours.append(hour)

        # Surface summary
        temps = [h.temp_c for h in hours[:24]]
        winds = [h.wind_speed_kmh for h in hours[:24]]
        clouds = [h.cloud_cover_pct for h in hours[:24]]

        surface = SurfaceSummary(
            max_temp_c=max(temps),
            min_temp_c=min(temps),
            avg_wind_kmh=sum(winds) / len(winds),
            peak_wind_kmh=max(winds),
            dominant_wind_dir_deg=225.0,
            avg_cloud_cover_pct=sum(clouds) / len(clouds),
            total_precipitation_mm=0.0,
            best_flying_hour=11,  # 11:00 UTC is typical thermal peak in summer
        )

        return WeatherForecast(
            hourly=hours,
            surface_summary=surface,
            provider="mock",
            lat=lat,
            lon=lon,
        )

    def _generate_hour(self, t: datetime, hour_of_day: int, day: int) -> WeatherHour:
        """Generate synthetic weather values for a single hour."""
        h = hour_of_day
        day_factor = 1.0 if day == 0 else 1.08  # Day 2 slightly stronger

        # --- Temperature (°C) ---
        # Diurnal: min ~18°C at 06:00, max ~34°C at 14:00
        temp_c = 18.0 + 16.0 * _gaussian(h, 14.0, 4.5) * day_factor
        # Night stays warm: add a floor
        if h < 6 or h > 21:
            temp_c = max(17.0, temp_c)

        # --- Dewpoint (°C) ---
        # Morning dew ~13°C, drops to ~6°C by afternoon (spread widens)
        dewpoint_c = 13.0 - 7.0 * _gaussian(h, 13.0, 4.0)
        dewpoint_c = min(dewpoint_c, temp_c - 1.0)  # Can't exceed temp

        # --- Humidity (%) ---
        # Derived from temp-dewpoint relationship (approximate)
        spread = max(0.1, temp_c - dewpoint_c)
        humidity_pct = max(15.0, min(95.0, 100.0 * math.exp(-spread / 18.0)))

        # --- Wind speed (km/h) ---
        # Calm morning, peak afternoon, drops evening
        wind_speed_kmh = 6.0 + 12.0 * _gaussian(h, 14.0, 4.0) * day_factor
        # Add slight random-looking variation via harmonic
        wind_speed_kmh += 1.5 * math.sin(h * 0.7)
        wind_speed_kmh = max(3.0, wind_speed_kmh)

        # --- Wind direction (degrees) ---
        # Predominantly SW (225°), drifts toward S (200°) in early morning,
        # backs slightly toward W (240°) in strong afternoon
        wind_dir_deg = 225.0 + 20.0 * math.sin(h * math.pi / 16.0) - 10.0 * _gaussian(h, 6.0, 3.0)

        # --- Pressure (hPa) ---
        # Gentle diurnal variation: max ~1016 at 10:00, min ~1013 at 22:00
        pressure_hpa = 1014.5 + 1.5 * math.cos((h - 10.0) * math.pi / 12.0)

        # --- Cloud cover (%) ---
        # Morning clear, builds midday with thermal activity, peaks ~15:00
        cloud_cover_pct = 8.0 + 47.0 * _gaussian(h, 14.5, 3.5)
        cloud_cover_pct = max(5.0, min(85.0, cloud_cover_pct))

        # --- Precipitation (mm) ---
        precipitation_mm = 0.0  # Dry summer day

        # --- WMO Weather code ---
        if cloud_cover_pct < 15:
            weather_code = 0  # Clear
        elif cloud_cover_pct < 35:
            weather_code = 1  # Mostly clear
        elif cloud_cover_pct < 60:
            weather_code = 2  # Partly cloudy
        else:
            weather_code = 3  # Overcast

        return WeatherHour(
            time=t,
            temp_c=round(temp_c, 1),
            dewpoint_c=round(dewpoint_c, 1),
            humidity_pct=round(humidity_pct, 0),
            wind_speed_kmh=round(wind_speed_kmh, 1),
            wind_dir_deg=round(wind_dir_deg, 0),
            pressure_hpa=round(pressure_hpa, 1),
            cloud_cover_pct=round(cloud_cover_pct, 0),
            precipitation_mm=precipitation_mm,
            weather_code=weather_code,
        )
