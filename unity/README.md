# Unity Integration — Eagle Ridge Airflow Visualisation

This directory contains everything needed to connect a Unity 3D project to the
Eagle Ridge multi-agent airflow planning backend.

## Contents

```
unity/
├── README.md                  ← you are here
├── INTEGRATION_SPEC.md        ← full API contract and coordinate conventions
├── payloads/
│   ├── thermal_zones_example.json
│   ├── ridge_lift_example.json
│   ├── caution_zones_example.json
│   ├── climb_hotspots_example.json
│   └── full_overlay_example.json
└── csharp_stubs/
    ├── Models/
    │   ├── AirflowZone.cs
    │   ├── SiteOverlay.cs
    │   ├── AgentClaim.cs
    │   └── RecommendationOverlay.cs
    └── API/
        └── AirflowApiClient.cs
```

## Quick Start

1. Copy `csharp_stubs/` into your Unity project under `Assets/Scripts/Airflow/`.
2. Set `AirflowApiClient.BaseUrl` to your backend URL (default: `http://localhost:8000`).
3. Call `AirflowApiClient.GetOverlayAsync(sessionId)` to fetch a `SiteOverlay` object.
4. Use `SiteOverlay.ThermalZones`, `RidgeCorridors`, and `CautionZones` to drive
   particle systems, mesh overlays, and hazard markers.

## Coordinate System

All GeoJSON coordinates are **WGS-84 longitude/latitude** (EPSG:4326).
Elevations are **metres above mean sea level (AMSL)**.

Site centre: **35.492°N, 118.187°W** (Eagle Ridge Main launch).

Convert to Unity world-space using:

```csharp
// Equirectangular approximation for small areas (~20 km radius)
float unityX = (lon - siteCentreLon) * Mathf.Cos(siteCentreLatRad) * MetresPerDegree;
float unityZ = (lat - siteCentreLat) * MetresPerDegree;
float unityY = elevationM - siteCentreElevM;
```

`MetresPerDegree ≈ 111_320`.

## Render Hints

Each overlay zone carries `render_hints`:

| Field            | Type    | Notes                                      |
|------------------|---------|--------------------------------------------|
| `color`          | string  | Hex RGB, e.g. `#f97316`                    |
| `opacity`        | float   | 0.0–1.0                                    |
| `particle_density` | string | `"low"` / `"medium"` / `"high"`          |
| `arrow_density`  | string  | `"sparse"` / `"dense"` (ridge corridors)  |
| `hazard_marker`  | bool    | Show hazard icon for caution zones         |

## Advisory

**This integration is for research and visualisation only.**
It is not certified for operational flight planning. Unity renders are
illustrative — always conduct a full ground-based preflight assessment
before flying Eagle Ridge or any site.
