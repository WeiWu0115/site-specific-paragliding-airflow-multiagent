"""
Knowledge ingestion service for paraglide-backend.

Handles importing KnowledgeItems and ExpertInterviews into the database,
including basic heuristic extraction from raw interview transcripts.
"""

import re
from datetime import date
from typing import Any

from loguru import logger

from knowledge.schema import HeuristicRule


class KnowledgeIngestionService:
    """
    Service for importing expert knowledge into the paraglide system.

    Methods are class-level (static) so they can be called without instantiation
    in route handlers that use dependency injection.
    """

    @staticmethod
    async def import_knowledge_item(
        item_data: dict[str, Any],
        site_id_int: int,
        db: Any,
    ) -> Any:
        """
        Validate and store a knowledge item in the database.

        Args:
            item_data: Validated KnowledgeItemCreate dict
            site_id_int: Integer site ID from DB
            db: Async SQLAlchemy session

        Returns:
            The created KnowledgeItem ORM object
        """
        import json
        from db.models import KnowledgeItem

        ki = KnowledgeItem(
            site_id=site_id_int,
            sub_region=item_data.get("sub_region"),
            wind_condition=item_data.get("wind_condition"),
            time_of_day=item_data.get("time_of_day"),
            season=item_data.get("season"),
            cloud_condition=item_data.get("cloud_condition"),
            statement=item_data["statement"],
            exception_statement=item_data.get("exception_statement"),
            risk_note=item_data.get("risk_note"),
            source_expert=item_data.get("source_expert"),
            source_date=item_data.get("source_date"),
            confidence=item_data.get("confidence", 0.5),
            provenance_json=json.dumps({
                "source_expert": item_data.get("source_expert"),
                "import_method": "ingestion_service",
            }),
        )
        db.add(ki)
        await db.flush()
        logger.info(f"Knowledge item stored: id={ki.id} region={ki.sub_region}")
        return ki

    @staticmethod
    async def import_interview(
        interview_data: dict[str, Any],
        site_id_int: int,
        db: Any,
    ) -> tuple[Any, list[HeuristicRule]]:
        """
        Store a raw expert interview and attempt to extract structured heuristics.

        Returns:
            Tuple of (ExpertInterview ORM object, list of extracted HeuristicRules)
        """
        import json
        from datetime import datetime
        from db.models import ExpertInterview

        transcript = interview_data.get("raw_transcript", "")
        heuristics = KnowledgeIngestionService.parse_heuristics_from_text(transcript)

        ei = ExpertInterview(
            site_id=site_id_int,
            expert_name=interview_data["expert_name"],
            interview_date=interview_data.get("interview_date"),
            raw_transcript=transcript,
            structured_json=json.dumps([
                {
                    "statement": h.statement,
                    "condition": h.condition.model_dump() if h.condition else None,
                    "confidence": h.confidence,
                    "sub_region": h.sub_region,
                    "risk_note": h.risk_note,
                }
                for h in heuristics
            ]),
            processed_at=datetime.utcnow(),
        )
        db.add(ei)
        await db.flush()

        logger.info(
            f"Interview imported: id={ei.id} expert={ei.expert_name} "
            f"heuristics_extracted={len(heuristics)}"
        )
        return ei, heuristics

    @staticmethod
    def parse_heuristics_from_text(text: str) -> list[HeuristicRule]:
        """
        Extract structured heuristics from a free-text interview transcript.

        Uses keyword pattern matching to identify:
        - Conditional patterns: "when X, Y happens", "if X, then Y"
        - Time references: "around 10am", "between 10 and 2"
        - Wind references: "SW wind", "10-15 mph"
        - Location references: "near the ridge", "over the bowl"
        - Risk statements: "avoid", "dangerous", "caution"

        Returns a list of HeuristicRule objects. These are approximate extractions
        and should be reviewed by a human before being trusted.
        """
        heuristics: list[HeuristicRule] = []

        # Split into sentences
        sentences = re.split(r"[.!?]+\s+|\n+", text)

        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) < 20:
                continue

            rule = KnowledgeIngestionService._try_extract_heuristic(sentence)
            if rule:
                heuristics.append(rule)

        logger.debug(f"Extracted {len(heuristics)} heuristics from {len(sentences)} sentences")
        return heuristics

    @staticmethod
    def _try_extract_heuristic(sentence: str) -> HeuristicRule | None:
        """
        Attempt to extract a heuristic from a single sentence.

        Returns HeuristicRule if the sentence contains a recognizable conditional
        or causal pattern, else None.
        """
        lower = sentence.lower()

        # Must contain a trigger word to be considered a heuristic
        trigger_words = [
            "when ", "if ", "whenever ", "once ", "after ", "around ",
            "typically", "usually", "always", "never", "avoid", "watch for",
            "be careful", "reliable", "fires", "triggers", "develops",
        ]
        if not any(tw in lower for tw in trigger_words):
            return None

        # Determine confidence based on language certainty
        confidence = 0.5
        if any(w in lower for w in ["always", "never", "reliably", "consistently"]):
            confidence = 0.80
        elif any(w in lower for w in ["usually", "typically", "generally", "often"]):
            confidence = 0.65
        elif any(w in lower for w in ["sometimes", "occasionally", "can"]):
            confidence = 0.45

        # Check for risk language
        risk_note = None
        if any(w in lower for w in ["avoid", "dangerous", "caution", "incident", "collapsed", "turbulence"]):
            risk_note = f"Risk indicator found in: {sentence[:80]}"
            confidence = max(confidence, 0.70)  # Risk statements get higher confidence

        # Detect sub-region mentions
        sub_region = None
        region_keywords = {
            "riverbed": "Tehachapi Creek Drainage",
            "bowl": "South Bowl",
            "ridge": "Eagle Ridge Main",
            "north notch": "North Notch Launch",
            "lee": "West Lee Sink Zone",
            "valley": "North Valley",
        }
        for keyword, region_name in region_keywords.items():
            if keyword in lower:
                sub_region = region_name
                break

        # Build a condition hint from time references
        condition_dict: dict[str, Any] = {}
        time_match = re.search(r"(\d{1,2})[:\s]?(?:am|pm|:00)", lower)
        if time_match:
            condition_dict["time_local"] = time_match.group(0)

        wind_dir_match = re.search(r"\b(n|s|e|w|nw|ne|sw|se)\s+wind", lower)
        if wind_dir_match:
            condition_dict["wind_dir_hint"] = wind_dir_match.group(1).upper()

        from knowledge.schema import ConditionBlock
        condition = ConditionBlock(**{}) if not condition_dict else None

        return HeuristicRule(
            statement=sentence,
            condition=condition,
            risk_note=risk_note,
            sub_region=sub_region,
            confidence=confidence,
            source="extracted_from_transcript",
        )
