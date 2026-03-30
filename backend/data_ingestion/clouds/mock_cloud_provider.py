"""
MockCloudProvider for paraglide-backend.

Returns realistic midday cloud observation data representing typical
paragliding conditions: 35% cover with cumulus development hints.
"""

from datetime import datetime, timezone

from loguru import logger

from data_ingestion.clouds.cloud_provider_base import CloudObservation, CloudProvider


class MockCloudProvider(CloudProvider):
    """
    Returns a fixed realistic cloud observation for development and testing.

    Represents midday conditions at Eagle Ridge on a good thermal day:
    - 35% cloud cover (cumulus developing)
    - Cloud base ~2,100m (good thermal height available)
    - Cumulus type hint
    - Moderate confidence (0.60) to reflect uncertainty in mock data
    """

    provider_id = "mock"

    async def fetch_observation(
        self,
        lat: float,
        lon: float,
    ) -> CloudObservation:
        """Return a synthetic midday cloud observation."""
        logger.info(f"MockCloudProvider returning synthetic cloud observation for lat={lat} lon={lon}")

        return CloudObservation(
            cover_pct=35.0,
            cloud_base_m=2100.0,
            cloud_type_hint="cumulus_fair_weather",
            satellite_url=None,
            observed_at=datetime.now(tz=timezone.utc),
            confidence=0.60,
        )
