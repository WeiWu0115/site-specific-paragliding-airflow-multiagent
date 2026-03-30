"""
Knowledge management routes for paraglide-backend.

Handles import and retrieval of expert knowledge items and interview transcripts.
"""

from datetime import date
from typing import Any

from fastapi import APIRouter, HTTPException
from loguru import logger
from pydantic import BaseModel, Field
from sqlalchemy import select

from api.deps import DatabaseDep, SettingsDep
from db.models import ExpertInterview, KnowledgeItem

router = APIRouter()


class KnowledgeItemCreate(BaseModel):
    """Request body for importing a knowledge item."""
    site_id: str
    sub_region: str | None = None
    wind_condition: str | None = None
    time_of_day: str | None = None
    season: str | None = None
    cloud_condition: str | None = None
    statement: str
    exception_statement: str | None = None
    risk_note: str | None = None
    source_expert: str | None = None
    source_date: date | None = None
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class ExpertInterviewCreate(BaseModel):
    """Request body for importing an expert interview."""
    site_id: str
    expert_name: str
    interview_date: date | None = None
    raw_transcript: str
    notes: str | None = None


@router.post("/import", summary="Import a knowledge item", status_code=201)
async def import_knowledge_item(
    item: KnowledgeItemCreate,
    settings: SettingsDep,
    db: DatabaseDep,
) -> dict[str, Any]:
    """
    Import a structured knowledge item into the database.

    Knowledge items represent expert-validated heuristics about the site:
    thermal triggers, wind conditions, risk zones, timing patterns, etc.
    """
    import json

    # Resolve site DB ID
    from db.models import SiteProfile
    result = await db.execute(
        select(SiteProfile).where(SiteProfile.slug == (item.site_id or settings.site_id))
    )
    site = result.scalar_one_or_none()
    if site is None:
        raise HTTPException(status_code=404, detail=f"Site '{item.site_id}' not found in database")

    ki = KnowledgeItem(
        site_id=site.id,
        sub_region=item.sub_region,
        wind_condition=item.wind_condition,
        time_of_day=item.time_of_day,
        season=item.season,
        cloud_condition=item.cloud_condition,
        statement=item.statement,
        exception_statement=item.exception_statement,
        risk_note=item.risk_note,
        source_expert=item.source_expert,
        source_date=item.source_date,
        confidence=item.confidence,
        provenance_json=json.dumps({
            "source_expert": item.source_expert,
            "source_date": item.source_date.isoformat() if item.source_date else None,
            "import_method": "api",
        }),
    )
    db.add(ki)
    await db.flush()
    await db.refresh(ki)

    logger.info(f"Knowledge item created: id={ki.id} region={ki.sub_region}")
    return {"id": ki.id, "statement": ki.statement, "confidence": ki.confidence}


@router.get("", summary="List knowledge items for this site")
async def list_knowledge_items(
    settings: SettingsDep,
    db: DatabaseDep,
    sub_region: str | None = None,
    wind_condition: str | None = None,
    time_of_day: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """
    Return knowledge items for the current site with optional filters.
    """
    from db.models import SiteProfile
    site_result = await db.execute(
        select(SiteProfile).where(SiteProfile.slug == settings.site_id)
    )
    site = site_result.scalar_one_or_none()
    if site is None:
        return []

    query = select(KnowledgeItem).where(KnowledgeItem.site_id == site.id)

    if sub_region:
        query = query.where(KnowledgeItem.sub_region.ilike(f"%{sub_region}%"))
    if wind_condition:
        query = query.where(KnowledgeItem.wind_condition.ilike(f"%{wind_condition}%"))
    if time_of_day:
        query = query.where(KnowledgeItem.time_of_day.ilike(f"%{time_of_day}%"))

    query = query.limit(limit).order_by(KnowledgeItem.confidence.desc())
    result = await db.execute(query)
    items = result.scalars().all()

    return [
        {
            "id": ki.id,
            "sub_region": ki.sub_region,
            "wind_condition": ki.wind_condition,
            "time_of_day": ki.time_of_day,
            "season": ki.season,
            "statement": ki.statement,
            "exception_statement": ki.exception_statement,
            "risk_note": ki.risk_note,
            "source_expert": ki.source_expert,
            "confidence": ki.confidence,
            "created_at": ki.created_at.isoformat() if ki.created_at else None,
        }
        for ki in items
    ]


@router.post("/import-interview", summary="Import expert interview transcript", status_code=201)
async def import_interview(
    interview: ExpertInterviewCreate,
    settings: SettingsDep,
    db: DatabaseDep,
) -> dict[str, Any]:
    """
    Import a raw expert interview transcript.

    The transcript is stored as-is and a basic keyword extraction pass is
    attempted to produce structured heuristics. Full NLP parsing can be
    added in Phase 3.
    """
    import json
    from datetime import datetime

    from db.models import SiteProfile
    site_result = await db.execute(
        select(SiteProfile).where(SiteProfile.slug == (interview.site_id or settings.site_id))
    )
    site = site_result.scalar_one_or_none()
    if site is None:
        raise HTTPException(status_code=404, detail=f"Site '{interview.site_id}' not found")

    from knowledge.ingestion import KnowledgeIngestionService
    parsed_heuristics = KnowledgeIngestionService.parse_heuristics_from_text(interview.raw_transcript)

    ei = ExpertInterview(
        site_id=site.id,
        expert_name=interview.expert_name,
        interview_date=interview.interview_date,
        raw_transcript=interview.raw_transcript,
        structured_json=json.dumps([
            {"statement": h.statement, "condition": h.condition, "confidence": h.confidence}
            for h in parsed_heuristics
        ]),
        processed_at=datetime.utcnow(),
    )
    db.add(ei)
    await db.flush()
    await db.refresh(ei)

    logger.info(f"Interview imported: id={ei.id} expert={ei.expert_name} heuristics_extracted={len(parsed_heuristics)}")

    return {
        "id": ei.id,
        "expert_name": ei.expert_name,
        "heuristics_extracted": len(parsed_heuristics),
        "extracted_heuristics": [
            {"statement": h.statement, "confidence": h.confidence}
            for h in parsed_heuristics
        ],
    }
