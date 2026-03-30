"""
Feature extraction for ML thermal scoring in paraglide-backend.

Converts raw weather and terrain data into numerical feature vectors
suitable for XGBoost/LightGBM training and inference.
"""

import math
from typing import Any

import numpy as np
from loguru import logger


FEATURE_NAMES = [
    # Weather features
    "temp_c",
    "dewpoint_spread_c",
    "wind_speed_kmh",
    "wind_dir_sin",
    "wind_dir_cos",
    "cloud_cover_pct",
    "hour_sin",
    "hour_cos",
    "pressure_hpa",
    "humidity_pct",
    # Terrain features
    "aspect_alignment_cos",
    "slope_deg",
    "elevation_m",
    "feature_type_ridge",
    "feature_type_bowl",
    "feature_type_riverbed",
]


class FeatureExtractor:
    """
    Extracts numerical feature vectors from weather and terrain data.

    Features are engineered to be:
    - Continuous where possible (avoid ordinal encoding artifacts)
    - Cyclical for periodic values (hour, wind direction — use sin/cos encoding)
    - Normalized approximately to 0-1 range or standard scale
    """

    def extract_weather_features(self, weather_hour: Any) -> dict[str, float]:
        """
        Extract numerical weather features from a single WeatherHour.

        Args:
            weather_hour: WeatherHour dataclass or dict with weather values

        Returns:
            Dict of feature_name -> float
        """
        if hasattr(weather_hour, "__dict__"):
            temp_c = float(getattr(weather_hour, "temp_c", 20.0) or 20.0)
            dewpoint_c = float(getattr(weather_hour, "dewpoint_c", 10.0) or 10.0)
            wind_speed_kmh = float(getattr(weather_hour, "wind_speed_kmh", 15.0) or 15.0)
            wind_dir_deg = float(getattr(weather_hour, "wind_dir_deg", 225.0) or 225.0)
            cloud_cover_pct = float(getattr(weather_hour, "cloud_cover_pct", 30.0) or 30.0)
            pressure_hpa = float(getattr(weather_hour, "pressure_hpa", 1013.0) or 1013.0)
            humidity_pct = float(getattr(weather_hour, "humidity_pct", 40.0) or 40.0)
            time = getattr(weather_hour, "time", None)
        else:
            temp_c = float(weather_hour.get("temp_c", 20.0))
            dewpoint_c = float(weather_hour.get("dewpoint_c", 10.0))
            wind_speed_kmh = float(weather_hour.get("wind_speed_kmh", 15.0))
            wind_dir_deg = float(weather_hour.get("wind_dir_deg", 225.0))
            cloud_cover_pct = float(weather_hour.get("cloud_cover_pct", 30.0))
            pressure_hpa = float(weather_hour.get("pressure_hpa", 1013.0))
            humidity_pct = float(weather_hour.get("humidity_pct", 40.0))
            time = weather_hour.get("time")

        # Hour of day (0-23) from time
        hour = 12
        if time is not None:
            if hasattr(time, "hour"):
                hour = time.hour
            else:
                try:
                    from datetime import datetime
                    hour = datetime.fromisoformat(str(time)).hour
                except Exception:
                    pass

        # Cyclical encoding for wind direction (sin/cos)
        wind_dir_rad = math.radians(wind_dir_deg)
        wind_dir_sin = math.sin(wind_dir_rad)
        wind_dir_cos = math.cos(wind_dir_rad)

        # Cyclical encoding for hour of day
        hour_sin = math.sin(2 * math.pi * hour / 24.0)
        hour_cos = math.cos(2 * math.pi * hour / 24.0)

        # Dewpoint spread (proxy for atmospheric dryness)
        dewpoint_spread_c = max(0.0, temp_c - dewpoint_c)

        return {
            "temp_c": temp_c,
            "dewpoint_spread_c": dewpoint_spread_c,
            "wind_speed_kmh": wind_speed_kmh,
            "wind_dir_sin": wind_dir_sin,
            "wind_dir_cos": wind_dir_cos,
            "cloud_cover_pct": cloud_cover_pct,
            "hour_sin": hour_sin,
            "hour_cos": hour_cos,
            "pressure_hpa": pressure_hpa,
            "humidity_pct": humidity_pct,
        }

    def extract_terrain_features(
        self,
        feature: dict[str, Any],
        wind_dir_deg: float,
    ) -> dict[str, float]:
        """
        Extract numerical terrain features from a terrain feature dict.

        Args:
            feature: Terrain feature dict from site profile
            wind_dir_deg: Current wind direction in degrees

        Returns:
            Dict of feature_name -> float
        """
        attrs = feature.get("attributes", {})
        feature_type = feature.get("type", "unknown")

        # Aspect alignment: how well the feature faces into the wind
        # Cos(angle between wind and aspect) — 1.0 = direct headwind, -1.0 = tailwind
        aspect_deg = attrs.get("aspect_deg", 180.0)
        angle_diff_rad = math.radians(wind_dir_deg - aspect_deg)
        aspect_alignment_cos = math.cos(angle_diff_rad)

        slope_deg = attrs.get("slope_deg_avg", 20.0) or 20.0
        elevation_m = attrs.get("crest_elevation_m", attrs.get("elevation_m", 1000.0)) or 1000.0

        # One-hot encode feature type
        feature_type_ridge = 1.0 if feature_type == "ridge" else 0.0
        feature_type_bowl = 1.0 if feature_type == "bowl" else 0.0
        feature_type_riverbed = 1.0 if feature_type == "riverbed" else 0.0

        return {
            "aspect_alignment_cos": aspect_alignment_cos,
            "slope_deg": float(slope_deg),
            "elevation_m": float(elevation_m),
            "feature_type_ridge": feature_type_ridge,
            "feature_type_bowl": feature_type_bowl,
            "feature_type_riverbed": feature_type_riverbed,
        }

    def combine_features(
        self,
        weather_feats: dict[str, float],
        terrain_feats: dict[str, float],
    ) -> np.ndarray:
        """
        Combine weather and terrain feature dicts into a single feature vector.

        Returns a 1D numpy array in the order specified by FEATURE_NAMES.
        """
        combined = {**weather_feats, **terrain_feats}
        vector = np.array([combined.get(name, 0.0) for name in FEATURE_NAMES], dtype=np.float32)
        return vector

    def build_feature_matrix(
        self,
        weather_hours: list[Any],
        terrain_features: list[dict[str, Any]],
        wind_dir_deg: float,
    ) -> np.ndarray:
        """
        Build a feature matrix for all (weather_hour, terrain_feature) combinations.

        Useful for batch scoring during planning sessions.

        Returns:
            2D array of shape (n_weather * n_terrain, n_features)
        """
        rows = []
        for wh in weather_hours:
            wf = self.extract_weather_features(wh)
            for tf_dict in terrain_features:
                tf = self.extract_terrain_features(tf_dict, wind_dir_deg)
                vec = self.combine_features(wf, tf)
                rows.append(vec)

        if not rows:
            return np.empty((0, len(FEATURE_NAMES)), dtype=np.float32)

        return np.vstack(rows)
