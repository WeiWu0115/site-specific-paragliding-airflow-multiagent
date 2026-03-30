# Future XR Extension Plan

## Vision

Extend the Eagle Ridge airflow planning system to support immersive XR (Extended Reality) experiences for:
1. **Pre-flight briefing** in VR — spatial walkthrough of predicted airflow zones
2. **In-flight AR** — heads-up display of confidence-weighted thermal cues overlaid on the real world (long-term, experimental)
3. **Post-flight debriefing** — replay tracked flight within the 3D airflow model

---

## Phase 1: Desktop / PCVR Visualisation (current)

- Unity 3D scene with terrain mesh, airflow overlays, agent layer toggles
- Controlled by a keyboard/gamepad or VR controllers
- Data source: `GET /unity/overlays` REST endpoint
- Documented in `unity_3d_design_spec.md`
- C# stubs in `unity/csharp_stubs/`

**Timeline**: Immediate (MVP alongside this codebase)

---

## Phase 2: Standalone VR Briefing (Meta Quest 3)

### Technical Requirements
- Unity 2022.3 LTS, URP, Meta XR SDK
- Dynamic resolution for 72 fps target
- Wi-Fi connection to backend (local network or cloud-hosted)
- Spatial UI: world-space panels, gaze-dwell interaction, controller ray-cast

### XR-Specific Features
- **Teleport locomotion** around the terrain model
- **Grab and reposition** recommendation panels
- **Thermal zone fly-through**: scale the terrain model 1:1 (pilots "fly" through at 1:1 scale)
- **Time scrubbing**: grab a timeline widget and drag forward/backward through the forecast

### Data Considerations
- Reduce polygon count for Quest 3: terrain mesh to 256×256 grid
- Particle density auto-caps at `low` in standalone mode
- Cache overlay JSON locally; refresh every 5 minutes via background coroutine

---

## Phase 3: AR In-Flight HUD (Experimental, Long-Term)

> **Important**: In-flight AR is **not** planned for operational use. This is a research concept only. Any in-flight display system would require extensive safety testing, certification, and would not be based on the advisory-grade data this system produces.

### Concept
- Pilot wears smart glasses (e.g. Meta Ray-Ban, Snap Spectacles 5+, or future OST headset)
- System displays confidence-weighted thermal markers in field of view
- Data from pre-flight planning session only (not real-time wind sensing)

### Research Questions
- Does spatial AR augmentation improve thermal detection rate for student pilots?
- What is the cognitive load impact of AR HUD vs. naked-eye flying?
- How should uncertainty be visualised in a sparse, glanceable HUD?

### Safety Constraints
- No information that distracts from visual scan (wing, sky, other traffic)
- All HUD elements auto-hide when pilot head movement exceeds 30°/s (active manoeuvre)
- Mandatory "advisory only" overlay at all times
- Auto-disable above wind threshold (> 30 km/h) — system suspends when conditions exceed its reliable range

---

## Phase 4: Multi-Pilot Shared XR

- Multiple pilots in the same VR session, each represented by an avatar
- Shared airflow overlay annotated with each pilot's GPS position (live)
- Collaborative annotation: pilots can "tag" areas of the terrain with observations
- Tagged observations feed back into the LocalKnowledgeAgent in real time

### Technical Stack
- Photon Fusion or Mirror Networking for multiplayer state sync
- GPS position streamed from phone companion app (NMEA over WebSocket)
- Annotation events stored as `KnowledgeItem` records in the backend DB

---

## Research Opportunities

| Phase | Research Question | Method |
|-------|------------------|--------|
| 2 | Does VR briefing improve novice pilots' site mental models? | Pre/post quiz, think-aloud protocol |
| 2 | Which airflow visualisation type (particle, ribbon, heatmap) is most legible? | Within-subjects A/B study |
| 3 | Does AR augmentation reduce pre-thermal recognition time? | Eye-tracking + vario analysis |
| 4 | Does collaborative annotation improve knowledge base quality? | Longitudinal data quality audit |

---

## Dependency on Current Codebase

All XR phases depend on the existing `GET /unity/overlays` endpoint and the
`SiteOverlay` C# model. The REST API is intentionally stable across phases.
Breaking changes will be versioned and announced in `CHANGELOG.md`.
