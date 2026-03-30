"""
Application settings for paraglide-backend.

Uses Pydantic BaseSettings to read configuration from environment variables
and .env file. Provides a cached singleton via get_settings().
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All application configuration, read from environment variables or .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Database ---
    database_url: str = Field(
        default="postgresql+asyncpg://paraglide:paraglide@localhost:5432/paraglide_db",
        description="Async PostgreSQL connection URL",
    )

    # --- Redis ---
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL",
    )

    # --- Weather Provider ---
    weather_provider: Literal["mock", "open_meteo"] = Field(
        default="mock",
        description="Weather data provider. 'mock' uses synthetic data; 'open_meteo' uses real API.",
    )
    open_meteo_base_url: str = Field(
        default="https://api.open-meteo.com/v1",
        description="Base URL for Open-Meteo API",
    )

    # --- Cloud Provider ---
    cloud_provider: Literal["mock"] = Field(
        default="mock",
        description="Cloud observation provider.",
    )

    # --- Site ---
    site_id: str = Field(
        default="eagle_ridge",
        description="The site slug used to load site profile JSON from config/site_profiles/",
    )

    # --- Logging ---
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(
        default="INFO",
        description="Logging verbosity level",
    )

    # --- API Server ---
    api_host: str = Field(default="0.0.0.0", description="Uvicorn bind host")
    api_port: int = Field(default=8000, description="Uvicorn bind port")

    # --- Frontend ---
    next_public_api_url: str = Field(
        default="http://localhost:8000",
        description="Public-facing API URL exposed to Next.js frontend",
    )

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        if not v.startswith("postgresql"):
            raise ValueError("DATABASE_URL must be a PostgreSQL URL")
        return v

    @property
    def is_mock_weather(self) -> bool:
        """True when using synthetic weather data instead of a real provider."""
        return self.weather_provider == "mock"

    @property
    def is_mock_cloud(self) -> bool:
        """True when using synthetic cloud data instead of a real provider."""
        return self.cloud_provider == "mock"

    @property
    def site_profile_path(self) -> str:
        """Absolute-ish path to the site profile JSON for the configured site_id."""
        import os
        base = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(base, "site_profiles", f"{self.site_id}.json")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached application settings singleton."""
    return Settings()
