"""
Confidence calibration for paraglide-backend ML scores.

Wraps isotonic regression calibration to convert raw model scores
to well-calibrated probabilities. Defaults to identity (passthrough)
until trained on real labeled data.
"""

from dataclasses import dataclass, field
from typing import Any

import numpy as np
from loguru import logger


@dataclass
class CalibrationCurve:
    """Stores calibration curve data for visualization."""
    raw_scores: list[float] = field(default_factory=list)
    calibrated_scores: list[float] = field(default_factory=list)
    fraction_pos: list[float] = field(default_factory=list)  # Actual positive rate per bin
    is_fitted: bool = False


class ConfidenceCalibrator:
    """
    Isotonic regression calibration wrapper for thermal likelihood scores.

    Usage:
        calibrator = ConfidenceCalibrator()
        # After collecting labeled training data:
        calibrated = calibrator.calibrate(raw_scores, labels)
        # At inference:
        cal_score = calibrator.apply(raw_score)

    Until fit on real data, apply() returns the raw score unchanged (identity).

    Calibration improves reliability of probability estimates:
    "a score of 0.7 should mean thermals occurred 70% of the time"
    """

    def __init__(self) -> None:
        self._calibrator: Any = None
        self._is_fitted: bool = False
        self._curve = CalibrationCurve()

    def calibrate(
        self,
        raw_scores: list[float] | np.ndarray,
        labels: list[int] | np.ndarray,
    ) -> np.ndarray:
        """
        Fit the isotonic regression calibrator on labeled data.

        Args:
            raw_scores: Uncalibrated model scores (0-1)
            labels: Binary labels (1 = thermal confirmed, 0 = no thermal)

        Returns:
            Calibrated scores (0-1) for the training set
        """
        try:
            from sklearn.isotonic import IsotonicRegression
        except ImportError:
            logger.warning("scikit-learn not available, calibration will be identity")
            return np.array(raw_scores)

        raw = np.array(raw_scores, dtype=np.float64)
        y = np.array(labels, dtype=np.float64)

        if len(raw) < 10:
            logger.warning(
                f"Only {len(raw)} samples for calibration — need at least 10. "
                f"Using identity calibration."
            )
            return raw

        self._calibrator = IsotonicRegression(out_of_bounds="clip")
        calibrated = self._calibrator.fit_transform(raw, y)
        self._is_fitted = True

        # Store curve data
        n_bins = min(10, len(raw) // 5)
        bin_edges = np.linspace(0, 1, n_bins + 1)
        bin_raw = []
        bin_cal = []
        bin_frac = []

        for i in range(n_bins):
            mask = (raw >= bin_edges[i]) & (raw < bin_edges[i + 1])
            if mask.sum() > 0:
                bin_raw.append(float(raw[mask].mean()))
                bin_cal.append(float(calibrated[mask].mean()))
                bin_frac.append(float(y[mask].mean()))

        self._curve = CalibrationCurve(
            raw_scores=bin_raw,
            calibrated_scores=bin_cal,
            fraction_pos=bin_frac,
            is_fitted=True,
        )

        logger.info(
            f"Calibrator fitted on {len(raw)} samples. "
            f"Mean shift: {(calibrated - raw).mean():.3f}"
        )
        return calibrated

    def apply(self, raw_score: float) -> float:
        """
        Apply calibration to a single raw score.

        If not fitted, returns the raw score unchanged (identity).

        Args:
            raw_score: Uncalibrated score (0-1)

        Returns:
            Calibrated score (0-1)
        """
        if not self._is_fitted or self._calibrator is None:
            return max(0.0, min(1.0, raw_score))

        try:
            calibrated = self._calibrator.predict([[raw_score]])[0]
            return float(max(0.0, min(1.0, calibrated)))
        except Exception as e:
            logger.warning(f"Calibration apply failed: {e}")
            return max(0.0, min(1.0, raw_score))

    def apply_batch(self, raw_scores: list[float] | np.ndarray) -> np.ndarray:
        """Apply calibration to a batch of scores."""
        if not self._is_fitted or self._calibrator is None:
            return np.clip(np.array(raw_scores), 0.0, 1.0)
        try:
            result = self._calibrator.predict(np.array(raw_scores).reshape(-1, 1))
            return np.clip(result, 0.0, 1.0)
        except Exception as e:
            logger.warning(f"Batch calibration failed: {e}")
            return np.clip(np.array(raw_scores), 0.0, 1.0)

    @property
    def is_fitted(self) -> bool:
        """True if the calibrator has been fitted on training data."""
        return self._is_fitted

    @property
    def curve(self) -> CalibrationCurve:
        """Calibration curve data for visualization."""
        return self._curve
