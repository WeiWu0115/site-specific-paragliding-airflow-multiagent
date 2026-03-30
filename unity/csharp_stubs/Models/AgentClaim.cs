// AgentClaim.cs
// Per-agent claim model for the agent explanation layer in Unity.
// Enables visualising which agent contributed which recommendation.

using System;
using System.Collections.Generic;

namespace EagleRidge.Airflow.Models
{
    /// <summary>A single piece of evidence backing an agent claim.</summary>
    [Serializable]
    public class EvidenceItem
    {
        /// <summary>Data source identifier, e.g. "open_meteo", "igc_cluster", "expert_heuristic".</summary>
        public string source;

        /// <summary>Human-readable value string or numeric representation.</summary>
        public string value;

        /// <summary>Relative weight this evidence had in the claim's confidence score (0–1).</summary>
        public float weight;

        /// <summary>Optional unit, e.g. "km/h", "m/s", "%".</summary>
        public string unit;
    }

    /// <summary>Confidence level enum mirroring Python ConfidenceLevel.</summary>
    public enum ConfidenceLevel
    {
        Unknown,
        Low,
        Medium,
        High
    }

    /// <summary>
    /// Claim type enum mirroring Python ClaimType.
    /// Used to drive per-type visualisation logic in Unity.
    /// </summary>
    public enum ClaimType
    {
        Unknown,
        ThermalZone,
        RidgeLift,
        SinkZone,
        Caution,
        LaunchWindow,
        RotorRisk
    }

    /// <summary>
    /// An individual agent claim with full evidence chain.
    /// Used by the AgentExplanationPanel visualisation and Unity agent layer display.
    /// </summary>
    [Serializable]
    public class AgentClaim
    {
        public string id;

        /// <summary>Agent identifier, e.g. "weather", "terrain", "risk".</summary>
        public string agent_id;

        public string agent_name;
        public string claim_type_str;   // raw string from API
        public string claim_text;

        /// <summary>Post-arbitration confidence 0.0–1.0.</summary>
        public float confidence;

        public string confidence_level_str; // "high" | "medium" | "low"

        public List<EvidenceItem> evidence;

        /// <summary>Free-text reasoning chain from the agent.</summary>
        public string reasoning;

        public List<string> assumptions;

        /// <summary>Terrain feature this claim references, or null.</summary>
        public string feature_name;

        /// <summary>ISO-8601 timestamp of when the claim was generated.</summary>
        public string created_at;

        // UTC hours for which this claim is temporally valid
        public int valid_from_hour;
        public int valid_to_hour;

        /// <summary>Parsed ClaimType enum from claim_type_str.</summary>
        public ClaimType ClaimTypeEnum
        {
            get
            {
                return claim_type_str switch
                {
                    "THERMAL_ZONE"  => ClaimType.ThermalZone,
                    "RIDGE_LIFT"    => ClaimType.RidgeLift,
                    "SINK_ZONE"     => ClaimType.SinkZone,
                    "CAUTION"       => ClaimType.Caution,
                    "LAUNCH_WINDOW" => ClaimType.LaunchWindow,
                    "ROTOR_RISK"    => ClaimType.RotorRisk,
                    _               => ClaimType.Unknown
                };
            }
        }

        /// <summary>Parsed ConfidenceLevel enum from confidence_level_str.</summary>
        public ConfidenceLevel ConfidenceLevelEnum
        {
            get
            {
                return confidence_level_str switch
                {
                    "high"   => ConfidenceLevel.High,
                    "medium" => ConfidenceLevel.Medium,
                    "low"    => ConfidenceLevel.Low,
                    _        => ConfidenceLevel.Unknown
                };
            }
        }

        public bool IsActiveAt(int utcHour)
        {
            if (valid_from_hour == 0 && valid_to_hour == 0) return true; // no temporal constraint
            return utcHour >= valid_from_hour && utcHour < valid_to_hour;
        }
    }

    /// <summary>
    /// Agent disagreement record — a conflict flagged by the RiskAgent
    /// between two agents' assessments of the same feature.
    /// </summary>
    [Serializable]
    public class AgentDisagreement
    {
        public string region;
        public string agent_a;
        public string agent_b;
        public string claim_type_a;
        public string claim_type_b;
        public string description;
    }
}
