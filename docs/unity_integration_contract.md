# Unity Integration Contract

Version: 1.0
Status: Stable
Maintainer: Backend team

This document is the authoritative contract between the Python backend and the Unity C# client.
Any breaking change to the overlay schema requires a version bump and migration guide.

---

## Versioning Policy

- The `GET /health` response includes `api_version` (string, semver).
- Breaking changes: increment major version.
- Additive changes: increment minor version.
- The `X-Api-Version` response header echoes the current version.

---

## Guaranteed Stable Fields (v1.x)

The following fields are guaranteed to remain present and type-stable across all v1.x releases.
Unity C# code may depend on them without defensive null-checking beyond standard practice.

### SiteOverlay

| Field | Type | Stable since |
|-------|------|-------------|
| `site_id` | string | 1.0 |
| `generated_at` | ISO-8601 string | 1.0 |
| `coordinate_system` | string (`"WGS84"`) | 1.0 |
| `thermal_zones` | ThermalZone[] | 1.0 |
| `ridge_corridors` | RidgeCorridor[] | 1.0 |
| `caution_zones` | CautionZone[] | 1.0 |
| `recommendations` | RecommendationItem[] | 1.0 |
| `advisory_disclaimer` | string | 1.0 |
| `uncertainty_summary` | string | 1.0 |

### ThermalZone / RidgeCorridor / CautionZone

| Field | Type | Stable since |
|-------|------|-------------|
| `id` | string | 1.0 |
| `name` | string | 1.0 |
| `confidence` | float | 1.0 |
| `render_hints` | RenderHints | 1.0 |
| `valid_hours` | int[] | 1.0 |
| `notes` | string | 1.0 |

### RenderHints

| Field | Type | Stable since |
|-------|------|-------------|
| `color` | string (hex) | 1.0 |
| `opacity` | float | 1.0 |

---

## Optional Fields (may be null)

The following fields may be null or absent. Unity code must handle null gracefully.

| Field | Notes |
|-------|-------|
| `session_id` | Null when no planning session has been run |
| `terrain.terrain_mesh_url` | Null unless a DEM mesh has been pre-generated |
| `polygon_geojson` | Null if spatial data is unavailable |
| `line_geojson` | Null if spatial data is unavailable |
| `conflict_description` | Null when no inter-agent conflict exists |
| `uncertainty_note` | Null when confidence is high |
| `particle_density` | May be absent in `render_hints` for non-thermal zones |
| `arrow_density` | May be absent in `render_hints` for non-ridge zones |
| `hazard_marker` | Defaults to false if absent |

---

## Deprecated Fields (planned removal in v2.0)

None at this time.

---

## Known Limitations

1. **agent_layers**: This field contains a nested dictionary that is not directly serialisable by Unity's built-in `JsonUtility`. Use Newtonsoft.Json for Unity (`com.unity.nuget.newtonsoft-json`) to deserialise it.

2. **GeoJSON coordinates**: The `coordinates` field in `GeoJsonGeometry` uses a variable-depth array. For Polygon: `[[[lon, lat], ...]]`. For LineString: `[[lon, lat, elev?], ...]`. Parse carefully.

3. **Climb hotspots**: The `climb_hotspots` field is currently a `List<object>` on the backend. The schema will be finalised in v1.1 when the `ClimbHotspot` model is promoted to stable.

---

## Change Log

### v1.0 (current)
- Initial release with `thermal_zones`, `ridge_corridors`, `caution_zones`, `recommendations`.
- `render_hints` standardised with `color`, `opacity`, `particle_density`, `arrow_density`, `hazard_marker`.
- C# stubs provided in `unity/csharp_stubs/`.

---

## Contact

For questions about this contract, open a GitHub issue tagged `unity-integration`.
For time-sensitive issues during development, contact the backend team directly.
