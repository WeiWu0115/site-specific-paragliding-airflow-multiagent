"""
Knowledge import CLI script for paraglide-backend.

Imports structured knowledge items from a JSON file into the database.

Usage:
    cd backend
    python ../scripts/import_knowledge.py --file /path/to/knowledge.json --site eagle_ridge

JSON file format:
    [
      {
        "site_id": "eagle_ridge",
        "sub_region": "South Bowl",
        "wind_condition": "SW 10-18 km/h",
        "time_of_day": "morning",
        "season": "summer",
        "statement": "South Bowl fires a reliable thermal around 10:00-11:30.",
        "confidence": 0.75,
        "source_expert": "Tom M., site instructor",
        "source_date": "2024-05-01"
      }
    ]
"""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://paraglide:paraglide@localhost:5432/paraglide_db"
)


async def main() -> None:
    parser = argparse.ArgumentParser(description="Import knowledge items into paraglide DB")
    parser.add_argument("--file", type=str, required=True, help="Path to JSON knowledge file")
    parser.add_argument("--site", type=str, default="eagle_ridge", help="Site slug")
    args = parser.parse_args()

    json_path = Path(args.file)
    if not json_path.exists():
        logger.error(f"File not found: {json_path}")
        sys.exit(1)

    with open(json_path) as f:
        items_data = json.load(f)

    if not isinstance(items_data, list):
        logger.error("JSON file must contain a list of knowledge item objects")
        sys.exit(1)

    logger.info(f"Loaded {len(items_data)} knowledge items from {json_path.name}")

    # Validate with Pydantic
    from knowledge.schema import KnowledgeItemCreate
    validated_items: list[KnowledgeItemCreate] = []
    errors = []
    for i, item_data in enumerate(items_data):
        try:
            validated = KnowledgeItemCreate(**item_data)
            validated_items.append(validated)
        except Exception as e:
            errors.append(f"Item {i}: {e}")

    if errors:
        logger.error(f"Validation errors:\n" + "\n".join(errors))
        sys.exit(1)

    logger.info(f"All {len(validated_items)} items validated successfully")

    engine = create_async_engine(DATABASE_URL, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        from db.models import SiteProfile
        site_result = await session.execute(
            select(SiteProfile).where(SiteProfile.slug == args.site)
        )
        site = site_result.scalar_one_or_none()
        if site is None:
            logger.error(f"Site '{args.site}' not found. Run seed_site.py first.")
            sys.exit(1)

        from knowledge.ingestion import KnowledgeIngestionService
        imported = 0
        for item in validated_items:
            await KnowledgeIngestionService.import_knowledge_item(
                item.model_dump(),
                site.id,
                session,
            )
            imported += 1
            logger.info(f"  Imported: {item.statement[:60]}...")

        await session.commit()

    await engine.dispose()

    logger.info(f"Import complete: {imported} knowledge items stored")


if __name__ == "__main__":
    asyncio.run(main())
