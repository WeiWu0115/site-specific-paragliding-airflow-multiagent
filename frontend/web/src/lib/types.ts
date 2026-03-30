/**
 * TypeScript interfaces for paraglide-frontend.
 * Mirrors the backend Pydantic models and agent data structures.
 */

// ---------------------------------------------------------------------------
// Weather
// ---------------------------------------------------------------------------

export interface WeatherHour {
  time: string; // ISO timestamp
  temp_c: number;
  dewpoint_c: number;
  humidity_pct: number;
  wind_speed_kmh: number;
  wind_dir_deg: number;
  pressure_hpa: number;
  cloud_cover_pct: number;
  precipitation_mm: number;
  weather_code: number;
}

export interface WeatherForecast {
  provider: string;
  site_id: string;
  location: { lat: number; lon: number };
  hourly: WeatherHour[];
  fetched_at: string;
}

// ---------------------------------------------------------------------------
// Site / Terrain
// ---------------------------------------------------------------------------

export interface GeoJSONGeometry {
  type: string;
  coordinates: number[][] | number[][][] | number[];
}

export interface TerrainFeature {
  id: string;
  type: string;
  name: string;
  description?: string;
  geometry?: GeoJSONGeometry;
  attributes?: Record<string, unknown>;
  notes?: string;
}

export interface LaunchPoint {
  id: string;
  name: string;
  lat: number;
  lon: number;
  elevation_m: number;
  facing_direction: string;
  facing_degrees: number;
  optimal_wind_dir_deg: [number, number];
  optimal_wind_speed_kmh: [number, number];
  notes?: string;
}

export interface LandingZone {
  id: string;
  name: string;
  lat: number;
  lon: number;
  elevation_m: number;
  surface?: string;
  notes?: string;
}

export interface SiteProfile {
  id: string;
  name: string;
  description: string;
  location: {
    lat: number;
    lon: number;
    elevation_m: number;
    timezone: string;
  };
  launches: LaunchPoint[];
  landings: LandingZone[];
  terrain_features: TerrainFeature[];
  known_heuristics: unknown[];
  risk_notes: string[];
  seasonal_notes: Record<string, string>;
}

// ---------------------------------------------------------------------------
// Cloud
// ---------------------------------------------------------------------------

export interface CloudObservation {
  site_id: string;
  provider: string;
  cover_pct: number;
  cloud_base_m: number | null;
  cloud_type_hint: string | null;
  observed_at: string;
  confidence: number;
  interpretation: string;
}

// ---------------------------------------------------------------------------
// Agents / Claims
// ---------------------------------------------------------------------------

export interface Evidence {
  source: string;
  description: string;
  data_ref?: Record<string, unknown>;
}

export interface SpatialScope {
  feature_name?: string;
  elevation_range_m?: [number, number];
  geojson?: GeoJSONGeometry;
}

export interface TemporalValidity {
  valid_from_hour?: number;
  valid_to_hour?: number;
  seasonal_constraint?: string;
  notes?: string;
}

export interface EvidenceItem {
  source: string;
  value: string | number;
  weight: number;
  unit?: string;
}

export interface AgentClaim {
  id: string;
  agent_id: string;
  agent_name: string;
  claim_type: string;
  claim_text: string;
  confidence: number;
  confidence_level: 'high' | 'medium' | 'low' | 'unknown';
  evidence: EvidenceItem[];
  reasoning?: string;
  assumptions: string[];
  feature_name?: string;
  spatial_scope?: SpatialScope;
  temporal_validity?: TemporalValidity;
  valid_from?: string;
  valid_until?: string;
  created_at: string;
}

// ---------------------------------------------------------------------------
// Recommendations
// ---------------------------------------------------------------------------

export interface LaunchWindow {
  rank: number;
  title: string;
  description: string;
  confidence: number;
  score: number;
  uncertainty_note: string;
  evidence_summary: string[];
  valid_from_hour?: number;
  valid_to_hour?: number;
  hour_start: number;
  hour_end: number;
  notes?: string[];
  wind_speed_kmh?: number;
  thermal_index?: number;
}

export interface TriggerZone {
  rank: number;
  zone_type: string;
  title: string;
  description: string;
  confidence: number;
  uncertainty_note: string;
  evidence_summary: string[];
  feature_name?: string;
}

export interface CautionZone {
  title: string;
  description: string;
  confidence: number;
  caution_type: string;
  conflict_description?: string;
  feature_name?: string;
}

export interface AgentDisagreement {
  region: string;
  agent_a: string;
  agent_b: string;
  claim_type_a: string;
  claim_type_b: string;
  description: string;
}

export interface NegotiationResult {
  session_id: number;
  launch_windows: LaunchWindow[];
  trigger_zones: TriggerZone[];
  ridge_corridors: TriggerZone[];
  caution_zones: CautionZone[];
  evidence_traces: Record<string, string[]>;
  uncertainty_summary: string;
  agent_disagreements: AgentDisagreement[];
  advisory_disclaimer: string;
}

// ---------------------------------------------------------------------------
// Unity Overlay
// ---------------------------------------------------------------------------

export interface RenderHints {
  color: string;
  opacity: number;
  particle_density?: string;
  arrow_density?: string;
  hazard_marker?: boolean;
}

export interface ThermalZone {
  id: string;
  name: string;
  confidence: number;
  uncertainty: number;
  evidence_count: number;
  evidence_sources: string[];
  polygon_geojson?: GeoJSONGeometry;
  elevation_center_m?: number;
  valid_hours: number[];
  agent_sources: string[];
  notes: string;
  render_hints: RenderHints;
}

export interface RidgeCorridor {
  id: string;
  name: string;
  confidence: number;
  uncertainty: number;
  evidence_count: number;
  line_geojson?: GeoJSONGeometry;
  elevation_m?: number;
  valid_hours: number[];
  agent_sources: string[];
  notes: string;
  render_hints: RenderHints;
}

export interface RecommendationOverlay {
  rank: number;
  type: string;
  title: string;
  description: string;
  confidence: number;
  uncertainty_note?: string;
  evidence_summary: string[];
}

export interface AgentLayerData {
  active: boolean;
  claim_count: number;
  claims: Array<{
    claim_type: string;
    claim_text: string;
    confidence: number;
  }>;
}

export interface UnityOverlayPayload {
  site_id: string;
  session_id?: number;
  generated_at: string;
  coordinate_system: string;
  time_range: { from: string; to: string };
  terrain: {
    launches: LaunchPoint[];
    landings: LandingZone[];
    features: TerrainFeature[];
    terrain_mesh_url?: string;
  };
  thermal_zones: ThermalZone[];
  ridge_corridors: RidgeCorridor[];
  caution_zones: CautionZone[];
  climb_hotspots: unknown[];
  recommendations: RecommendationOverlay[];
  agent_layers: Record<string, AgentLayerData>;
  uncertainty_summary: string;
  advisory_disclaimer: string;
}

// ---------------------------------------------------------------------------
// API request/response
// ---------------------------------------------------------------------------

export interface PlanningRequest {
  site_id: string;
  target_date?: string;
  target_time_utc?: string;
}

export type PlanningResponse = NegotiationResult;

// ---------------------------------------------------------------------------
// Negotiation summary (for NegotiationPanel)
// ---------------------------------------------------------------------------

export interface NegotiationSummary {
  claims_by_agent: Record<string, number>;
  accepted_by_agent?: Record<string, number>;
  rejected_by_agent?: Record<string, number>;
  conflict_count?: number;
  overall_confidence?: number;
  conflict_notes?: string[];
}

// ---------------------------------------------------------------------------
// Uncertainty summary (for UncertaintyPanel)
// ---------------------------------------------------------------------------

export interface DataGap {
  label: string;
  severity: 'high' | 'medium' | 'low';
  note: string;
}

export interface UncertaintySummary {
  overall_uncertainty: number;
  data_gaps: DataGap[];
  confidence_distribution: Record<string, number>;
  calibration_note?: string;
}

// ---------------------------------------------------------------------------
// Flight tracks (for HistoricalReplayPanel)
// ---------------------------------------------------------------------------

export interface FlightTrackSummary {
  id: number;
  date: string;
  duration_s: number;
  track_type?: string;
  max_alt_m?: number;
  avg_climb_ms?: number;
  climb_seconds?: number;
  glide_seconds?: number;
  sink_seconds?: number;
}

// ---------------------------------------------------------------------------
// Knowledge
// ---------------------------------------------------------------------------

export interface KnowledgeItemCreate {
  site_id: string;
  sub_region?: string;
  wind_condition?: string;
  time_of_day?: string;
  season?: string;
  statement: string;
  confidence: number;
  source_expert?: string;
}
