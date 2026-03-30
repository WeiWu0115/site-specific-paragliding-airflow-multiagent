"""
Open-Meteo weather provider for paraglide-backend.

Fetches real hourly forecasts from the Open-Meteo free weather API.
No API key required. Returns WeatherForecast in standard format.
"""

from datetime import datetime, timezone

import httpx
from loguru import logger

from data_ingestion.weather.provider_base import (
    SurfaceSummary,
    WeatherForecast,
    WeatherHour,
    WeatherProvider,
    register_provider,
)

# Open-Meteo WMO weather code to simple description
WMO_CODES = {
    0: "clear",
    1: "mostly_clear",
    2: "partly_cloudy",
    3: "overcast",
    45: "fog",
    48: "rime_fog",
    51: "light_drizzle",
    61: "light_rain",
    80: "light_showers",
    95: "thunderstorm",
}


@register_provider
class OpenMeteoProvider(WeatherProvider):
    """
    Fetches 48-hour hourly forecasts from the Open-Meteo API.

    Open-Meteo API docs: https://open-meteo.com/en/docs
    No authentication required. Rate limit: ~10,000 requests/day.
    """

    provider_id = "open_meteo"

    def __init__(self, base_url: str = "https://api.open-meteo.com/v1") -> None:
        self.base_url = base_url.rstrip("/")

    async def fetch_forecast(
        self,
        lat: float,
        lon: float,
        hours_ahead: int = 48,
    ) -> WeatherForecast:
        """
        Fetch hourly forecast from Open-Meteo API.

        Parameters requested:
        - temperature_2m: Air temperature at 2m [°C]
        - dewpoint_2m: Dewpoint temperature at 2m [°C]
        - relativehumidity_2m: Relative humidity at 2m [%]
        - windspeed_10m: Wind speed at 10m [km/h]
        - winddirection_10m: Wind direction at 10m [°]
        - surface_pressure: Surface pressure [hPa]
        - cloudcover: Total cloud cover [%]
        - precipitation: Precipitation [mm]
        - weathercode: WMO weather interpretation code
        """
        params = {
            "latitude": lat,
            "longitude": lon,
            "hourly": ",".join([
                "temperature_2m",
                "dewpoint_2m",
                "relativehumidity_2m",
                "windspeed_10m",
                "winddirection_10m",
                "surface_pressure",
                "cloudcover",
                "precipitation",
                "weathercode",
            ]),
            "forecast_days": min(7, max(1, hours_ahead // 24 + 1)),
            "timezone": "UTC",
            "wind_speed_unit": "kmh",
        }

        url = f"{self.base_url}/forecast"
        logger.info(f"Fetching Open-Meteo forecast: lat={lat}, lon={lon}")

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()
            except httpx.HTTPStatusError as e:
                logger.error(f"Open-Meteo HTTP error: {e.response.status_code} {e.response.text}")
                raise
            except httpx.RequestError as e:
                logger.error(f"Open-Meteo network error: {e}")
                raise

        return self._parse_response(data, lat, lon, hours_ahead)

    def _parse_response(
        self,
        data: dict,
        lat: float,
        lon: float,
        hours_ahead: int,
    ) -> WeatherForecast:
        """Parse Open-Meteo JSON response into WeatherForecast."""
        hourly = data.get("hourly", {})

        times = hourly.get("time", [])
        temps = hourly.get("temperature_2m", [])
        dewpoints = hourly.get("dewpoint_2m", [])
        humidities = hourly.get("relativehumidity_2m", [])
        windspeeds = hourly.get("windspeed_10m", [])
        windirs = hourly.get("winddirection_10m", [])
        pressures = hourly.get("surface_pressure", [])
        cloudcovers = hourly.get("cloudcover", [])
        precipitations = hourly.get("precipitation", [])
        weathercodes = hourly.get("weathercode", [])

        if not times:
            raise ValueError("Open-Meteo response missing hourly time data")

        hours: list[WeatherHour] = []
        for i, time_str in enumerate(times[:hours_ahead]):
            try:
                # Parse ISO 8601 time string (Open-Meteo returns UTC without 'Z')
                t = datetime.fromisoformat(time_str).replace(tzinfo=timezone.utc)
            except ValueError:
                logger.warning(f"Could not parse time: {time_str}")
                continue

            hour = WeatherHour(
                time=t,
                temp_c=float(temps[i] if i < len(temps) and temps[i] is not None else 20.0),
                dewpoint_c=float(dewpoints[i] if i < len(dewpoints) and dewpoints[i] is not None else 8.0),
                humidity_pct=float(humidities[i] if i < len(humidities) and humidities[i] is not None else 40.0),
                wind_speed_kmh=float(windspeeds[i] if i < len(windspeeds) and windspeeds[i] is not None else 10.0),
                wind_dir_deg=float(windirs[i] if i < len(windirs) and windirs[i] is not None else 225.0),
                pressure_hpa=float(pressures[i] if i < len(pressures) and pressures[i] is not None else 1013.0),
                cloud_cover_pct=float(cloudcovers[i] if i < len(cloudcovers) and cloudcovers[i] is not None else 30.0),
                precipitation_mm=float(precipitations[i] if i < len(precipitations) and precipitations[i] is not None else 0.0),
                weather_code=int(weathercodes[i] if i < len(weathercodes) and weathercodes[i] is not None else 0),
            )
            hours.append(hour)

        # Build surface summary
        surface = None
        if hours:
            temps_c = [h.temp_c for h in hours]
            winds = [h.wind_speed_kmh for h in hours]
            clouds = [h.cloud_cover_pct for h in hours]
            surface = SurfaceSummary(
                max_temp_c=max(temps_c),
                min_temp_c=min(temps_c),
                avg_wind_kmh=sum(winds) / len(winds),
                peak_wind_kmh=max(winds),
                dominant_wind_dir_deg=hours[len(hours) // 2].wind_dir_deg,
                avg_cloud_cover_pct=sum(clouds) / len(clouds),
                total_precipitation_mm=sum(h.precipitation_mm for h in hours),
            )

        logger.info(f"Open-Meteo: parsed {len(hours)} hourly records for lat={lat} lon={lon}")

        return WeatherForecast(
            hourly=hours,
            surface_summary=surface,
            provider="open_meteo",
            lat=lat,
            lon=lon,
        )
