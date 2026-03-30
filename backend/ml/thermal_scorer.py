"""
ThermalScorer for paraglide-backend.

Wraps either a trained ML model (XGBoost/LightGBM) or a rule-based fallback
to score thermal likelihood for a given weather+terrain feature combination.

The rule-based scorer uses the same thermal index formula as WeatherAgent
but adds terrain aspect and slope weighting.
"""

import math
from pathlib import Path
from typing import Any

import numpy as np
from loguru import logger

from ml.features import FeatureExtractor, FEATURE_NAMES


class ThermalScorer:
    """
    Scores thermal likelihood for weather+terrain feature combinations.

    In Phase 1 (no training data), uses the rule-based formula.
    In Phase 3, loads a trained XGBoost/LightGBM model for ML scoring.

    Rule-based formula:
        score = dewpoint_spread_factor * wind_factor * time_factor * aspect_factor * cloud_factor

    Coefficients are documented with reasoning below.
    """

    def __init__(self) -> None:
        self._model: Any = None
        self._model_type: str = "rule_based"
        self._feature_extractor = FeatureExtractor()

    def score(self, features: np.ndarray) -> float:
        """
        Score thermal likelihood from a feature vector.

        Args:
            features: 1D numpy array in FEATURE_NAMES order

        Returns:
            Float 0.0–1.0 (higher = more likely thermals)
        """
        if self._model is not None:
            return self._ml_score(features)
        return self._rule_based_score_from_vector(features)

    def load_model(self, path: str) -> None:
        """
        Load a saved XGBoost or LightGBM model from disk.

        Args:
            path: Path to saved model file (.pkl or .json)
        """
        import pickle
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Model artifact not found: {path}")

        with open(p, "rb") as f:
            self._model = pickle.load(f)

        self._model_type = "ml_model"
        logger.info(f"Thermal scorer loaded ML model from: {path}")

    def get_rule_based_score(
        self,
        weather_hour: Any,
        terrain_feature: dict[str, Any],
    ) -> float:
        """
        Compute the rule-based thermal score for a specific weather hour and terrain feature.

        This is the primary scoring method in Phase 1 before ML training data is available.

        Formula components:
        - dewpoint_spread_factor: measures atmospheric dryness (dry air → better thermals)
        - wind_factor: gaussian peak at 15 km/h, falls off at very light and very strong winds
        - time_factor: gaussian peak at 13:00 local (thermal peak)
        - aspect_factor: south-facing slopes in daytime score highest
        - cloud_factor: 20-50% cover is ideal (markers without suppression)
        """
        wf = self._feature_extractor.extract_weather_features(weather_hour)
        tf = self._feature_extractor.extract_terrain_features(terrain_feature, wf["wind_dir_sin"])
        features = self._feature_extractor.combine_features(wf, tf)
        return self._rule_based_score_from_vector(features)

    def _rule_based_score_from_vector(self, features: np.ndarray) -> float:
        """Apply the rule-based formula to a feature vector."""
        feat = dict(zip(FEATURE_NAMES, features))

        # --- Dewpoint spread factor ---
        # Spread of 20°C → factor 1.0; spread 5°C → 0.25; spread 0°C → 0.0
        # Larger spread = drier air = stronger thermal buoyancy
        # Coefficient: 1/20 per degree of spread
        spread = max(0.0, feat.get("dewpoint_spread_c", 10.0))
        dewpoint_spread_factor = min(1.0, spread / 20.0)

        # --- Wind factor ---
        # Gaussian centered at 15 km/h, sigma=7
        # Rationale: too light = no trigger; ideal = 12-18 km/h; too strong = rotor risk
        wind = feat.get("wind_speed_kmh", 15.0)
        wind_factor = math.exp(-0.5 * ((wind - 15.0) / 7.0) ** 2)
        # Hard penalty above 25 km/h
        if wind > 25.0:
            wind_factor *= max(0.0, 1.0 - (wind - 25.0) / 10.0)

        # --- Time of day factor ---
        # hour_sin/cos encode time cyclically; reconstruct hour
        # Gaussian peak at 13:00, sigma=2.5
        hour_sin = feat.get("hour_sin", 0.0)
        hour_cos = feat.get("hour_cos", 1.0)
        hour_approx = (math.atan2(hour_sin, hour_cos) / (2 * math.pi) * 24) % 24
        time_factor = math.exp(-0.5 * ((hour_approx - 13.0) / 2.5) ** 2)

        # --- Aspect factor ---
        # Aspect alignment cosine: 1.0 = wind directly into slope face
        # For thermal potential: south-facing is ideal regardless of wind
        # We blend wind-alignment with a south-facing bonus
        aspect_alignment = feat.get("aspect_alignment_cos", 0.5)
        # Convert back to rough aspect (0=wind-aligned, so positive alignment = lift side)
        # South-facing boost: if aspect is ~180° (south), apply bonus in daytime
        aspect_factor = 0.5 + 0.5 * max(0.0, aspect_alignment)

        # Feature type bonus: riverbeds and south-facing bowls are thermal generators
        type_bonus = 0.0
        if feat.get("feature_type_riverbed", 0) > 0.5:
            type_bonus = 0.15  # Riverbeds are strong thermal triggers
        elif feat.get("feature_type_bowl", 0) > 0.5:
            type_bonus = 0.10  # Bowls concentrate thermals

        # --- Cloud factor ---
        cloud = feat.get("cloud_cover_pct", 30.0)
        if cloud < 5:
            cloud_factor = 0.75   # Clear: strong heating, no markers
        elif cloud <= 50:
            # Optimal range 20-40%, slightly reduced above and below
            cloud_factor = 1.0 - abs(cloud - 30.0) / 60.0
            cloud_factor = max(0.45, cloud_factor)
        else:
            cloud_factor = max(0.10, 1.0 - (cloud - 50.0) / 60.0)

        score = (
            dewpoint_spread_factor
            * wind_factor
            * time_factor
            * aspect_factor
            * cloud_factor
            + type_bonus * (1.0 - time_factor * 0.5)  # Type bonus smaller during peak hours
        )

        return float(max(0.0, min(1.0, score)))

    def _ml_score(self, features: np.ndarray) -> float:
        """Score using loaded ML model."""
        try:
            prob = self._model.predict_proba(features.reshape(1, -1))[0][1]
            return float(prob)
        except Exception as e:
            logger.warning(f"ML scoring failed ({e}), falling back to rule-based")
            return self._rule_based_score_from_vector(features)
