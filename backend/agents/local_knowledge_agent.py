"""
LocalKnowledgeAgent for paraglide-backend.

Matches site-specific heuristics from the site profile and DB KnowledgeItems
against the current context (wind direction, wind speed, time of day, season,
cloud condition) to produce typed Claims with source attribution.
"""

from datetime import datetime
from typing import Any

from loguru import logger

from agents.base import AgentBase, Claim, ClaimType, Evidence, SpatialScope, TemporalValidity


# Mapping from heuristic content keywords to ClaimType
KEYWORD_CLAIM_TYPE_MAP = {
    "thermal": ClaimType.THERMAL_ZONE,
    "ridge lift": ClaimType.RIDGE_LIFT,
    "ridge": ClaimType.RIDGE_LIFT,
    "sink": ClaimType.SINK_ZONE,
    "rotor": ClaimType.ROTOR_RISK,
    "turbulence": ClaimType.ROTOR_RISK,
    "caution": ClaimType.CAUTION,
    "avoid": ClaimType.CAUTION,
    "launch window": ClaimType.LAUNCH_WINDOW,
    "glass-off": ClaimType.LAUNCH_WINDOW,
    "do not fly": ClaimType.CAUTION,
    "hazard": ClaimType.CAUTION,
    "risk": ClaimType.CAUTION,
}


def _infer_claim_type(statement: str) -> ClaimType:
    """Infer the most appropriate ClaimType from the text of a heuristic statement."""
    lower = statement.lower()
    for keyword, claim_type in KEYWORD_CLAIM_TYPE_MAP.items():
        if keyword in lower:
            return claim_type
    return ClaimType.THERMAL_ZONE


class LocalKnowledgeAgent(AgentBase):
    """
    Matches local expert heuristics to the current flying context.

    Expected context keys:
        site_profile: site profile dict with known_heuristics list
        knowledge_items: optional list of KnowledgeItem DB records
        wind_dir_deg: float, current wind direction in degrees
        wind_speed_kmh: float, current wind speed in km/h
        time_of_day_hour: int, local hour (0-23)
        season: str, one of "spring", "summer", "fall", "winter"
        cloud_condition: str, e.g. "partly_cloudy", "clear", "overcast"
    """

    name = "local_knowledge_agent"
    reliability_weight: float = 0.75

    async def run(self, context: dict[str, Any]) -> list[Claim]:
        """
        Match all available heuristics and knowledge items to context.

        Returns a Claim for each heuristic that matches the current conditions.
        """
        site_profile = context.get("site_profile", {})
        heuristics = site_profile.get("known_heuristics", [])
        knowledge_items = context.get("knowledge_items", [])

        wind_dir_deg: float = float(context.get("wind_dir_deg", 225.0))
        wind_speed_kmh: float = float(context.get("wind_speed_kmh", 15.0))
        time_of_day_hour: int = int(context.get("time_of_day_hour", 12))
        season: str = context.get("season", "summer")
        cloud_condition: str = context.get("cloud_condition", "partly_cloudy")

        flying_context = {
            "wind_dir_deg": wind_dir_deg,
            "wind_speed_kmh": wind_speed_kmh,
            "time_of_day_hour": time_of_day_hour,
            "season": season,
            "cloud_condition": cloud_condition,
        }

        logger.info(
            f"LocalKnowledgeAgent matching {len(heuristics)} heuristics + "
            f"{len(knowledge_items)} KB items to context: "
            f"wind={wind_dir_deg:.0f}° {wind_speed_kmh:.0f}km/h, "
            f"hour={time_of_day_hour}, season={season}"
        )

        claims: list[Claim] = []

        # Match profile heuristics
        for heuristic in heuristics:
            match_score = self.match_heuristic(heuristic, flying_context)
            if match_score > 0.3:
                claim = self._build_heuristic_claim(heuristic, match_score, flying_context)
                if claim:
                    claims.append(claim)

        # Match DB knowledge items
        for ki in knowledge_items:
            if hasattr(ki, "__dict__"):
                ki_dict = {
                    "statement": ki.statement,
                    "sub_region": ki.sub_region,
                    "wind_condition": ki.wind_condition,
                    "time_of_day": ki.time_of_day,
                    "season": ki.season,
                    "confidence": ki.confidence,
                    "source_expert": ki.source_expert,
                    "risk_note": ki.risk_note,
                }
            else:
                ki_dict = ki

            match_score = self._match_knowledge_item(ki_dict, flying_context)
            if match_score > 0.3:
                claim = self._build_knowledge_item_claim(ki_dict, match_score, flying_context)
                if claim:
                    claims.append(claim)

        logger.info(f"LocalKnowledgeAgent produced {len(claims)} matching claims")
        return claims

    def match_heuristic(self, heuristic: dict[str, Any], context: dict[str, Any]) -> float:
        """
        Compute a match score (0.0–1.0) for a heuristic against the current context.

        Checks:
        - Season match
        - Time of day match
        - Wind direction range match
        - Wind speed range match
        - Cloud condition match

        Returns weighted average of matched conditions. Returns 0.0 if a hard
        EXCLUDE condition is violated.
        """
        condition = heuristic.get("condition", {})
        if not condition:
            # No condition = always applies (background knowledge)
            return 0.60

        scores: list[float] = []
        weights: list[float] = []

        # --- Season match ---
        cond_season = condition.get("season")
        if cond_season:
            ctx_season = context.get("season", "summer")
            if isinstance(cond_season, list):
                season_match = 1.0 if ctx_season in cond_season else 0.0
            else:
                season_match = 1.0 if ctx_season == cond_season else 0.0
            scores.append(season_match)
            weights.append(1.5)  # Season is important

        # --- Time of day match ---
        cond_time = condition.get("time_local")
        if cond_time and "-" in str(cond_time):
            try:
                t_parts = str(cond_time).split("-")
                t_from = int(t_parts[0].split(":")[0])
                t_to = int(t_parts[1].split(":")[0])
                ctx_hour = context.get("time_of_day_hour", 12)
                time_match = 1.0 if t_from <= ctx_hour <= t_to else 0.0
                scores.append(time_match)
                weights.append(1.5)
            except (ValueError, IndexError):
                pass

        # --- Wind direction match ---
        cond_wind_dir = condition.get("wind_dir_deg_range")
        if cond_wind_dir and len(cond_wind_dir) == 2:
            ctx_dir = context.get("wind_dir_deg", 225.0)
            dir_match = 1.0 if cond_wind_dir[0] <= ctx_dir <= cond_wind_dir[1] else 0.0
            scores.append(dir_match)
            weights.append(2.0)  # Direction is highly important

        # --- Wind speed match ---
        cond_speed_range = condition.get("wind_speed_kmh_range")
        if cond_speed_range and len(cond_speed_range) == 2:
            ctx_speed = context.get("wind_speed_kmh", 15.0)
            speed_match = 1.0 if cond_speed_range[0] <= ctx_speed <= cond_speed_range[1] else 0.0
            scores.append(speed_match)
            weights.append(1.5)

        cond_speed_min = condition.get("wind_speed_kmh_min")
        if cond_speed_min:
            ctx_speed = context.get("wind_speed_kmh", 15.0)
            speed_match = 1.0 if ctx_speed >= cond_speed_min else 0.0
            scores.append(speed_match)
            weights.append(1.5)

        cond_speed_max = condition.get("wind_speed_kmh_max")
        if cond_speed_max:
            ctx_speed = context.get("wind_speed_kmh", 15.0)
            speed_match = 1.0 if ctx_speed <= cond_speed_max else 0.0
            scores.append(speed_match)
            weights.append(1.0)

        if not scores:
            return 0.55  # No specific conditions — assume loosely applicable

        weighted_sum = sum(s * w for s, w in zip(scores, weights))
        total_weight = sum(weights)
        base_score = weighted_sum / total_weight

        # Hard EXCLUDE: if any critical condition scored 0 and had weight >= 2.0
        for score, weight in zip(scores, weights):
            if score == 0.0 and weight >= 2.0:
                return 0.0  # Critical condition not met — heuristic doesn't apply

        return base_score

    def _match_knowledge_item(self, ki: dict, context: dict) -> float:
        """Match a DB knowledge item against context using available fields."""
        score = 0.0
        checks = 0

        # Season
        if ki.get("season"):
            checks += 1
            if ki["season"].lower() == context.get("season", "").lower():
                score += 1.0

        # Wind condition (text-based)
        if ki.get("wind_condition"):
            checks += 1
            wind_desc = ki["wind_condition"].lower()
            ctx_dir = context.get("wind_dir_deg", 225)
            # Simple SW/NW/etc. matching
            if "sw" in wind_desc and 200 <= ctx_dir <= 250:
                score += 1.0
            elif "nw" in wind_desc and 290 <= ctx_dir <= 340:
                score += 1.0
            elif "se" in wind_desc and 115 <= ctx_dir <= 160:
                score += 1.0
            else:
                score += 0.3  # Partial credit

        # Time of day
        if ki.get("time_of_day"):
            checks += 1
            tod = ki["time_of_day"].lower()
            hour = context.get("time_of_day_hour", 12)
            if "morning" in tod and 7 <= hour <= 11:
                score += 1.0
            elif "midday" in tod or "noon" in tod and 11 <= hour <= 14:
                score += 1.0
            elif "afternoon" in tod and 12 <= hour <= 17:
                score += 1.0
            else:
                score += 0.3

        if checks == 0:
            return 0.50  # No conditions to check
        return score / checks

    def _build_heuristic_claim(
        self,
        heuristic: dict,
        match_score: float,
        context: dict,
    ) -> Claim | None:
        """Build a Claim from a matched heuristic."""
        statement = heuristic.get("statement", "")
        if not statement:
            return None

        sub_region = heuristic.get("sub_region")
        base_confidence = heuristic.get("confidence", 0.5)
        source = heuristic.get("source", "site_heuristic")
        risk_note = heuristic.get("risk_note")
        exception = heuristic.get("exception")
        heuristic_id = heuristic.get("id", "unknown")

        # Combined confidence: heuristic confidence * context match score
        combined_confidence = base_confidence * (0.7 + 0.3 * match_score)
        combined_confidence = max(0.0, min(0.95, combined_confidence))

        claim_type = _infer_claim_type(statement)
        if risk_note:
            claim_type = ClaimType.CAUTION

        evidence = [
            Evidence(
                source=f"local_knowledge_heuristic_{heuristic_id}",
                description=f"Site heuristic from: {source}. Match score: {match_score:.2f}",
                data_ref={
                    "heuristic_id": heuristic_id,
                    "source": source,
                    "match_score": round(match_score, 3),
                    "condition": heuristic.get("condition", {}),
                },
            )
        ]

        assumptions = []
        if exception:
            assumptions.append(f"Exception: {exception}")

        full_text = statement
        if risk_note:
            full_text += f" RISK NOTE: {risk_note}"

        return self._make_claim(
            claim_type=claim_type,
            claim_text=full_text,
            confidence=combined_confidence,
            evidence=evidence,
            assumptions=assumptions,
            spatial_scope=SpatialScope(feature_name=sub_region) if sub_region else None,
            temporal_validity=TemporalValidity(notes=f"Heuristic condition match: {match_score:.2f}"),
        )

    def _build_knowledge_item_claim(
        self,
        ki: dict,
        match_score: float,
        context: dict,
    ) -> Claim | None:
        """Build a Claim from a matched DB KnowledgeItem."""
        statement = ki.get("statement", "")
        if not statement:
            return None

        base_confidence = ki.get("confidence", 0.5)
        combined_confidence = base_confidence * (0.7 + 0.3 * match_score)
        claim_type = _infer_claim_type(statement)
        risk_note = ki.get("risk_note")
        if risk_note:
            claim_type = ClaimType.CAUTION

        source_expert = ki.get("source_expert", "unknown expert")
        evidence = [
            Evidence(
                source=f"knowledge_item_db",
                description=f"KB item from {source_expert}. Match: {match_score:.2f}",
                data_ref={"source_expert": source_expert, "match_score": round(match_score, 3)},
            )
        ]

        return self._make_claim(
            claim_type=claim_type,
            claim_text=statement + (f" RISK: {risk_note}" if risk_note else ""),
            confidence=min(0.92, combined_confidence),
            evidence=evidence,
            spatial_scope=SpatialScope(feature_name=ki.get("sub_region")),
        )
