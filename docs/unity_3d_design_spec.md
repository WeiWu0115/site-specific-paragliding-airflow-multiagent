# Unity 3D Visualisation Design Spec — Eagle Ridge Airflow Overlay

## Overview

This document specifies the visual design for the Unity 3D airflow overlay layer,
covering particle systems, mesh overlays, UI elements, and interaction model.

Site: Eagle Ridge Flying Site (35.492°N, 118.187°W, Tehachapi Mountains, CA)
Unity version: 2022.3 LTS (URP)
Target: PC / VR headset (Meta Quest 3, PCVR)

---

## Scene Setup

### Terrain

- Import 30m SRTM DEM for the 20×20 km area centred on 35.492°N, 118.187°W.
- Apply a photorealistic terrain material (satellite imagery as albedo, normal map from DEM).
- Site centre placed at Unity world origin (0, 0, 0).
- Y-up coordinate system; terrain height = (elevation_m - 1340) metres.

### Coordinate Conversion

```csharp
// Equirectangular (accurate to ~0.5m at 20km radius)
const float METRES_PER_DEG = 111320f;
const float SITE_LAT = 35.492f;
const float SITE_LON = -118.187f;
const float SITE_ELEV = 1340f;
const float LAT_COS = Mathf.Cos(SITE_LAT * Mathf.Deg2Rad);

Vector3 GeoToUnity(float lat, float lon, float elevM)
{
    float x = (lon - SITE_LON) * LAT_COS * METRES_PER_DEG;
    float z = (lat - SITE_LAT) * METRES_PER_DEG;
    float y = elevM - SITE_ELEV;
    return new Vector3(x, y, z);
}
```

---

## Airflow Zone Visuals

### Thermal Zones (ThermalZone)

- Render as a **translucent vertical cylinder** or polygon prism above the trigger area.
- Base at trigger elevation (e.g. ground level), top at cloud base (default 2100m AMSL).
- Particle system inside: upward-moving particles (dust/smoke aesthetic).

| Confidence | Colour | Opacity | Particle density |
|-----------|--------|---------|-----------------|
| ≥ 0.70 | `#f97316` (orange) | 0.55 | medium |
| 0.45–0.70 | `#f59e0b` (amber) | 0.38 | low |
| < 0.45 | `#fcd34d` (pale amber) | 0.22 | low |

- Particle count scales linearly with `render_hints.particle_density`:
  - `low`: 30 particles/s
  - `medium`: 80 particles/s
  - `high`: 150 particles/s

### Ridge Corridors (RidgeCorridor)

- Render as a **ribbon** extruded along the `line_geojson` LineString.
- Width: 60m on each side of the ridge line.
- Arrow meshes spaced along the ribbon pointing upward along the lift axis.

| Confidence | Colour | Opacity | Arrow density |
|-----------|--------|---------|--------------|
| ≥ 0.70 | `#10b981` (green) | 0.65 | dense (1 per 80m) |
| 0.45–0.70 | `#6ee7b7` (light green) | 0.42 | sparse (1 per 200m) |
| < 0.45 | `#d1fae5` (pale green) | 0.28 | sparse |

### Caution Zones (CautionZone)

- Render as a **pulsing transparent sphere or box** at the feature centre.
- Rotor risk (`caution_type == "ROTOR_RISK"`): red pulsing mesh, hazard icon floating above.
- General caution: amber translucent box.

| Type | Colour | Pulse rate |
|------|--------|-----------|
| `ROTOR_RISK` | `#dc2626` (red) | 0.8 Hz |
| `CAUTION` | `#f59e0b` (amber) | 0.4 Hz |

### Climb Hotspots (ClimbHotspot)

- Render as a **glowing vertical cone** at the hotspot lat/lon/elevation.
- Cone radius = `radius_m`, height = 300m.
- Inner glow intensity scales with `avg_climb_ms` (max 5 m/s = max glow).
- Label above: `name`, `avg_climb_ms` m/s.

---

## Launch Point Markers

- 3D launch pad marker at each `LaunchPoint` position.
- Arrow indicating `facing_degrees`.
- Green when wind is within optimal range (`optimal_wind_dir_deg`, `optimal_wind_speed_kmh`).
- Amber when marginal, red when outside limits.

---

## Time Slider Integration

- A Unity UI time slider (6–20 UTC) controls which zones are shown.
- On slider change: call `SiteOverlay.GetThermalZonesAt(hour)` and `GetRidgeCorridorsAt(hour)`.
- Smooth fade in/out (0.5s) when zones activate/deactivate.

---

## Agent Layer Toggle

- A panel of toggle buttons (one per agent: Weather, Terrain, Cloud, Local Knowledge, Flight History, Risk).
- When an agent is toggled off, hide all zones whose `agent_sources` list is exclusively that agent.
- When multiple agents support a zone, it stays visible unless all supporting agents are toggled off.

---

## UI Panels

### Recommendation Panel (World-Space)
- Floating panel anchored near the launch area.
- Lists top 3 recommendations from `SiteOverlay.recommendations`.
- Colour-coded by `RecommendationOverlay.PriorityColor()`.

### Advisory Banner
- Persistent, non-dismissible text overlay at bottom of screen.
- Text: `SiteOverlay.advisory_disclaimer`.
- Yellow background, high contrast.

---

## VR Considerations

- All UI panels: world-space canvas, grabbable and repositionable.
- Gaze-dwell to expand zone details (1.5s dwell threshold).
- Controller ray-cast to select a zone and show `AgentClaim` evidence panel.
- Particle density auto-reduces to `low` in VR to maintain 72 fps.

---

## Performance Budget

| Element | Max count | GPU cost estimate |
|---------|----------|------------------|
| Thermal zone cylinders | 10 | Low |
| Particle systems | 5 (one per visible thermal zone) | Medium |
| Ridge corridor ribbons | 5 | Low |
| Caution zone pulses | 8 | Low |
| Climb hotspot cones | 10 | Low |

Target: 90 fps on RTX 3060 (PCVR), 72 fps on Meta Quest 3 with dynamic resolution.
