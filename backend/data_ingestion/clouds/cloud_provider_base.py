"""
Abstract base class and data structures for cloud observation providers.

Cloud providers supply current cloud cover information used by the CloudAgent
to assess thermal development potential and overdevelopment risk.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import ClassVar


@dataclass
class CloudObservation:
    """
    A single cloud observation for a location.

    cover_pct: Total cloud cover as percentage (0-100)
    cloud_base_m: Estimated cloud base altitude in meters (None if unknown)
    cloud_type_hint: Descriptive string, e.g. "cumulus", "stratus", "clear"
    satellite_url: Optional URL to satellite imagery for this observation
    observed_at: Timestamp of observation (UTC)
    confidence: Confidence in this observation (0.0-1.0)
    """
    cover_pct: float
    cloud_base_m: float | None
    cloud_type_hint: str | None
    satellite_url: str | None
    observed_at: datetime
    confidence: float = 0.5


class CloudProvider(ABC):
    """
    Abstract base class for all cloud observation providers.

    Phase 1 only has a mock implementation. Phase 2 will add satellite-based
    observation providers.
    """

    provider_id: ClassVar[str] = "base"

    @abstractmethod
    async def fetch_observation(
        self,
        lat: float,
        lon: float,
    ) -> CloudObservation:
        """
        Fetch a current cloud observation for the given location.

        Args:
            lat: Latitude in decimal degrees
            lon: Longitude in decimal degrees

        Returns:
            CloudObservation with current cover data
        """
        ...
