"""
TerrainAgent for paraglide-backend.

Analyzes site terrain features (ridges, bowls, valleys, riverbeds) against
current wind conditions to produce thermal_zone, ridge_lift, sink_zone,
and rotor_risk Claims.

Uses simple vector math: dot product for ridge alignment with wind,
cross product for determining lee-side. Falls back to site profile
features when no DEM data is available.
"""

import math
from typing import Any

from loguru import logger

from agents.base import AgentBase, Claim, ClaimType, Evidence, SpatialScope, TemporalValidity


def _deg_to_rad(deg: float) -> float:
    return deg * math.pi / 180.0


def _wind_unit_vector(wind_dir_deg: float) -> tuple[float, float]:
    """Return unit vector in the direction the wind is blowing FROM."""
    r = _deg_to_rad(wind_dir_deg)
    return (math.sin(r), math.cos(r))


def _feature_normal_vector(orientation_deg: float) -> tuple[float, float]:
    """Return unit vector perpendicular to a ridge (the face direction)."""
    r = _deg_to_rad(orientation_deg)
    return (math.sin(r), math.cos(r))


class TerrainAgent(AgentBase):
    """
    Reasons about terrain features given current wind direction and speed.

    Expected context keys:
        site_profile: full site profile dict with terrain_features list
        wind_dir_deg: current wind direction in degrees (from compass)
        wind_speed_kmh: current wind speed in km/h
        dem_analysis: optional TerrainAnalysis dataclass from dem_loader

    For each terrain feature, calls assess_feature() which uses vector math
    to determine alignment with wind direction and whether an area is in
    the lee or windward position.
    """

    name = "terrain_agent"
    reliability_weight: float = 0.80

    # Ridge alignment within this many degrees of wind = lift
    RIDGE_ALIGNMENT_THRESHOLD_DEG = 35.0
    # Minimum wind speed to generate ridge lift
    RIDGE_LIFT_MIN_WIND_KMH = 10.0
    # Wind speed above which lee-side rotor becomes significant
    ROTOR_WIND_THRESHOLD_KMH = 15.0

    async def run(self, context: dict[str, Any]) -> list[Claim]:
        """
        Produce terrain-based claims for all features in the site profile.

        Returns Claims for thermal zones, ridge lift, sink zones, and rotor risk.
        """
        site_profile = context.get("site_profile", {})
        features = site_profile.get("terrain_features", [])

        # Get wind conditions from context or use defaults
        wind_dir_deg: float = float(context.get("wind_dir_deg", 225.0))  # Default SW
        wind_speed_kmh: float = float(context.get("wind_speed_kmh", 15.0))

        if not features:
            logger.warning("TerrainAgent: no terrain features in site profile")
            return []

        logger.info(
            f"TerrainAgent analyzing {len(features)} features "
            f"for wind {wind_dir_deg:.0f}° at {wind_speed_kmh:.0f} km/h"
        )

        claims: list[Claim] = []
        for feature in features:
            feature_claims = self.assess_feature(feature, wind_dir_deg, wind_speed_kmh)
            claims.extend(feature_claims)

        logger.info(f"TerrainAgent produced {len(claims)} claims")
        return claims

    def assess_feature(
        self,
        feature: dict[str, Any],
        wind_dir_deg: float,
        wind_speed_kmh: float,
    ) -> list[Claim]:
        """
        Assess a single terrain feature and return applicable claims.

        Uses dot product to measure ridge alignment with wind.
        Uses cross product sign to determine windward vs lee side.
        """
        feature_type = feature.get("type", "")
        name = feature.get("name", "unknown")
        attrs = feature.get("attributes", {})
        description = feature.get("description", "")
        claims: list[Claim] = []

        if feature_type == "ridge":
            claims.extend(self._assess_ridge(feature, wind_dir_deg, wind_speed_kmh))

        elif feature_type == "bowl":
            claims.extend(self._assess_bowl(feature, wind_dir_deg, wind_speed_kmh))

        elif feature_type == "riverbed":
            claims.extend(self._assess_riverbed(feature, wind_dir_deg, wind_speed_kmh))

        elif feature_type == "valley":
            claims.extend(self._assess_valley(feature, wind_dir_deg, wind_speed_kmh))

        elif feature_type in ("rotor_zone", "sink_zone"):
            claims.extend(self._assess_hazard_zone(feature, wind_dir_deg, wind_speed_kmh))

        return claims

    def _assess_ridge(
        self,
        feature: dict,
        wind_dir_deg: float,
        wind_speed_kmh: float,
    ) -> list[Claim]:
        """Determine if wind produces ridge lift or lee-side sink on this ridge."""
        claims = []
        name = feature.get("name", "ridge")
        attrs = feature.get("attributes", {})
        orientation_deg = attrs.get("orientation_deg", 0.0)
        aspect_deg = attrs.get("aspect_deg", orientation_deg)
        elevation_m = attrs.get("crest_elevation_m", attrs.get("elevation_m", 1000.0))
        wind_range = attrs.get("wind_range_for_lift_kmh", [10, 28])

        # Dot product: alignment between ridge normal (face direction) and wind vector
        # If the wind is blowing into the ridge face, dot product is positive → lift
        face_vec = _feature_normal_vector(aspect_deg)
        wind_vec = _wind_unit_vector(wind_dir_deg)

        # Dot product: how much wind is blowing into the face
        dot = face_vec[0] * wind_vec[0] + face_vec[1] * wind_vec[1]
        # Cross product z-component: positive = wind from left, negative = wind from right
        cross = face_vec[0] * wind_vec[1] - face_vec[1] * wind_vec[0]

        # Angular difference between wind direction and ridge orientation
        angle_diff = abs(((wind_dir_deg - aspect_deg + 180) % 360) - 180)

        geom = feature.get("geometry")
        spatial = SpatialScope(
            feature_name=name,
            geojson=geom,
            elevation_range_m=(elevation_m - 100, elevation_m + 50) if elevation_m else None,
        )

        if dot > 0.5 and wind_speed_kmh >= self.RIDGE_LIFT_MIN_WIND_KMH:
            # Wind blowing into face → ridge lift
            wind_in_range = wind_range[0] <= wind_speed_kmh <= wind_range[1]
            confidence = 0.85 if wind_in_range else 0.55
            if wind_speed_kmh > wind_range[1]:
                confidence = 0.45  # Overspeed — rotor risk overrides lift

            claims.append(
                self._make_claim(
                    claim_type=ClaimType.RIDGE_LIFT,
                    claim_text=(
                        f"{name}: ridge lift expected. Wind {wind_dir_deg:.0f}° at {wind_speed_kmh:.0f} km/h "
                        f"is aligned {angle_diff:.0f}° off ridge face ({aspect_deg:.0f}°). "
                        f"Dot product alignment: {dot:.2f}."
                    ),
                    confidence=confidence,
                    evidence=[
                        Evidence(
                            source="terrain_agent_vector_analysis",
                            description=f"Wind-to-ridge face dot product {dot:.2f} (>0.5 = lift expected)",
                            data_ref={
                                "wind_dir_deg": wind_dir_deg,
                                "wind_speed_kmh": wind_speed_kmh,
                                "ridge_aspect_deg": aspect_deg,
                                "dot_product": round(dot, 3),
                                "angle_diff_deg": round(angle_diff, 1),
                            },
                        )
                    ],
                    assumptions=[
                        "Ridge orientation from site profile (not measured)",
                        "No local deflection from upstream terrain modeled",
                    ],
                    spatial_scope=spatial,
                    temporal_validity=TemporalValidity(notes="Active while wind conditions hold"),
                )
            )

        elif dot < -0.3 and wind_speed_kmh > self.ROTOR_WIND_THRESHOLD_KMH:
            # Wind blowing away from face → lee side
            confidence = min(0.85, 0.55 + (wind_speed_kmh - self.ROTOR_WIND_THRESHOLD_KMH) * 0.02)

            # Sink zone on lee side
            claims.append(
                self._make_claim(
                    claim_type=ClaimType.SINK_ZONE,
                    claim_text=(
                        f"{name} LEE SIDE: wind {wind_dir_deg:.0f}° puts the leeward face of "
                        f"{name} into sink/rotor shadow. Dot product {dot:.2f} (< -0.3). "
                        f"Wind {wind_speed_kmh:.0f} km/h — rotor risk {'HIGH' if wind_speed_kmh > 20 else 'MODERATE'}."
                    ),
                    confidence=confidence,
                    evidence=[
                        Evidence(
                            source="terrain_agent_vector_analysis",
                            description=f"Wind-to-ridge dot product {dot:.2f} indicates lee-side position",
                            data_ref={
                                "wind_dir_deg": wind_dir_deg,
                                "wind_speed_kmh": wind_speed_kmh,
                                "ridge_aspect_deg": aspect_deg,
                                "dot_product": round(dot, 3),
                            },
                        )
                    ],
                    spatial_scope=spatial,
                )
            )

        return claims

    def _assess_bowl(
        self,
        feature: dict,
        wind_dir_deg: float,
        wind_speed_kmh: float,
    ) -> list[Claim]:
        """Bowls facing sun are thermal zones; bowls in lee are rotor zones."""
        claims = []
        name = feature.get("name", "bowl")
        attrs = feature.get("attributes", {})
        aspect_deg = attrs.get("aspect_deg", 180.0)  # Default south-facing
        geom = feature.get("geometry")
        bottom_elev = attrs.get("bowl_bottom_elevation_m", 1000.0)

        spatial = SpatialScope(
            feature_name=name,
            geojson=geom,
            elevation_range_m=(bottom_elev, bottom_elev + 250) if bottom_elev else None,
        )

        # South-facing bowl: good thermal if not in rotor shadow
        is_south_facing = 135 <= aspect_deg <= 225
        face_vec = _feature_normal_vector(aspect_deg)
        wind_vec = _wind_unit_vector(wind_dir_deg)
        dot = face_vec[0] * wind_vec[0] + face_vec[1] * wind_vec[1]

        if is_south_facing and dot > -0.2 and wind_speed_kmh <= 20:
            # South-facing bowl not in rotor shadow = thermal zone
            trigger_time = attrs.get("thermal_trigger_time_local", "10:00-12:00")
            claims.append(
                self._make_claim(
                    claim_type=ClaimType.THERMAL_ZONE,
                    claim_text=(
                        f"{name}: south-facing ({aspect_deg:.0f}°) bowl with good solar exposure. "
                        f"Expected thermal trigger {trigger_time} local time. "
                        f"Wind {wind_dir_deg:.0f}° not in direct lee (dot={dot:.2f})."
                    ),
                    confidence=0.72,
                    evidence=[
                        Evidence(
                            source="terrain_agent_aspect_analysis",
                            description=f"South-facing bowl aspect {aspect_deg:.0f}°, not in rotor shadow",
                            data_ref={"aspect_deg": aspect_deg, "dot_product": round(dot, 3)},
                        )
                    ],
                    spatial_scope=spatial,
                    temporal_validity=TemporalValidity(
                        valid_from_hour=10,
                        valid_to_hour=14,
                        notes=f"Based on site profile trigger time: {trigger_time}",
                    ),
                )
            )
        elif dot < -0.4 and wind_speed_kmh > self.ROTOR_WIND_THRESHOLD_KMH:
            # Bowl in lee = rotor trap
            claims.append(
                self._make_claim(
                    claim_type=ClaimType.ROTOR_RISK,
                    claim_text=(
                        f"{name}: bowl is in the lee of the ridge in current wind direction "
                        f"({wind_dir_deg:.0f}°). Rotor turbulence likely at {wind_speed_kmh:.0f} km/h. "
                        f"Avoid flying into or below this bowl."
                    ),
                    confidence=0.78,
                    evidence=[
                        Evidence(
                            source="terrain_agent_vector_analysis",
                            description=f"Bowl in lee shadow (dot={dot:.2f}), wind {wind_speed_kmh:.0f} km/h",
                            data_ref={"dot_product": round(dot, 3), "wind_speed_kmh": wind_speed_kmh},
                        )
                    ],
                    spatial_scope=spatial,
                )
            )

        return claims

    def _assess_riverbed(
        self,
        feature: dict,
        wind_dir_deg: float,
        wind_speed_kmh: float,
    ) -> list[Claim]:
        """Riverbeds are strong thermal triggers on sunny mornings."""
        name = feature.get("name", "riverbed")
        geom = feature.get("geometry")
        attrs = feature.get("attributes", {})
        elev_m = attrs.get("elevation_m", 870.0)
        trigger_time = attrs.get("thermal_trigger_time_local", "09:30-11:00")

        # Riverbeds produce thermals regardless of wind direction (heating trigger)
        # Confidence drops in high wind (thermal gets blown away quickly)
        confidence = 0.80 if wind_speed_kmh < 20 else 0.55

        return [
            self._make_claim(
                claim_type=ClaimType.THERMAL_ZONE,
                claim_text=(
                    f"{name}: riverbed surface heats rapidly in morning sun, "
                    f"triggering organized thermals. Typical trigger window: {trigger_time} local. "
                    f"Thermal drift with wind {wind_dir_deg:.0f}° at {wind_speed_kmh:.0f} km/h."
                ),
                confidence=confidence,
                evidence=[
                    Evidence(
                        source="terrain_agent_surface_analysis",
                        description=f"Light-colored riverbed surface = rapid solar heating trigger",
                        data_ref={"elevation_m": elev_m, "trigger_time": trigger_time},
                    )
                ],
                assumptions=["Surface heating based on site profile description, not DEM"],
                spatial_scope=SpatialScope(
                    feature_name=name,
                    geojson=geom,
                    elevation_range_m=(elev_m, elev_m + 600),
                ),
                temporal_validity=TemporalValidity(
                    valid_from_hour=9,
                    valid_to_hour=13,
                    notes=f"Riverbed trigger typically {trigger_time} local",
                ),
            )
        ]

    def _assess_valley(
        self,
        feature: dict,
        wind_dir_deg: float,
        wind_speed_kmh: float,
    ) -> list[Claim]:
        """Valley floor can produce thermals or venturi acceleration hazards."""
        name = feature.get("name", "valley")
        attrs = feature.get("attributes", {})
        geom = feature.get("geometry")
        hazard = attrs.get("hazard", "")

        claims = []
        if "venturi" in hazard.lower() and wind_speed_kmh > 22:
            claims.append(
                self._make_claim(
                    claim_type=ClaimType.CAUTION,
                    claim_text=(
                        f"{name}: potential venturi acceleration in current wind conditions. "
                        f"Wind {wind_speed_kmh:.0f} km/h may accelerate through valley. {hazard}"
                    ),
                    confidence=0.65,
                    evidence=[
                        Evidence(
                            source="terrain_agent_site_profile",
                            description=f"Site profile hazard note: {hazard}",
                            data_ref={"wind_speed_kmh": wind_speed_kmh},
                        )
                    ],
                    spatial_scope=SpatialScope(feature_name=name, geojson=geom),
                )
            )
        return claims

    def _assess_hazard_zone(
        self,
        feature: dict,
        wind_dir_deg: float,
        wind_speed_kmh: float,
    ) -> list[Claim]:
        """Pre-defined hazard zones from site profile."""
        name = feature.get("name", "hazard")
        attrs = feature.get("attributes", {})
        geom = feature.get("geometry")
        hazard_type = attrs.get("hazard_type", feature.get("type", "sink_zone"))

        wind_trigger_dir = attrs.get("wind_trigger_dir_deg", None)
        wind_trigger_speed = attrs.get("wind_trigger_speed_kmh", 15.0)
        incident_reports = attrs.get("incident_reports", 0)

        # Check if current wind matches the trigger condition for this hazard
        dir_match = True
        if wind_trigger_dir and len(wind_trigger_dir) == 2:
            dir_min, dir_max = wind_trigger_dir
            # Normalize comparison
            if dir_min <= wind_dir_deg <= dir_max:
                dir_match = True
            else:
                dir_match = False

        speed_exceeds = wind_speed_kmh >= wind_trigger_speed

        if dir_match and speed_exceeds:
            confidence = 0.88 + min(0.10, incident_reports * 0.03)  # Higher if incident history
            return [
                self._make_claim(
                    claim_type=ClaimType.CAUTION,
                    claim_text=(
                        f"{name}: active hazard zone. Wind {wind_dir_deg:.0f}° at {wind_speed_kmh:.0f} km/h "
                        f"matches trigger condition for {hazard_type}. "
                        f"{'Incident history: ' + str(incident_reports) + ' reports.' if incident_reports else ''}"
                    ),
                    confidence=min(0.95, confidence),
                    evidence=[
                        Evidence(
                            source="terrain_agent_hazard_profile",
                            description=f"Site-defined hazard zone with trigger conditions met",
                            data_ref={
                                "hazard_type": hazard_type,
                                "wind_trigger": wind_trigger_dir,
                                "incident_reports": incident_reports,
                            },
                        )
                    ],
                    spatial_scope=SpatialScope(feature_name=name, geojson=geom),
                )
            ]

        return []
