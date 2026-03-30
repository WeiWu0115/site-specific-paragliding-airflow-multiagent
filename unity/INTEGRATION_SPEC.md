# Unity Integration Contract — Site-Specific Airflow Overlay

Version: 1.0
Backend API version: see `/health` endpoint
Site: Eagle Ridge Flying Site (eagle_ridge)

---

## 1. Endpoint Reference

| Method | Path                          | Description                                      |
|--------|-------------------------------|--------------------------------------------------|
| GET    | `/health`                     | Liveness check; returns `site_id`                |
| GET    | `/unity/overlays`             | Latest overlay for the configured site           |
| GET    | `/unity/overlays/{session_id}`| Overlay for a specific planning session          |
| POST   | `/planning`                   | Trigger a new planning session; returns result   |
| GET    | `/forecast`                   | Raw hourly weather forecast (Open-Meteo)         |
| GET    | `/terrain`                    | Terrain feature GeoJSON                          |

### POST /planning — Request Body

```json
{
  "site_id": "eagle_ridge",
  "target_date": "2025-06-15",         // optional ISO date
  "target_time_utc": "12:00"           // optional HH:MM
}
```

### GET /unity/overlays — Response Shape

See `payloads/full_overlay_example.json` for a complete example.

Top-level keys:

```
site_id            string
session_id         integer | null
generated_at       ISO-8601 timestamp
coordinate_system  "WGS84"
time_range         { from: ISO-8601, to: ISO-8601 }
terrain            { launches, landings, features, terrain_mesh_url }
thermal_zones      ThermalZone[]
ridge_corridors    RidgeCorridor[]
caution_zones      CautionZone[]
climb_hotspots     ClimbHotspot[]
recommendations    RecommendationOverlay[]
agent_layers       { [agent_name]: AgentLayerData }
uncertainty_summary  string
advisory_disclaimer  string
```

---

## 2. Data Structures

### ThermalZone

```json
{
  "id": "tz_001",
  "name": "South Bowl Thermal",
  "confidence": 0.72,
  "uncertainty": 0.28,
  "evidence_count": 4,
  "evidence_sources": ["weather_agent", "terrain_agent", "flight_history_agent"],
  "polygon_geojson": {
    "type": "Polygon",
    "coordinates": [[[...WGS84 lon/lat pairs...]]]
  },
  "elevation_center_m": 1480,
  "valid_hours": [10, 11, 12, 13, 14],
  "agent_sources": ["weather", "terrain", "flight_history"],
  "notes": "South-facing bowl. Triggers when spread > 8°C.",
  "render_hints": {
    "color": "#f97316",
    "opacity": 0.55,
    "particle_density": "medium"
  }
}
```

### RidgeCorridor

```json
{
  "id": "rc_001",
  "name": "Eagle Ridge Main Corridor",
  "confidence": 0.81,
  "uncertainty": 0.19,
  "evidence_count": 5,
  "line_geojson": {
    "type": "LineString",
    "coordinates": [[lon, lat, elevM], ...]
  },
  "elevation_m": 1420,
  "valid_hours": [9, 10, 11, 12, 13, 14, 15],
  "agent_sources": ["terrain", "weather", "local_knowledge"],
  "notes": "SW-facing ridge. Best lift when wind 200-230°.",
  "render_hints": {
    "color": "#10b981",
    "opacity": 0.65,
    "arrow_density": "dense"
  }
}
```

### CautionZone

```json
{
  "title": "West Lee Sink — Rotor Risk",
  "description": "Mechanical turbulence in the lee of Pine Tree Line when W > 20 km/h.",
  "confidence": 0.78,
  "caution_type": "ROTOR_RISK",
  "conflict_description": "Weather agent (caution) vs terrain agent (neutral)",
  "feature_name": "West Lee Sink Zone",
  "render_hints": {
    "color": "#dc2626",
    "opacity": 0.45,
    "hazard_marker": true
  }
}
```

---

## 3. Coordinate Conversion

Eagle Ridge site centre reference:

```
lat_centre = 35.492
lon_centre = -118.187
elev_centre_m = 1340
METRES_PER_DEGREE = 111_320
```

Unity world-space (Y-up):

```
unity_x = (lon - lon_centre) * cos(lat_centre_rad) * METRES_PER_DEGREE
unity_z = (lat - lat_centre) * METRES_PER_DEGREE
unity_y = elevation_m - elev_centre_m
```

For terrain mesh alignment, use `unity_y` directly as height above the scene
origin, which sits at launch elevation (1340m AMSL).

---

## 4. Polling Strategy

The backend runs planning on-demand via `POST /planning`.
Unity should:

1. Call `POST /planning` when the scene loads or the user requests a refresh.
2. Store the returned `session_id`.
3. Call `GET /unity/overlays/{session_id}` to fetch the rendered overlay.
4. Re-poll `GET /unity/overlays` every 5 minutes for live weather updates
   (the overlay endpoint triggers a lightweight weather refresh).

Avoid hammering the endpoint faster than 60-second intervals during flight.

---

## 5. Error Handling

All API errors return JSON:

```json
{ "detail": "human-readable error message" }
```

HTTP status codes follow REST conventions (400, 404, 422, 500).
`AirflowApiClient` in the C# stubs throws `AirflowApiException` for non-2xx responses.

---

## 6. Versioning

The overlay schema is versioned via the `generated_at` timestamp. Breaking changes
will be announced in `CHANGELOG.md` and the `X-Api-Version` response header.
