# Data Schema Reference

## Backend Pydantic Models

### Claim (base agent output)

```python
@dataclass
class Claim:
    id: str                          # UUID
    agent_name: str                  # e.g. "WeatherAgent"
    claim_type: ClaimType            # enum
    claim_text: str                  # human-readable summary
    confidence: float                # 0.0–1.0, post-calibration
    confidence_level: ConfidenceLevel
    evidence: list[Evidence]
    assumptions: list[str]
    spatial_scope: SpatialScope | None
    temporal_validity: TemporalValidity | None
    created_at: datetime
```

### ClaimType (enum)

| Value | Meaning |
|-------|---------|
| `THERMAL_ZONE` | Identified thermal trigger area |
| `RIDGE_LIFT` | Ridge producing consistent lift |
| `SINK_ZONE` | Area of consistent sink |
| `CAUTION` | General caution (overdevelopment, shear, etc.) |
| `LAUNCH_WINDOW` | Recommended launch time window |
| `ROTOR_RISK` | Mechanical turbulence / rotor hazard |

### Evidence

```python
@dataclass
class Evidence:
    source: str        # e.g. "open_meteo", "igc_cluster"
    description: str   # free text
    data_ref: dict     # arbitrary supporting data
```

### NegotiationResult (API response)

```python
@dataclass
class NegotiationResult:
    session_id: int
    launch_windows: list[LaunchWindow]
    trigger_zones: list[TriggerZone]
    ridge_corridors: list[TriggerZone]
    caution_zones: list[CautionZone]
    evidence_traces: dict[str, list[str]]
    uncertainty_summary: str
    agent_disagreements: list[AgentDisagreement]
    advisory_disclaimer: str
```

---

## Weather Data

### WeatherHour

| Field | Type | Unit |
|-------|------|------|
| `time` | ISO-8601 string | UTC |
| `temp_c` | float | °C |
| `dewpoint_c` | float | °C |
| `humidity_pct` | float | % |
| `wind_speed_kmh` | float | km/h |
| `wind_dir_deg` | float | degrees true |
| `pressure_hpa` | float | hPa |
| `cloud_cover_pct` | float | % |
| `precipitation_mm` | float | mm |
| `weather_code` | int | WMO code |

### Thermal Index Formula

```
spread        = max(0, temp_c - dewpoint_c)
dew_factor    = min(1, spread / 20)
wind_factor   = exp(-0.5 * ((wind_kmh - 15) / 7)^2)
time_factor   = exp(-0.5 * ((hour_utc - 13) / 2.5)^2)
cloud_factor  = (piecewise, see WeatherAgent.score_hour())
thermal_index = dew_factor * wind_factor * time_factor * cloud_factor
```

Thresholds: green ≥ 0.55, amber 0.35–0.55, red < 0.35.

---

## Flight Track Data

### IGC B-Record

Parsed fields:
- `time_utc` — HHMMSS
- `lat` — degrees, from DDMMmmmN format
- `lon` — degrees, from DDDMMMmmE format
- `validity` — `A` (GPS+baro) or `V` (GPS only)
- `press_alt_m` — barometric altitude
- `gnss_alt_m` — GPS altitude

### FlightSegment types

| Type | Vario threshold |
|------|----------------|
| `climb` | ≥ +0.3 m/s (5-point smoothed) |
| `glide` | -0.8 to +0.3 m/s |
| `sink` | < -0.8 m/s |

---

## Site Profile JSON

Located at `backend/config/site_profiles/eagle_ridge.json`.

Top-level keys:
- `id`, `name`, `description`
- `location`: `{ lat, lon, elevation_m, timezone }`
- `launches`: list of launch point objects
- `landings`: list of landing zone objects
- `terrain_features`: list of GeoJSON-based feature objects
- `known_heuristics`: list of condition-action rules
- `risk_notes`: list of string advisories
- `seasonal_notes`: dict of season → notes

### Heuristic Rule Format

```json
{
  "id": "h001",
  "description": "South Bowl triggers when temp-dew spread > 8°C",
  "conditions": [
    { "field": "temp_dew_spread", "operator": ">", "value": 8, "weight": 1.5 }
  ],
  "action": "THERMAL_ZONE",
  "sub_region": "south_bowl",
  "confidence_if_match": 0.75
}
```

---

## Unity Overlay Payload

See `unity/payloads/full_overlay_example.json` for a complete example.

Coordinate system: WGS-84 (EPSG:4326). Elevations in metres AMSL.

### RenderHints

| Field | Type | Values |
|-------|------|--------|
| `color` | string | Hex RGB `#rrggbb` |
| `opacity` | float | 0.0–1.0 |
| `particle_density` | string | `"low"` / `"medium"` / `"high"` |
| `arrow_density` | string | `"sparse"` / `"dense"` |
| `hazard_marker` | bool | Show hazard icon |
