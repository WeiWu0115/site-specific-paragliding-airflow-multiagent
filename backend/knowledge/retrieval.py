"""
Knowledge retrieval service for paraglide-backend.

Queries stored knowledge items by condition matching and provides
heuristic retrieval from site profiles for agent consumption.
"""

from typing import Any

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class KnowledgeRetrieval:
    """
    Retrieves relevant knowledge items for a given flying context.

    Supports:
    - DB-backed knowledge item queries with multi-field filtering
    - Site profile heuristic matching against context
    - Simple keyword similarity for context matching
    """

    @staticmethod
    async def query_by_conditions(
        wind_dir_deg: float | None,
        wind_speed_kmh: float | None,
        time_of_day: int | None,
        season: str | None,
        site_id: int,
        db: AsyncSession,
    ) -> list[Any]:
        """
        Query knowledge items from DB matching the given conditions.

        Uses loose matching: items are returned if their stored conditions
        overlap with the provided context (not requiring exact match).

        Args:
            wind_dir_deg: Current wind direction in degrees
            wind_speed_kmh: Current wind speed in km/h
            time_of_day: Local hour (0-23)
            season: "spring", "summer", "fall", "winter"
            site_id: DB site profile ID
            db: Async SQLAlchemy session

        Returns:
            List of KnowledgeItem ORM objects
        """
        from db.models import KnowledgeItem

        query = select(KnowledgeItem).where(KnowledgeItem.site_id == site_id)

        # Filter by season if provided
        if season:
            query = query.where(
                (KnowledgeItem.season == season) | (KnowledgeItem.season.is_(None))
            )

        # Filter by time of day
        if time_of_day is not None:
            tod_label = _hour_to_time_label(time_of_day)
            if tod_label:
                query = query.where(
                    (KnowledgeItem.time_of_day.ilike(f"%{tod_label}%"))
                    | (KnowledgeItem.time_of_day.is_(None))
                )

        result = await db.execute(query.limit(100))
        items = result.scalars().all()

        logger.debug(
            f"KnowledgeRetrieval: returned {len(items)} items for "
            f"wind={wind_dir_deg}° {wind_speed_kmh}km/h, hour={time_of_day}, season={season}"
        )
        return items

    @staticmethod
    def get_matching_heuristics(
        context: dict[str, Any],
        site_profile: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """
        Return site profile heuristics that match the given context.

        Applies the same matching logic as LocalKnowledgeAgent.match_heuristic()
        but returns raw heuristic dicts for use in pre-agent preprocessing.

        Args:
            context: Flying context dict with keys:
                wind_dir_deg, wind_speed_kmh, time_of_day_hour, season, cloud_condition
            site_profile: Site profile dict with known_heuristics list

        Returns:
            List of matching heuristic dicts with added 'match_score' key
        """
        heuristics = site_profile.get("known_heuristics", [])
        if not heuristics:
            return []

        from agents.local_knowledge_agent import LocalKnowledgeAgent
        agent = LocalKnowledgeAgent()

        matched = []
        for h in heuristics:
            score = agent.match_heuristic(h, context)
            if score > 0.3:
                matched.append({**h, "match_score": round(score, 3)})

        matched.sort(key=lambda h: h["match_score"], reverse=True)
        logger.debug(f"KnowledgeRetrieval: {len(matched)}/{len(heuristics)} heuristics matched context")
        return matched


def _hour_to_time_label(hour: int) -> str | None:
    """Convert an hour (0-23) to a rough time-of-day label."""
    if 5 <= hour <= 9:
        return "morning"
    elif 10 <= hour <= 12:
        return "midday"
    elif 13 <= hour <= 17:
        return "afternoon"
    elif 18 <= hour <= 21:
        return "evening"
    return None
