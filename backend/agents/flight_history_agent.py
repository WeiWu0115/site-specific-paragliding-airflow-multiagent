"""
FlightHistoryAgent for paraglide-backend.

Analyzes historical flight segments (climbs) from the database to identify
spatial hotspots (where pilots have found lift before) and temporal patterns
(what time of day climbs typically occur).
"""

import math
from collections import defaultdict
from typing import Any

from loguru import logger

from agents.base import AgentBase, Claim, ClaimType, Evidence, SpatialScope, TemporalValidity


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Compute approximate distance in meters between two lat/lon points."""
    R = 6371000.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


class ClimbHotspot:
    """A spatial cluster of climb segments."""
    def __init__(self) -> None:
        self.segments: list[dict] = []
        self.center_lat: float = 0.0
        self.center_lon: float = 0.0
        self.center_elevation_m: float | None = None
        self.avg_vario_ms: float = 0.0
        self.max_vario_ms: float = 0.0
        self.flight_count: int = 0
        self.time_of_day_hours: list[int] = []


class FlightHistoryAgent(AgentBase):
    """
    Identifies thermal zones and ridge lift patterns from historical flight data.

    Expected context keys:
        flight_segments: list of FlightSegment ORM objects or dicts with:
            - segment_type: "climb"
            - avg_vario_ms: float
            - max_altitude_m: float
            - start_time: datetime (for time-of-day analysis)
            - path_geojson: dict with coordinates
        site_profile: site profile dict (for spatial reference)

    Spatial clustering: groups climb segments within CLUSTER_RADIUS_M of each other
    into hotspots. A hotspot is significant if it has >= MIN_FLIGHTS supporting flights.
    """

    name = "flight_history_agent"
    reliability_weight: float = 0.70

    CLUSTER_RADIUS_M = 200.0       # Merge climbs within 200m
    MIN_FLIGHTS_FOR_CLAIM = 2      # Minimum flights to generate a claim
    STRONG_CLIMB_VARIO_MS = 2.0    # Vario > 2 m/s = strong thermal

    async def run(self, context: dict[str, Any]) -> list[Claim]:
        """
        Cluster historical climbs and generate thermal zone claims.
        """
        flight_segments = context.get("flight_segments", [])
        if not flight_segments:
            logger.info("FlightHistoryAgent: no flight segments available")
            return []

        # Filter to climb segments only
        climb_segments = [
            s for s in flight_segments
            if (getattr(s, "segment_type", None) or s.get("segment_type", "")) == "climb"
        ]

        if not climb_segments:
            logger.info("FlightHistoryAgent: no climb segments in history")
            return []

        logger.info(f"FlightHistoryAgent clustering {len(climb_segments)} climb segments")

        # Extract center points from segments
        segment_points = self._extract_segment_centers(climb_segments)
        if not segment_points:
            logger.warning("FlightHistoryAgent: could not extract center points from segments")
            return []

        # Cluster by proximity
        hotspots = self.cluster_climbs(segment_points)

        claims: list[Claim] = []
        for hotspot in hotspots:
            if hotspot.flight_count >= self.MIN_FLIGHTS_FOR_CLAIM:
                claim = self._build_hotspot_claim(hotspot)
                if claim:
                    claims.append(claim)

        logger.info(
            f"FlightHistoryAgent: {len(hotspots)} hotspot clusters, "
            f"{len(claims)} claims produced"
        )
        return claims

    def cluster_climbs(
        self,
        segment_points: list[dict],
    ) -> list[ClimbHotspot]:
        """
        Group climb segments into spatial hotspots using greedy clustering.

        Each unassigned segment attempts to join the nearest existing hotspot
        within CLUSTER_RADIUS_M. If none found, starts a new hotspot.

        Returns list of ClimbHotspot objects sorted by flight_count descending.
        """
        hotspots: list[ClimbHotspot] = []

        for point in segment_points:
            lat = point.get("lat")
            lon = point.get("lon")
            if lat is None or lon is None:
                continue

            # Find nearest hotspot within radius
            best_hotspot: ClimbHotspot | None = None
            best_dist = float("inf")

            for hotspot in hotspots:
                dist = _haversine_m(lat, lon, hotspot.center_lat, hotspot.center_lon)
                if dist < self.CLUSTER_RADIUS_M and dist < best_dist:
                    best_dist = dist
                    best_hotspot = hotspot

            if best_hotspot:
                best_hotspot.segments.append(point)
                # Update centroid
                n = len(best_hotspot.segments)
                all_lats = [s["lat"] for s in best_hotspot.segments if s.get("lat")]
                all_lons = [s["lon"] for s in best_hotspot.segments if s.get("lon")]
                best_hotspot.center_lat = sum(all_lats) / len(all_lats)
                best_hotspot.center_lon = sum(all_lons) / len(all_lons)
                best_hotspot.flight_count = n
            else:
                # New hotspot
                h = ClimbHotspot()
                h.segments = [point]
                h.center_lat = lat
                h.center_lon = lon
                h.flight_count = 1
                hotspots.append(h)

        # Compute statistics for each hotspot
        for hotspot in hotspots:
            vario_values = [s["avg_vario_ms"] for s in hotspot.segments if s.get("avg_vario_ms")]
            if vario_values:
                hotspot.avg_vario_ms = sum(vario_values) / len(vario_values)
                hotspot.max_vario_ms = max(vario_values)
            elevations = [s["max_altitude_m"] for s in hotspot.segments if s.get("max_altitude_m")]
            if elevations:
                hotspot.center_elevation_m = sum(elevations) / len(elevations)
            hours = [s["hour"] for s in hotspot.segments if s.get("hour") is not None]
            hotspot.time_of_day_hours = hours

        hotspots.sort(key=lambda h: h.flight_count, reverse=True)
        return hotspots

    def _extract_segment_centers(
        self,
        segments: list[Any],
    ) -> list[dict]:
        """Extract center lat/lon and metadata from each climb segment."""
        import json
        points = []

        for seg in segments:
            # Handle both ORM objects and dicts
            if hasattr(seg, "__dict__"):
                seg_type = seg.segment_type
                vario = seg.avg_vario_ms
                alt = seg.max_altitude_m
                path_json = seg.path_geojson
                start_time = seg.start_time
            else:
                seg_type = seg.get("segment_type")
                vario = seg.get("avg_vario_ms")
                alt = seg.get("max_altitude_m")
                path_json = seg.get("path_geojson")
                start_time = seg.get("start_time")

            if seg_type != "climb":
                continue

            # Extract center from path GeoJSON
            lat, lon = None, None
            if path_json:
                try:
                    if isinstance(path_json, str):
                        geom = json.loads(path_json)
                    else:
                        geom = path_json
                    coords = geom.get("coordinates", [])
                    if coords:
                        # Use the midpoint of the path
                        mid = coords[len(coords) // 2]
                        lon, lat = mid[0], mid[1]
                except (json.JSONDecodeError, IndexError, KeyError):
                    pass

            hour = None
            if start_time:
                if hasattr(start_time, "hour"):
                    hour = start_time.hour

            if lat is not None and lon is not None:
                points.append({
                    "lat": lat,
                    "lon": lon,
                    "avg_vario_ms": vario or 0.0,
                    "max_altitude_m": alt,
                    "hour": hour,
                })

        return points

    def _build_hotspot_claim(self, hotspot: ClimbHotspot) -> Claim | None:
        """Build a THERMAL_ZONE Claim from a significant climb hotspot."""
        # Confidence scales with flight count and climb quality
        # 2 flights = 0.45, 5 flights = 0.65, 10+ flights = 0.80
        count_factor = min(1.0, hotspot.flight_count / 12.0)
        vario_factor = min(1.0, hotspot.avg_vario_ms / 3.0)
        confidence = 0.40 + 0.35 * count_factor + 0.15 * vario_factor

        # Time of day pattern
        temporal_note = ""
        if hotspot.time_of_day_hours:
            avg_hour = sum(hotspot.time_of_day_hours) / len(hotspot.time_of_day_hours)
            temporal_note = f"Climbs typically occur around {avg_hour:.0f}:00 local"

        # Build approximate polygon (circle around center)
        polygon = _build_circle_geojson(
            hotspot.center_lat,
            hotspot.center_lon,
            radius_m=self.CLUSTER_RADIUS_M,
        )

        evidence = [
            Evidence(
                source="flight_history_cluster",
                description=(
                    f"{hotspot.flight_count} historical flights found lift within "
                    f"{self.CLUSTER_RADIUS_M:.0f}m of ({hotspot.center_lat:.4f}, {hotspot.center_lon:.4f})"
                ),
                data_ref={
                    "flight_count": hotspot.flight_count,
                    "avg_vario_ms": round(hotspot.avg_vario_ms, 2),
                    "max_vario_ms": round(hotspot.max_vario_ms, 2),
                    "center_lat": hotspot.center_lat,
                    "center_lon": hotspot.center_lon,
                    "time_of_day_hours": hotspot.time_of_day_hours,
                },
            )
        ]

        return self._make_claim(
            claim_type=ClaimType.THERMAL_ZONE,
            claim_text=(
                f"Thermal hotspot: {hotspot.flight_count} flights found avg "
                f"{hotspot.avg_vario_ms:.1f} m/s climb "
                f"near ({hotspot.center_lat:.4f}, {hotspot.center_lon:.4f}). "
                f"{temporal_note}"
            ),
            confidence=confidence,
            evidence=evidence,
            assumptions=[
                "Historical climbs may reflect different wind conditions than today",
                "Cluster radius is fixed — actual thermal extent varies",
            ],
            spatial_scope=SpatialScope(
                geojson=polygon,
                elevation_range_m=(
                    (hotspot.center_elevation_m - 400, hotspot.center_elevation_m + 100)
                    if hotspot.center_elevation_m else None
                ),
            ),
            temporal_validity=TemporalValidity(
                notes=temporal_note,
            ),
        )


def _build_circle_geojson(lat: float, lon: float, radius_m: float, n_points: int = 8) -> dict:
    """Build a simple approximate circular polygon GeoJSON around a center point."""
    # Approximate degrees per meter
    lat_deg_per_m = 1.0 / 111000.0
    lon_deg_per_m = 1.0 / (111000.0 * math.cos(math.radians(lat)))

    coords = []
    for i in range(n_points + 1):
        angle = 2 * math.pi * i / n_points
        dlat = radius_m * math.cos(angle) * lat_deg_per_m
        dlon = radius_m * math.sin(angle) * lon_deg_per_m
        coords.append([lon + dlon, lat + dlat])

    return {"type": "Polygon", "coordinates": [coords]}
