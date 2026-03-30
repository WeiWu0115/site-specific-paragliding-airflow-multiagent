// SiteOverlay.cs
// Root payload returned by GET /unity/overlays or GET /unity/overlays/{session_id}.
// Deserialise the API JSON response into this class.

using System;
using System.Collections.Generic;

namespace EagleRidge.Airflow.Models
{
    /// <summary>Launch point metadata from the site profile.</summary>
    [Serializable]
    public class LaunchPoint
    {
        public string id;
        public string name;
        public float lat;
        public float lon;
        public float elevation_m;
        public string facing_direction;
        public float facing_degrees;
        public float[] optimal_wind_dir_deg;   // [min, max]
        public float[] optimal_wind_speed_kmh; // [min, max]
        public string notes;
    }

    /// <summary>Landing zone metadata from the site profile.</summary>
    [Serializable]
    public class LandingZone
    {
        public string id;
        public string name;
        public float lat;
        public float lon;
        public float elevation_m;
        public string surface;
        public string notes;
    }

    /// <summary>Named terrain feature (ridge, bowl, lee zone, etc.).</summary>
    [Serializable]
    public class TerrainFeature
    {
        public string id;
        public string type;
        public string name;
        public string description;
        public string notes;
    }

    /// <summary>Terrain sub-object within the overlay payload.</summary>
    [Serializable]
    public class TerrainSection
    {
        public List<LaunchPoint> launches;
        public List<LandingZone> landings;
        public List<TerrainFeature> features;

        /// <summary>Optional URL to a hosted terrain mesh asset (.obj / .glb).</summary>
        public string terrain_mesh_url;
    }

    /// <summary>UTC time range for which this overlay is valid.</summary>
    [Serializable]
    public class TimeRange
    {
        public string from;
        public string to;
    }

    /// <summary>Per-agent activity summary for the agent layer visualisation.</summary>
    [Serializable]
    public class AgentClaimSummary
    {
        public string claim_type;
        public string claim_text;
        public float confidence;
    }

    /// <summary>Top-level agent layer data.</summary>
    [Serializable]
    public class AgentLayerData
    {
        public bool active;
        public int claim_count;
        public List<AgentClaimSummary> claims;
    }

    /// <summary>Ranked recommendation from the negotiation agent.</summary>
    [Serializable]
    public class RecommendationItem
    {
        public int rank;
        public string type;
        public string title;
        public string description;
        public float confidence;
        public string uncertainty_note;
        public List<string> evidence_summary;
    }

    /// <summary>
    /// Full site overlay payload returned by the backend.
    /// Deserialise with JsonUtility.FromJson&lt;SiteOverlay&gt;(json) or Newtonsoft.Json.
    /// </summary>
    [Serializable]
    public class SiteOverlay
    {
        public string site_id;
        public int session_id;
        public string generated_at;
        public string coordinate_system;
        public TimeRange time_range;
        public TerrainSection terrain;

        public List<ThermalZone> thermal_zones;
        public List<RidgeCorridor> ridge_corridors;
        public List<CautionZone> caution_zones;
        public List<ClimbHotspot> climb_hotspots;
        public List<RecommendationItem> recommendations;

        // Dictionary not directly serialisable by JsonUtility — use Newtonsoft.Json
        // or build a wrapper list. See AirflowApiClient for parsing notes.
        public string uncertainty_summary;
        public string advisory_disclaimer;

        /// <summary>Filter thermal zones valid at a given UTC hour.</summary>
        public List<ThermalZone> GetThermalZonesAt(int utcHour)
        {
            var result = new List<ThermalZone>();
            if (thermal_zones == null) return result;
            foreach (var z in thermal_zones)
                if (z.IsActiveAt(utcHour)) result.Add(z);
            return result;
        }

        /// <summary>Filter ridge corridors valid at a given UTC hour.</summary>
        public List<RidgeCorridor> GetRidgeCorridorsAt(int utcHour)
        {
            var result = new List<RidgeCorridor>();
            if (ridge_corridors == null) return result;
            foreach (var c in ridge_corridors)
                if (c.IsActiveAt(utcHour)) result.Add(c);
            return result;
        }
    }
}
