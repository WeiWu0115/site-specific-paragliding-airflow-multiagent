"""
FastAPI dependency injectors for paraglide-backend.

Provides reusable dependencies for database sessions, settings, and site profile
loading. Import these in route handlers using Depends().
"""

import json
from typing import Annotated, Any

from fastapi import Depends, HTTPException
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from config.settings import Settings, get_settings
from db.session import get_db


# ---------------------------------------------------------------------------
# Settings dependency
# ---------------------------------------------------------------------------

def get_settings_dep() -> Settings:
    """Return the application settings singleton."""
    return get_settings()


SettingsDep = Annotated[Settings, Depends(get_settings_dep)]
DatabaseDep = Annotated[AsyncSession, Depends(get_db)]


# ---------------------------------------------------------------------------
# Site profile dependency
# ---------------------------------------------------------------------------

async def get_site_profile(
    settings: SettingsDep,
) -> dict[str, Any]:
    """
    Load and return the site profile JSON for the configured SITE_ID.

    Raises HTTP 404 if the profile file does not exist.
    Raises HTTP 500 if the file cannot be parsed.
    """
    try:
        with open(settings.site_profile_path) as f:
            profile = json.load(f)
        logger.debug(f"Loaded site profile: {profile.get('name', 'unknown')}")
        return profile
    except FileNotFoundError:
        logger.error(f"Site profile not found: {settings.site_profile_path}")
        raise HTTPException(
            status_code=404,
            detail=f"Site profile for '{settings.site_id}' not found. "
                   f"Expected at: {settings.site_profile_path}",
        )
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse site profile JSON: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Site profile JSON is malformed: {e}",
        )


SiteProfileDep = Annotated[dict[str, Any], Depends(get_site_profile)]
