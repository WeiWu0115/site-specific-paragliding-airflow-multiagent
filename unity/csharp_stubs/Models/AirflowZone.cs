// AirflowZone.cs
// Models for thermal zones, ridge corridors, caution zones, and climb hotspots
// received from the Eagle Ridge airflow planning backend.
//
// Advisory: this data is for research and visualisation only.
// Not for operational flight planning.

using System;
using System.Collections.Generic;
using UnityEngine;

namespace EagleRidge.Airflow.Models
{
    /// <summary>Render hints controlling Unity visual representation of an airflow zone.</summary>
    [Serializable]
    public class RenderHints
    {
        /// <summary>Hex colour string, e.g. "#f97316".</summary>
        public string color;

        /// <summary>Opacity 0.0–1.0.</summary>
        public float opacity;

        /// <summary>"low" | "medium" | "high" — particle system density.</summary>
        public string particle_density;

        /// <summary>"sparse" | "dense" — arrow density for ridge corridors.</summary>
        public string arrow_density;

        /// <summary>When true, render a hazard marker icon.</summary>
        public bool hazard_marker;

        /// <summary>Convert hex colour string to Unity Color.</summary>
        public Color ToUnityColor()
        {
            if (ColorUtility.TryParseHtmlString(color, out Color c))
            {
                c.a = opacity;
                return c;
            }
            return new Color(0.5f, 0.5f, 0.5f, opacity);
        }
    }

    /// <summary>A GeoJSON geometry (Polygon or LineString).</summary>
    [Serializable]
    public class GeoJsonGeometry
    {
        public string type;
        // Coordinates are represented as a raw JSON string; parse with JsonUtility
        // or Newtonsoft.Json as needed for your Unity version.
        public List<List<List<float>>> coordinates; // Polygon: [ring][point][lon,lat]
    }

    /// <summary>
    /// Thermal zone identified by the multi-agent negotiation layer.
    /// Polygon-based, carries confidence and render hints.
    /// </summary>
    [Serializable]
    public class ThermalZone
    {
        public string id;
        public string name;

        /// <summary>Post-arbitration confidence 0.0–1.0.</summary>
        public float confidence;

        /// <summary>1 - confidence.</summary>
        public float uncertainty;

        public int evidence_count;
        public List<string> evidence_sources;
        public GeoJsonGeometry polygon_geojson;
        public float elevation_center_m;
        public List<int> valid_hours;
        public List<string> agent_sources;
        public string notes;
        public RenderHints render_hints;

        /// <summary>True if this zone is active for the given UTC hour.</summary>
        public bool IsActiveAt(int utcHour) => valid_hours != null && valid_hours.Contains(utcHour);
    }

    /// <summary>
    /// Ridge lift corridor identified by the terrain and weather agents.
    /// LineString-based; arrows indicate lift direction along the ridge.
    /// </summary>
    [Serializable]
    public class RidgeCorridor
    {
        public string id;
        public string name;
        public float confidence;
        public float uncertainty;
        public int evidence_count;
        public GeoJsonGeometry line_geojson;
        public float elevation_m;
        public List<int> valid_hours;
        public List<string> agent_sources;
        public string notes;
        public RenderHints render_hints;

        public bool IsActiveAt(int utcHour) => valid_hours != null && valid_hours.Contains(utcHour);
    }

    /// <summary>
    /// Caution or hazard zone. May be a rotor risk, sink zone, or general caution.
    /// </summary>
    [Serializable]
    public class CautionZone
    {
        public string title;
        public string description;
        public float confidence;

        /// <summary>"ROTOR_RISK" | "SINK_ZONE" | "CAUTION".</summary>
        public string caution_type;

        /// <summary>Non-null when two agents produced conflicting assessments.</summary>
        public string conflict_description;

        public string feature_name;
        public RenderHints render_hints;

        public bool IsRotorRisk => caution_type == "ROTOR_RISK";
    }

    /// <summary>
    /// Spatially precise climb hotspot derived from clustered historical GPS tracks.
    /// </summary>
    [Serializable]
    public class ClimbHotspot
    {
        public string id;
        public string name;
        public float lat;
        public float lon;
        public float elevation_m;
        public float avg_climb_ms;
        public float max_climb_ms;
        public int flight_count;
        public float confidence;
        public float radius_m;
        public List<int> valid_hours;
        public string notes;
        public RenderHints render_hints;

        public bool IsActiveAt(int utcHour) => valid_hours != null && valid_hours.Contains(utcHour);
    }
}
