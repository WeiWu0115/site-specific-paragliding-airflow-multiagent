"""
Abstract base class and data structures for weather providers.

All weather providers must implement WeatherProvider.fetch_forecast() and
return a WeatherForecast containing a list of WeatherHour objects.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import ClassVar


@dataclass
class WeatherHour:
    """A single hourly weather observation or forecast."""
    time: datetime
    temp_c: float
    dewpoint_c: float
    humidity_pct: float
    wind_speed_kmh: float
    wind_dir_deg: float
    pressure_hpa: float
    cloud_cover_pct: float
    precipitation_mm: float
    weather_code: int  # WMO weather interpretation code


@dataclass
class SurfaceSummary:
    """Summary statistics for the surface forecast period."""
    max_temp_c: float
    min_temp_c: float
    avg_wind_kmh: float
    peak_wind_kmh: float
    dominant_wind_dir_deg: float
    avg_cloud_cover_pct: float
    total_precipitation_mm: float
    best_flying_hour: int | None = None  # Local hour with best thermal index


@dataclass
class WeatherForecast:
    """Full weather forecast for a location over a time period."""
    hourly: list[WeatherHour] = field(default_factory=list)
    surface_summary: SurfaceSummary | None = None
    provider: str = ""
    lat: float = 0.0
    lon: float = 0.0
    fetched_at: datetime = field(default_factory=datetime.utcnow)

    def get_hour(self, hour: int) -> WeatherHour | None:
        """Return the first WeatherHour where time.hour == hour, or None."""
        for h in self.hourly:
            if hasattr(h.time, "hour") and h.time.hour == hour:
                return h
        return None


class WeatherProvider(ABC):
    """
    Abstract base class for all weather data providers.

    Implementations must be safe to call concurrently. Errors should be
    raised as informative exceptions rather than returning partial data.
    """

    # Provider identifier string
    provider_id: ClassVar[str] = "base"

    @abstractmethod
    async def fetch_forecast(
        self,
        lat: float,
        lon: float,
        hours_ahead: int = 48,
    ) -> WeatherForecast:
        """
        Fetch a weather forecast for the given location.

        Args:
            lat: Latitude in decimal degrees
            lon: Longitude in decimal degrees
            hours_ahead: Number of hours to forecast (default 48)

        Returns:
            WeatherForecast with hourly data

        Raises:
            httpx.HTTPError: if network request fails
            ValueError: if response is malformed
        """
        ...


# ---------------------------------------------------------------------------
# Provider registry
# ---------------------------------------------------------------------------

_PROVIDER_REGISTRY: dict[str, type[WeatherProvider]] = {}


def register_provider(cls: type[WeatherProvider]) -> type[WeatherProvider]:
    """Class decorator to register a WeatherProvider implementation."""
    _PROVIDER_REGISTRY[cls.provider_id] = cls
    return cls


def get_provider(provider_id: str) -> type[WeatherProvider]:
    """Return registered WeatherProvider class by ID."""
    if provider_id not in _PROVIDER_REGISTRY:
        raise ValueError(
            f"Unknown weather provider: '{provider_id}'. "
            f"Available: {list(_PROVIDER_REGISTRY.keys())}"
        )
    return _PROVIDER_REGISTRY[provider_id]
