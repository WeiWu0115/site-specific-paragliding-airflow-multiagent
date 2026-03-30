# Research Framing — Multi-Agent Sensemaking for Paragliding Airflow

## Research Question

> How can a multi-agent sensemaking architecture integrate heterogeneous airflow data sources — meteorological forecasts, terrain geometry, local expert knowledge, and historical flight trajectories — into calibrated, interpretable recommendations for site-specific paragliding planning?

## Motivation

Paragliding airflow assessment is a canonical **naturalistic decision-making** task. Experienced pilots integrate:
- Meteorological abstractions (NWP forecasts, skew-T diagrams)
- Direct terrain observation (cloud formation, dust devils, flag trees)
- Tacit site knowledge accumulated over years
- In-flight feedback (vario readings, wing feel)

Existing tools (RASP, XC-Skies, Windguru) provide **raw data** but do not perform **sensemaking** — the process of integrating signals into an actionable situation assessment. This project builds a system that makes sensemaking explicit, auditable, and improvable.

## Theoretical Grounding

### Naturalistic Decision Making (NDM)
Klein's Recognition-Primed Decision (RPD) model suggests experts pattern-match situations to prototypical cases, then mentally simulate action outcomes. This system externalises the pattern library via:
- Site-specific heuristics (LocalKnowledgeAgent)
- Historical flight clustering (FlightHistoryAgent)

### Epistemic Humility in Safety-Critical Systems
The system explicitly models **epistemic uncertainty** via:
- Per-claim confidence scores
- Calibrated probabilities (isotonic regression)
- Conflict detection (RiskAgent)
- Uncertainty summary surfaced in every API response

### Multi-Agent Systems for Sensemaking
Each agent corresponds to a distinct **epistemic community**: weather forecasters, terrain analysts, local experts, data analysts. The NegotiationAgent arbitrates across these communities with explicit reliability weights, avoiding a single point of failure or overconfidence.

## Research Contributions

1. **Typed claim architecture**: Formalises agent outputs as structured `Claim` objects with evidence, confidence, spatial scope, and temporal validity — enabling systematic aggregation and conflict detection.

2. **Site-specific knowledge encoding**: The site profile JSON encodes expert knowledge as parameterised heuristics, making tacit knowledge machine-readable and auditable.

3. **Calibrated uncertainty surface**: Rather than presenting a single "flyable / not flyable" verdict, the system exposes confidence distributions and data gaps to support human decision-making under uncertainty.

4. **Unity 3D integration contract**: Defines a rigorous API contract for 3D spatial visualisation, supporting future XR/VR applications for pilot training and briefing.

## Scope and Limitations

**In scope:**
- Eagle Ridge Flying Site (seed site, Tehachapi Mountains)
- Thermal and ridge lift prediction
- Launch window timing
- Mechanical turbulence (rotor) risk
- Integration with IGC/GPX flight history

**Out of scope:**
- Real-time in-flight navigation assistance
- Cross-country XC route planning
- Multi-site generalisation (deliberate — site-specificity is a design choice)
- Operational certification for flight planning

## Advisory Statement

This system is an **experimental research prototype**. It does not replace:
- A qualified preflight briefing from a certified instructor
- RASP or operational weather forecast services
- On-site wind and cloud observation
- Independent pilot judgment

All system outputs carry an explicit `advisory_disclaimer` field. No recommendation should be acted upon without a full preflight assessment by a qualified pilot.

## Related Work

- RASP (Regional Atmospheric Soaring Prediction) — NWP-based thermal mapping
- XC-Skies — pilot-oriented weather aggregation
- Airsports meteorology research (Lenschow, Stull)
- IGC data analysis for thermal extraction (Bonnin et al.)
- NDM in aviation (Klein, Orasanu)
- Multi-agent systems for environmental monitoring (general literature)
