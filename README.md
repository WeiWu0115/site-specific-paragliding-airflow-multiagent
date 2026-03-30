# site-specific-paragliding-airflow-multiagent

> "The mountain does not speak in averages. It speaks in particular winds, particular moments, particular ground."

---

## What This System Is

A **site-specific, multi-agent sensemaking system** for paragliding airflow planning. It combines weather forecast data, terrain analysis, historical flight tracks, cloud observation, and structured local expert knowledge to produce explainable, uncertainty-aware recommendations for a specific flying site.

The system is built around a **negotiation architecture**: multiple specialized agents each produce typed, evidence-backed claims about conditions at specific zones. A NegotiationAgent aggregates these claims, detects conflicts, and produces ranked recommendations with full provenance traces. Every recommendation shows *which agents agreed*, *what evidence they cited*, and *what they disagreed about*.

The seed site is **Eagle Ridge Flying Site** in the Tehachapi Mountains, California (35.49°N, 118.19°W). All terrain, heuristics, and example data are modeled on this fictional-but-realistic site.

---

## What This System Is NOT

- **Not an autopilot or flight control system.** It never commands or controls any aircraft.
- **Not a safety-certified system.** It provides no guarantees of accuracy or completeness.
- **Not a replacement for pilot judgment, training, or site mentorship.** Use of this system does not substitute for proper paragliding education, site briefings, or experienced guidance.
- **Not a real-time safety instrument.** All outputs are advisory suggestions to support pre-flight sensemaking, not in-flight navigation commands.

---

## Advisory Disclaimer

**All outputs from this system are advisory only. Paragliding is a high-risk activity. Conditions in the air change rapidly and unpredictably. This system cannot observe actual air movement, actual rotor turbulence, or actual weather. Always rely on your own judgment, local site experts, and current direct observation. Do not fly beyond your skill level. If in doubt, do not fly.**

---

## Quick Start

### Prerequisites
- Docker and Docker Compose
- Python 3.11+ (for scripts)
- Node.js 18+ (for frontend)

### 1. Clone and configure

```bash
git clone <repo>
cd site-specific-paragliding-airflow-multiagent
cp .env.example .env
```

### 2. Start infrastructure

```bash
docker-compose up -d postgres redis
```

### 3. Initialize database and seed site

```bash
cd backend
pip install uv
uv pip install -e ".[dev]"
alembic upgrade head
python ../scripts/seed_site.py
```

### 4. Start backend

```bash
uvicorn backend.api.main:app --reload --host 0.0.0.0 --port 8000
```

### 5. Start frontend

```bash
cd frontend/web
npm install
npm run dev
```

### 6. Full Docker Compose (all services)

```bash
docker-compose up --build
```

Open http://localhost:3000 for the planning dashboard.
Open http://localhost:8000/docs for the API documentation.

---

## Repository Structure

```
site-specific-paragliding-airflow-multiagent/
├── backend/
│   ├── agents/                   # Multi-agent reasoning layer
│   │   ├── base.py               # Claim/Evidence dataclasses, AgentBase
│   │   ├── weather_agent.py      # Thermal window scoring from forecast
│   │   ├── terrain_agent.py      # Ridge/sink/rotor analysis from DEM + site profile
│   │   ├── cloud_agent.py        # Cloud cover thermal suppression/enhancement
│   │   ├── local_knowledge_agent.py  # Site heuristic matching
│   │   ├── flight_history_agent.py   # Spatial clustering of historical climbs
│   │   ├── risk_agent.py         # Conflict detection, caution escalation
│   │   └── negotiation_agent.py  # Claim aggregation, ranking, arbitration
│   ├── api/                      # FastAPI application
│   │   ├── main.py
│   │   ├── deps.py
│   │   └── routes/               # site, forecast, terrain, clouds, planning, agents, knowledge, tracks, replay, unity
│   ├── config/
│   │   ├── settings.py           # Pydantic settings
│   │   └── site_profiles/
│   │       └── eagle_ridge.json  # Full site profile with heuristics
│   ├── data_ingestion/
│   │   ├── weather/              # WeatherProvider base + Open-Meteo + mock
│   │   ├── terrain/              # DEM loader + terrain analyzer
│   │   ├── clouds/               # CloudProvider base + mock
│   │   └── flights/              # IGC + GPX parsers
│   ├── db/                       # SQLAlchemy models + session
│   ├── knowledge/                # Schema, ingestion, retrieval
│   ├── ml/                       # Feature extraction, thermal scorer, launch timing
│   ├── spatial/                  # PostGIS queries, Unity overlay builder
│   ├── services/                 # Planning service, replay service
│   ├── alembic/                  # Database migrations
│   └── tests/
├── frontend/web/                 # Next.js 14 planning dashboard
│   └── src/
│       ├── pages/                # index.tsx (dashboard), replay.tsx
│       ├── components/           # WeatherPanel, TriggerZonePanel, LaunchTimingPanel, etc.
│       └── lib/                  # TypeScript types, API client
├── unity/
│   ├── csharp_stubs/             # C# data models + API client for Unity
│   ├── payloads/                 # Example JSON payloads
│   ├── README.md
│   ├── INTEGRATION_SPEC.md
│   └── (Unity project files added separately)
├── docs/
│   ├── architecture.md
│   ├── data_schema.md
│   ├── provider_interfaces.md
│   ├── ml_plan.md
│   ├── research_framing.md
│   ├── expert_interview_guide.md
│   ├── unity_3d_design_spec.md
│   ├── future_xr_extension.md
│   └── unity_integration_contract.md
├── notebooks/                    # Exploration + model training notebooks
├── scripts/                      # seed_site.py, import_igc.py, train_baseline.py
├── docker-compose.yml
├── .env.example
└── .gitignore
```

---

## Phase Roadmap

| Phase | Focus | Status |
|-------|-------|--------|
| **Phase 1** | Core architecture: agents, DB schema, mock providers, site profile, API scaffolding | Current |
| **Phase 2** | Real data ingestion: Open-Meteo integration, IGC bulk import, expert interview import, PostGIS terrain analysis | Next |
| **Phase 3** | ML layer: XGBoost/LightGBM thermal scorer trained on labeled flight segments, confidence calibration, SHAP explainability | Planned |
| **Phase 4** | Unity 3D visualization: terrain mesh, zone overlays, confidence rendering, time playback | Planned |
| **Phase 5** | XR extension: HMD/spatial computing pre-flight planning mode, minimal in-flight cue mode | Future |

---

## Stack

| Layer | Technology |
|-------|-----------|
| Backend API | FastAPI + Uvicorn |
| Database | PostgreSQL 15 + PostGIS 3.3 |
| ORM / Migrations | SQLAlchemy (async) + Alembic |
| Caching | Redis 7 |
| Weather | Open-Meteo API (or mock) |
| ML | XGBoost, LightGBM, scikit-learn, numpy, pandas |
| Spatial | GeoAlchemy2, Shapely, pyproj, rasterio |
| Frontend | Next.js 14, React, TypeScript, Tailwind CSS, Recharts |
| 3D Visualization | Unity 2022 LTS (separate project) |
| Containerization | Docker + Docker Compose |
| Python tooling | uv, loguru, pydantic v2 |

---

## Adding a New Site

1. Create `backend/config/site_profiles/{site_slug}.json` following `eagle_ridge.json` as template
2. Set `SITE_ID={site_slug}` in `.env`
3. Run `scripts/seed_site.py` to populate DB
4. Optionally import IGC tracks with `scripts/import_igc.py`
5. Optionally import expert knowledge with `scripts/import_knowledge.py`

---

## License

Research prototype. Not licensed for commercial or safety-critical use.
