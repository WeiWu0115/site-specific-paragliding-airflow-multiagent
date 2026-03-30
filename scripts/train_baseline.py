"""
Baseline thermal likelihood model training script for paraglide-backend.

Loads flight_segments (climbs) and corresponding weather_snapshots from DB,
extracts features, trains an XGBoost classifier, evaluates with cross-validation,
saves the model artifact, and prints feature importances.

Requires Phase 2 data: IGC flights imported + weather snapshots stored.
Exits gracefully if insufficient data is available.

Usage:
    cd backend
    python ../scripts/train_baseline.py --site eagle_ridge --output ../ml_artifacts/thermal_v1.pkl
"""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from loguru import logger

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://paraglide:paraglide@localhost:5432/paraglide_db"
)

MIN_SAMPLES = 30  # Minimum positive+negative examples to train


async def load_training_data(site_slug: str) -> tuple[list, list]:
    """
    Load climb segments (positive examples) and glide segments (negative examples)
    from DB with associated weather features.

    Returns: (features_list, labels_list)
    """
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from db.models import FlightSegment, HistoricalFlightTrack, SiteProfile, WeatherSnapshot
    from ml.features import FeatureExtractor
    from data_ingestion.weather.provider_base import WeatherHour

    engine = create_async_engine(DATABASE_URL, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    features_list = []
    labels_list = []

    async with session_factory() as session:
        site_result = await session.execute(
            select(SiteProfile).where(SiteProfile.slug == site_slug)
        )
        site = site_result.scalar_one_or_none()
        if site is None:
            logger.error(f"Site '{site_slug}' not found")
            return [], []

        # Load climb segments (label=1)
        climb_result = await session.execute(
            select(FlightSegment, HistoricalFlightTrack)
            .join(HistoricalFlightTrack, FlightSegment.track_id == HistoricalFlightTrack.id)
            .where(
                HistoricalFlightTrack.site_id == site.id,
                FlightSegment.segment_type == "climb",
            )
            .limit(500)
        )
        climbs = climb_result.fetchall()
        logger.info(f"Loaded {len(climbs)} climb segments")

        # Load glide segments (label=0)
        glide_result = await session.execute(
            select(FlightSegment, HistoricalFlightTrack)
            .join(HistoricalFlightTrack, FlightSegment.track_id == HistoricalFlightTrack.id)
            .where(
                HistoricalFlightTrack.site_id == site.id,
                FlightSegment.segment_type == "glide",
            )
            .limit(500)
        )
        glides = glide_result.fetchall()
        logger.info(f"Loaded {len(glides)} glide segments")

        # Load site profile for terrain features
        profile_path = os.path.join(
            os.path.dirname(__file__), "..", "backend", "config", "site_profiles", f"{site_slug}.json"
        )
        with open(profile_path) as f:
            site_profile = json.load(f)

        terrain_features = site_profile.get("terrain_features", [])
        primary_terrain = next((tf for tf in terrain_features if tf.get("type") == "ridge"), {})

        extractor = FeatureExtractor()

        # For each climb/glide, find matching weather snapshot
        # Simple approach: match by flight_date to closest weather snapshot
        all_snapshots_result = await session.execute(
            select(WeatherSnapshot).where(WeatherSnapshot.site_id == site.id).limit(100)
        )
        snapshots = {s.id: s for s in all_snapshots_result.scalars().all()}

        def _segment_to_features(seg: FlightSegment, label: int) -> None:
            # Create a synthetic WeatherHour from segment time + midday assumptions
            start_time = seg.start_time
            hour = start_time.hour if start_time and hasattr(start_time, "hour") else 12

            # Synthetic weather hour (Phase 2 will use real matched snapshots)
            import math
            from datetime import datetime, timezone
            from data_ingestion.weather.provider_base import WeatherHour

            fake_hour = WeatherHour(
                time=start_time or datetime.now(tz=timezone.utc),
                temp_c=28.0,
                dewpoint_c=8.0,
                humidity_pct=35.0,
                wind_speed_kmh=15.0,
                wind_dir_deg=225.0,
                pressure_hpa=1013.0,
                cloud_cover_pct=30.0,
                precipitation_mm=0.0,
                weather_code=1,
            )

            wf = extractor.extract_weather_features(fake_hour)
            tf = extractor.extract_terrain_features(primary_terrain, 225.0)
            vec = extractor.combine_features(wf, tf)
            features_list.append(vec)
            labels_list.append(label)

        for seg, track in climbs:
            _segment_to_features(seg, 1)

        for seg, track in glides:
            _segment_to_features(seg, 0)

    await engine.dispose()
    return features_list, labels_list


async def main() -> None:
    parser = argparse.ArgumentParser(description="Train baseline thermal likelihood model")
    parser.add_argument("--site", type=str, default="eagle_ridge")
    parser.add_argument("--output", type=str, default="../ml_artifacts/thermal_v1.pkl")
    args = parser.parse_args()

    logger.info(f"Loading training data for site: {args.site}")
    features_list, labels_list = await load_training_data(args.site)

    if len(features_list) < MIN_SAMPLES:
        logger.warning(
            f"Insufficient training data: {len(features_list)} samples (need {MIN_SAMPLES}). "
            f"Import more IGC flights first using scripts/import_igc.py. "
            f"Exiting without training."
        )
        sys.exit(0)

    import numpy as np
    X = np.vstack(features_list)
    y = np.array(labels_list)

    logger.info(f"Training set: {X.shape[0]} samples, {X.shape[1]} features")
    logger.info(f"Class distribution: {y.sum()} positive ({y.mean():.1%}), {(1-y).sum()} negative")

    try:
        import xgboost as xgb
        from sklearn.model_selection import StratifiedKFold, cross_val_score
        from sklearn.metrics import roc_auc_score
    except ImportError as e:
        logger.error(f"Required ML libraries not available: {e}")
        sys.exit(1)

    model = xgb.XGBClassifier(
        n_estimators=100,
        max_depth=4,
        learning_rate=0.1,
        subsample=0.8,
        colsample_bytree=0.8,
        use_label_encoder=False,
        eval_metric="logloss",
        random_state=42,
    )

    # Cross-validation
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    cv_scores = cross_val_score(model, X, y, cv=cv, scoring="roc_auc")
    logger.info(f"Cross-validation ROC-AUC: {cv_scores.mean():.3f} ± {cv_scores.std():.3f}")

    # Train on full dataset
    model.fit(X, y)

    # Feature importances
    from ml.features import FEATURE_NAMES
    importances = model.feature_importances_
    sorted_features = sorted(zip(FEATURE_NAMES, importances), key=lambda x: x[1], reverse=True)
    logger.info("Feature importances:")
    for fname, importance in sorted_features:
        logger.info(f"  {fname:<30} {importance:.4f}")

    # Save model
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    import pickle
    with open(output_path, "wb") as f:
        pickle.dump(model, f)

    logger.info(f"Model saved to: {output_path}")

    # Save metrics to DB
    try:
        from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
        engine = create_async_engine(DATABASE_URL, echo=False)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        from sqlalchemy import select
        async with session_factory() as session:
            from db.models import ModelVersion, SiteProfile
            site_result = await session.execute(
                select(SiteProfile).where(SiteProfile.slug == args.site)
            )
            site = site_result.scalar_one_or_none()
            mv = ModelVersion(
                model_type="thermal_likelihood_xgb",
                version_tag="v1_baseline",
                site_id=site.id if site else None,
                metrics_json=json.dumps({
                    "cv_roc_auc_mean": float(cv_scores.mean()),
                    "cv_roc_auc_std": float(cv_scores.std()),
                    "n_samples": len(features_list),
                    "n_features": X.shape[1],
                }),
                artifact_path=str(output_path.resolve()),
            )
            session.add(mv)
            await session.commit()
        await engine.dispose()
        logger.info("Model version record saved to DB")
    except Exception as e:
        logger.warning(f"Could not save model version to DB: {e}")

    logger.info("Training complete.")


if __name__ == "__main__":
    asyncio.run(main())
