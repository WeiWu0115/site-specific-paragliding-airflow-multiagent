# System Architecture — Site-Specific Paragliding Airflow Multi-Agent System

## Overview

This system implements a **multi-agent sensemaking architecture** for site-specific paragliding airflow planning. Multiple specialised agents independently analyse different data streams, produce typed `Claim` objects, and a `NegotiationAgent` arbitrates them into a ranked `NegotiationResult`.

The seed site is **Eagle Ridge Flying Site** (35.492°N, 118.187°W, Tehachapi Mountains, CA).

---

## Component Map

```
┌─────────────────────────────────────────────────────────────────┐
│                        External Data Sources                    │
│  Open-Meteo API  │  IGC/GPX Tracks  │  Expert Interviews        │
└────────┬─────────┴────────┬──────────┴────────┬─────────────────┘
         │                  │                   │
┌────────▼──────────────────▼───────────────────▼─────────────────┐
│                     Data Ingestion Layer                         │
│  WeatherProvider  │  IGCParser / GPXParser  │  KnowledgeIngestion│
└────────┬──────────┴──────────┬──────────────┴────────┬──────────┘
         │                     │                        │
┌────────▼─────────────────────▼────────────────────────▼─────────┐
│                        Agent Layer                               │
│  WeatherAgent  TerrainAgent  CloudAgent  LocalKnowledgeAgent     │
│  FlightHistoryAgent  RiskAgent                                   │
│  (each produces typed Claim objects with confidence + evidence)  │
└────────────────────────────┬────────────────────────────────────┘
                             │  List[Claim]
┌────────────────────────────▼────────────────────────────────────┐
│                     NegotiationAgent                             │
│  • Detects inter-agent conflicts (RiskAgent input)               │
│  • Applies per-agent reliability weights                         │
│  • Aggregates into NegotiationResult                             │
│  • Ranks launch windows, trigger zones, caution zones            │
└──────────┬─────────────────────────────────┬────────────────────┘
           │ NegotiationResult                │ Unity overlay
┌──────────▼──────────┐            ┌──────────▼──────────────────┐
│   FastAPI REST API  │            │   UnityOverlayBuilder        │
│   /planning         │            │   → UnityOverlayPayload      │
│   /unity/overlays   │            │   → GET /unity/overlays      │
└──────────┬──────────┘            └──────────────────────────────┘
           │
┌──────────▼──────────┐
│   Next.js Frontend  │
│   Dashboard / Replay│
└─────────────────────┘
```

---

## Agent Descriptions

### WeatherAgent
- **Input**: `WeatherForecast` from `WeatherProvider` (Open-Meteo or mock)
- **Output**: `LAUNCH_WINDOW`, `CAUTION` claims
- **Key method**: `score_hour(hour) -> float` — composite thermal index
  - `dewpoint_spread_factor * wind_factor * time_factor * cloud_factor`
  - All factors Gaussian-modelled; time peaks at 13:00 UTC, wind optimal at 15 km/h

### TerrainAgent
- **Input**: Site profile terrain features, current wind direction/speed
- **Output**: `RIDGE_LIFT`, `ROTOR_RISK`, `THERMAL_ZONE` claims
- **Key method**: `assess_feature(feature, wind_dir_deg, wind_speed_kmh)`
  - Ridge alignment: dot product of wind vector with face normal
  - Lee side: cross product sign check

### CloudAgent
- **Input**: `CloudObservation` from `CloudProvider`
- **Output**: `THERMAL_ZONE`, `CAUTION` claims
- Cloud cover → thermal interpretation:
  - <10%: punchy, unstable
  - 10–60%: good thermal development
  - >60%: suppressed / overdevelopment risk

### LocalKnowledgeAgent
- **Input**: Heuristics from site profile + knowledge DB
- **Output**: `THERMAL_ZONE`, `LAUNCH_WINDOW`, `CAUTION` claims
- Hard-excludes when a critical condition (weight ≥ 2.0) scores 0
- Weighted condition scoring: each condition scores 0–1, multiplied by weight

### FlightHistoryAgent
- **Input**: Segmented flight tracks from DB
- **Output**: `THERMAL_ZONE`, `SINK_ZONE` claims
- Greedy spatial clustering within 200m radius
- Confidence scales with track count (saturates at 20 tracks) and avg vario

### RiskAgent
- **Input**: All claims from other agents
- **Output**: `CAUTION`, conflict flags passed to NegotiationAgent
- Detects: inter-agent contradictions, low-confidence zones, high wind escalation

### NegotiationAgent
- **Input**: All claims from all agents
- **Output**: `NegotiationResult` with ranked recommendations
- Per-agent reliability weights: Risk=0.90, Weather=0.85, Terrain=0.80, LocalKnowledge=0.75, FlightHistory=0.70, Cloud=0.65

---

## Data Flow: Planning Session

```
POST /planning
  → PlanningService.run_planning_session()
      ├── WeatherProvider.get_forecast()        ─┐
      ├── CloudProvider.get_observation()        │ parallel
      ├── SpatialQueries.get_features_near()    ─┘
      │
      ├── WeatherAgent.run()                    ─┐
      ├── TerrainAgent.run()                     │ parallel
      ├── CloudAgent.run()                       │ asyncio.gather
      ├── LocalKnowledgeAgent.run()              │
      ├── FlightHistoryAgent.run()              ─┘
      │
      ├── RiskAgent.run(all_claims)
      │
      ├── NegotiationAgent.arbitrate(all_claims)
      │
      └── DB: save NegotiationSession, Recommendations
          → return NegotiationResult
```

---

## Database Schema (key tables)

| Table | Purpose |
|-------|---------|
| `site_profiles` | Site metadata (name, location, heuristics JSON) |
| `terrain_features` | GeoAlchemy2 geometry-tagged terrain features |
| `weather_snapshots` | Hourly forecast cache per site |
| `cloud_observations` | Cloud cover observations |
| `historical_flight_tracks` | IGC/GPX track metadata |
| `flight_segments` | Climb/glide/sink segments with vario data |
| `knowledge_items` | Expert knowledge statements |
| `agent_claims` | Per-agent claims for a session (persisted) |
| `negotiation_sessions` | Session metadata and result JSON |
| `recommendations` | Ranked output for a session |
| `model_versions` | ML artifact registry |

---

## ML Layer

Located in `backend/ml/`:

- `FeatureExtractor` — 16 features with cyclical sin/cos encoding for hour and wind direction
- `ThermalScorer` — rule-based fallback; XGBoost artifact loaded if available
- `LaunchTimingRanker` — combines thermal score + wind suitability + direction alignment
- `ConfidenceCalibrator` — isotonic regression; identity passthrough until fitted

---

## Advisory

This system is an experimental research prototype. It does not replace a qualified preflight briefing, RASP forecast, or instructor assessment. All recommendations carry an explicit `advisory_disclaimer` field that must be surfaced in any UI or API response.
