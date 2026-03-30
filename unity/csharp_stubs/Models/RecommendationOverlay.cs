// RecommendationOverlay.cs
// Models for the ranked recommendations produced by the NegotiationAgent
// and surfaced in the Unity planning overlay.

using System;
using System.Collections.Generic;
using UnityEngine;

namespace EagleRidge.Airflow.Models
{
    /// <summary>Recommendation type enum mirroring backend ClaimType.</summary>
    public enum RecommendationType
    {
        Unknown,
        LaunchWindow,
        ThermalZone,
        RidgeLift,
        Caution,
        RotorRisk
    }

    /// <summary>
    /// A ranked recommendation from the multi-agent negotiation layer.
    /// Rank 1 is the highest-priority action for the pilot.
    /// </summary>
    [Serializable]
    public class RecommendationOverlay
    {
        /// <summary>1-based rank. Rank 1 = highest priority.</summary>
        public int rank;

        /// <summary>Raw type string from API, e.g. "LAUNCH_WINDOW".</summary>
        public string type;

        public string title;
        public string description;

        /// <summary>Post-arbitration confidence 0.0–1.0.</summary>
        public float confidence;

        /// <summary>Non-null when calibrator or risk agent flagged reduced confidence.</summary>
        public string uncertainty_note;

        /// <summary>Up to 3 bullet-point evidence strings.</summary>
        public List<string> evidence_summary;

        /// <summary>Parsed recommendation type.</summary>
        public RecommendationType RecommendationTypeEnum
        {
            get
            {
                return type switch
                {
                    "LAUNCH_WINDOW" => RecommendationType.LaunchWindow,
                    "THERMAL_ZONE"  => RecommendationType.ThermalZone,
                    "RIDGE_LIFT"    => RecommendationType.RidgeLift,
                    "CAUTION"       => RecommendationType.Caution,
                    "ROTOR_RISK"    => RecommendationType.RotorRisk,
                    _               => RecommendationType.Unknown
                };
            }
        }

        /// <summary>
        /// Returns a Unity Color appropriate for rendering this recommendation's
        /// priority indicator in 3D space.
        /// </summary>
        public Color PriorityColor()
        {
            return RecommendationTypeEnum switch
            {
                RecommendationType.RotorRisk    => new Color(0.863f, 0.078f, 0.235f, 0.9f),
                RecommendationType.Caution      => new Color(0.961f, 0.620f, 0.043f, 0.8f),
                RecommendationType.ThermalZone  => new Color(0.976f, 0.451f, 0.086f, 0.7f),
                RecommendationType.RidgeLift    => new Color(0.063f, 0.725f, 0.506f, 0.7f),
                RecommendationType.LaunchWindow => new Color(0.145f, 0.380f, 0.922f, 0.8f),
                _                               => new Color(0.6f, 0.6f, 0.6f, 0.6f),
            };
        }

        /// <summary>
        /// Returns true if this recommendation has high confidence and should be
        /// rendered with priority visual emphasis (e.g. glowing outline).
        /// </summary>
        public bool IsHighPriority => confidence >= 0.70f && rank <= 2;
    }

    /// <summary>
    /// Launch window recommendation with temporal bounds.
    /// Extends the generic recommendation with hour-level timing.
    /// </summary>
    [Serializable]
    public class LaunchWindowRecommendation : RecommendationOverlay
    {
        /// <summary>Start UTC hour (inclusive).</summary>
        public int hour_start;

        /// <summary>End UTC hour (exclusive).</summary>
        public int hour_end;

        public float wind_speed_kmh;
        public float thermal_index;

        /// <summary>Duration of the launch window in hours.</summary>
        public int DurationHours => Math.Max(0, hour_end - hour_start);

        /// <summary>Returns true if a given UTC hour falls within this window.</summary>
        public bool ContainsHour(int utcHour) => utcHour >= hour_start && utcHour < hour_end;

        /// <summary>
        /// Qualitative label for UI display.
        /// </summary>
        public string QualityLabel()
        {
            if (confidence >= 0.75f) return "Excellent";
            if (confidence >= 0.60f) return "Good";
            if (confidence >= 0.45f) return "Marginal";
            return "Poor";
        }
    }
}
