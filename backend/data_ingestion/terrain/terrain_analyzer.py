"""
Terrain analyzer for paraglide-backend.

Takes DEMData and site profile to identify ridges, thermal slope candidates,
lee zones, and rotor zones using spatial analysis on the elevation grid.
"""

import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from loguru import logger

from data_ingestion.terrain.dem_loader import DEMData, SlopeAspectData


@dataclass
class IdentifiedZone:
    """A zone identified by terrain analysis."""
    zone_type: str           # "ridge", "thermal_slope", "lee_zone", "rotor_zone"
    name: str
    center_row: int
    center_col: int
    center_lat: float
    center_lon: float
    elevation_m: float
    slope_deg: float | None = None
    aspect_deg: float | None = None
    area_cells: int = 1
    notes: str = ""


@dataclass
class TerrainAnalysis:
    """Result of terrain analysis on a DEM."""
    ridges: list[IdentifiedZone] = field(default_factory=list)
    thermal_slopes: list[IdentifiedZone] = field(default_factory=list)
    lee_zones: list[IdentifiedZone] = field(default_factory=list)
    rotor_zones: list[IdentifiedZone] = field(default_factory=list)
    dem_source: str = ""

    def all_zones(self) -> list[IdentifiedZone]:
        return self.ridges + self.thermal_slopes + self.lee_zones + self.rotor_zones


class TerrainAnalyzer:
    """
    Analyzes DEMData to identify terrain zones relevant to paragliding.

    Combines slope/aspect analysis from the DEM with the wind direction to
    classify zones as thermally active, ridge-lift producing, or hazardous.
    """

    # Thermal slope criteria: slope 15-35 degrees, south-to-west-facing (120-270 degrees)
    THERMAL_SLOPE_MIN_DEG = 12.0
    THERMAL_SLOPE_MAX_DEG = 38.0
    THERMAL_ASPECT_RANGE = (120.0, 270.0)  # South-facing arc

    def __init__(self, dem_data: DEMData, slope_aspect: SlopeAspectData, site_profile: dict[str, Any]) -> None:
        self.dem = dem_data
        self.slope_aspect = slope_aspect
        self.site_profile = site_profile

    def _grid_to_latlon(self, row: int, col: int) -> tuple[float, float]:
        """Convert grid row/col to approximate lat/lon."""
        # Origin is top-left (max lat, min lon)
        lat = self.dem.origin_lat - row * (self.dem.resolution_m / 111000.0)
        lon = self.dem.origin_lon + col * (self.dem.resolution_m / 111000.0)
        return lat, lon

    def identify_ridges(self) -> list[IdentifiedZone]:
        """
        Find ridge lines: local maxima in elevation where cells are
        higher than their neighbors in the cross-ridge direction.

        Returns a list of IdentifiedZone for identified ridge cells.
        """
        grid = self.dem.elevation_grid
        ridges = []

        # Simple approach: cells where elevation > mean of N-S neighbors by more than 20m
        for row in range(1, self.dem.n_rows - 1):
            for col in range(1, self.dem.n_cols - 1):
                elev = grid[row, col]
                north = grid[row - 1, col]
                south = grid[row + 1, col]
                east = grid[row, col + 1]
                west = grid[row, col - 1]

                # Ridge: higher than both N and S neighbors by > 20m
                ns_crest = elev > north + 20 and elev > south + 20
                # Or higher than both E and W neighbors
                ew_crest = elev > east + 20 and elev > west + 20

                if ns_crest or ew_crest:
                    lat, lon = self._grid_to_latlon(row, col)
                    ridges.append(IdentifiedZone(
                        zone_type="ridge",
                        name=f"Ridge_{row}_{col}",
                        center_row=row,
                        center_col=col,
                        center_lat=lat,
                        center_lon=lon,
                        elevation_m=float(elev),
                        slope_deg=float(self.slope_aspect.slope_deg[row, col]),
                        aspect_deg=float(self.slope_aspect.aspect_deg[row, col]),
                    ))

        logger.debug(f"Identified {len(ridges)} ridge cells")
        return ridges

    def identify_thermal_slopes(self) -> list[IdentifiedZone]:
        """
        Find cells with slope 12-38 degrees and south/SE/SW aspect (120-270°).

        These are the most likely thermal generation zones on clear sunny days.
        """
        slope = self.slope_aspect.slope_deg
        aspect = self.slope_aspect.aspect_deg
        grid = self.dem.elevation_grid
        thermal_slopes = []

        s_min, s_max = self.THERMAL_SLOPE_MIN_DEG, self.THERMAL_SLOPE_MAX_DEG
        a_min, a_max = self.THERMAL_ASPECT_RANGE

        for row in range(self.dem.n_rows):
            for col in range(self.dem.n_cols):
                s = float(slope[row, col])
                a = float(aspect[row, col])

                if s_min <= s <= s_max and a_min <= a <= a_max:
                    lat, lon = self._grid_to_latlon(row, col)
                    thermal_slopes.append(IdentifiedZone(
                        zone_type="thermal_slope",
                        name=f"ThermalSlope_{row}_{col}",
                        center_row=row,
                        center_col=col,
                        center_lat=lat,
                        center_lon=lon,
                        elevation_m=float(grid[row, col]),
                        slope_deg=s,
                        aspect_deg=a,
                        notes=f"Slope {s:.0f}°, aspect {a:.0f}°",
                    ))

        logger.debug(f"Identified {len(thermal_slopes)} thermal slope cells")
        return thermal_slopes

    def identify_lee_zones(self, wind_dir_deg: float) -> list[IdentifiedZone]:
        """
        Find cells on the leeward side of ridges for a given wind direction.

        The lee side is where the wind is deflected downward after crossing a ridge.
        Wind blowing from direction wind_dir_deg creates lee on the opposite side.

        Returns:
            List of IdentifiedZone marked as lee zones
        """
        grid = self.dem.elevation_grid
        aspect = self.slope_aspect.aspect_deg
        lee_zones = []

        # Lee aspect: approximately opposite to wind direction
        lee_aspect_center = (wind_dir_deg + 180) % 360

        for row in range(self.dem.n_rows):
            for col in range(self.dem.n_cols):
                a = float(aspect[row, col])

                # Angular difference from lee aspect
                diff = abs(((a - lee_aspect_center + 180) % 360) - 180)

                if diff < 45 and float(self.slope_aspect.slope_deg[row, col]) > 15:
                    lat, lon = self._grid_to_latlon(row, col)
                    lee_zones.append(IdentifiedZone(
                        zone_type="lee_zone",
                        name=f"Lee_{row}_{col}",
                        center_row=row,
                        center_col=col,
                        center_lat=lat,
                        center_lon=lon,
                        elevation_m=float(grid[row, col]),
                        slope_deg=float(self.slope_aspect.slope_deg[row, col]),
                        aspect_deg=a,
                        notes=f"Lee of wind {wind_dir_deg:.0f}°, aspect {a:.0f}°",
                    ))

        logger.debug(f"Identified {len(lee_zones)} lee zone cells for wind {wind_dir_deg:.0f}°")
        return lee_zones

    def identify_rotor_zones(self, wind_dir_deg: float) -> list[IdentifiedZone]:
        """
        Identify concave areas in the lee of ridges where rotor is likely.

        Rotor zones are bowl-shaped depressions on the leeward side of ridges.
        We identify them as areas that are both in the lee aspect AND below
        nearby ridge cells.
        """
        grid = self.dem.elevation_grid
        lee_zones = self.identify_lee_zones(wind_dir_deg)
        rotor_zones = []

        # For each lee zone cell, check if it's concave (below local mean of neighbors)
        lee_set = {(z.center_row, z.center_col) for z in lee_zones}

        for zone in lee_zones:
            row, col = zone.center_row, zone.center_col
            elev = grid[row, col]

            # Check if this cell is lower than average of its 8 neighbors
            neighbors = []
            for dr in [-1, 0, 1]:
                for dc in [-1, 0, 1]:
                    if dr == 0 and dc == 0:
                        continue
                    nr, nc = row + dr, col + dc
                    if 0 <= nr < self.dem.n_rows and 0 <= nc < self.dem.n_cols:
                        neighbors.append(float(grid[nr, nc]))

            if neighbors:
                neighbor_mean = sum(neighbors) / len(neighbors)
                # Concave: cell is lower than its mean neighbors by at least 15m
                if elev < neighbor_mean - 15:
                    rotor_zones.append(IdentifiedZone(
                        zone_type="rotor_zone",
                        name=f"Rotor_{row}_{col}",
                        center_row=row,
                        center_col=col,
                        center_lat=zone.center_lat,
                        center_lon=zone.center_lon,
                        elevation_m=float(elev),
                        slope_deg=zone.slope_deg,
                        aspect_deg=zone.aspect_deg,
                        notes=f"Concave lee zone: {elev:.0f}m vs neighbor mean {neighbor_mean:.0f}m",
                    ))

        logger.debug(f"Identified {len(rotor_zones)} rotor zone cells")
        return rotor_zones

    def analyze(self, wind_dir_deg: float = 225.0) -> TerrainAnalysis:
        """
        Run the full terrain analysis and return a TerrainAnalysis object.
        """
        logger.info(f"Running full terrain analysis for wind {wind_dir_deg:.0f}°")
        return TerrainAnalysis(
            ridges=self.identify_ridges(),
            thermal_slopes=self.identify_thermal_slopes(),
            lee_zones=self.identify_lee_zones(wind_dir_deg),
            rotor_zones=self.identify_rotor_zones(wind_dir_deg),
            dem_source=self.dem.source,
        )
