# ML Plan — Thermal Scoring and Launch Timing

## Current State

The ML layer (`backend/ml/`) provides:

1. **Rule-based fallback** — `ThermalScorer._rule_based_score_from_vector()` with documented coefficients matching the thermal index formula used by `WeatherAgent.score_hour()`.
2. **XGBoost loader** — `ThermalScorer.load_model(path)` reads a pre-trained XGBoost `Booster` from a `.json` or `.ubj` artifact. Falls back to rule-based if no artifact is present.
3. **Confidence calibration** — `ConfidenceCalibrator` wraps isotonic regression from scikit-learn. Acts as identity until fitted on labelled data.

## Feature Set

`FeatureExtractor` produces 16 features per weather hour × terrain context:

| Feature | Description |
|---------|-------------|
| `temp_c` | Surface temperature |
| `dewpoint_c` | Surface dewpoint |
| `temp_dew_spread` | `temp_c - dewpoint_c` |
| `wind_speed_kmh` | Surface wind speed |
| `wind_sin`, `wind_cos` | Cyclical encoding of wind direction |
| `cloud_cover_pct` | Total cloud cover |
| `hour_sin`, `hour_cos` | Cyclical encoding of UTC hour |
| `pressure_hpa` | Surface pressure |
| `humidity_pct` | Relative humidity |
| `ridge_alignment` | Dot product of wind with face normal (terrain) |
| `slope_deg` | DEM-derived slope |
| `aspect_deg` | DEM-derived aspect |
| `elevation_m` | Feature elevation |
| `is_south_facing` | Binary: aspect 120–270° |

## Training Data Strategy

### Phase 1 (current): Rule-based baseline
- No labelled data required.
- `ThermalScorer` uses the analytic formula.
- Baseline accuracy estimated from physical reasonableness, not empirical validation.

### Phase 2: IGC-derived weak labels
- **Positive labels**: flight segments with vario > 1.5 m/s sustained for > 60s in the South Bowl polygon.
- **Negative labels**: segments within 500m of a positive cluster but with vario < -0.5 m/s.
- Label quality is limited by GPS noise and track sparsity.
- Expected: 200–500 labelled segments from 12 existing tracks (Eagle Ridge).

### Phase 3: Expert-validated labels
- Pilots annotate replay sessions with "thermal quality" ratings (1–5).
- Use `notebooks/03_baseline_thermal_model.ipynb` to train and evaluate.
- Isotonic calibration applied to output probabilities.

## Model Selection

| Candidate | Pros | Cons |
|-----------|------|------|
| XGBoost | Fast inference, handles tabular data, interpretable feature importance | Requires scikit-learn, offline training |
| LightGBM | Faster training on large datasets | Similar to XGBoost |
| Linear regression | Fully interpretable, deployable without ML deps | Lower accuracy on non-linear features |
| Rule-based (current) | No data required, physically motivated | Fixed coefficients, no adaptation |

Recommendation: XGBoost for Phase 2+. Rule-based remains the safe fallback.

## Training Script

`scripts/train_baseline.py`:
- Generates synthetic training data from the diurnal mock provider
- Trains XGBoost with 5-fold cross-validation
- Saves artifact to `backend/ml/artifacts/thermal_scorer.json`
- Records a `ModelVersion` DB entry with feature importances

Run:
```bash
cd site-specific-paragliding-airflow-multiagent
uv run python scripts/train_baseline.py
```

## Evaluation Metrics

| Metric | Target (Phase 2) |
|--------|-----------------|
| AUC-ROC | > 0.75 |
| Brier score | < 0.18 |
| Calibration (ECE) | < 0.08 |

## Limitations and Caveats

- **Small dataset**: Eagle Ridge has ~12 flight tracks at time of writing. Model generalisation is limited.
- **Label noise**: IGC vario is noisy; brief climbs may be thermal or mechanical.
- **Temporal leakage**: avoid splitting train/test by random shuffle — split by date.
- **Site specificity**: a model trained on Eagle Ridge data should not be applied to other sites without retraining.
- **Not safety-critical**: the ML layer is advisory. All outputs carry explicit uncertainty and advisory disclaimers.
