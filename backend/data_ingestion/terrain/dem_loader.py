"""
DEM (Digital Elevation Model) loader for paraglide-backend.

Loads elevation data from GeoTIFF files when available, or generates
synthetic DEM data from the site profile when no file is provided.
Provides slope and aspect analysis for thermal zone identification.
"""

from dataclasses import dataclass, field
from typing import Any

import numpy as np
from loguru import logger


@dataclass
class DEMData:
    """Holds a raster elevation grid with metadata."""
    elevation_grid: np.ndarray          # 2D array of elevation values in meters
    resolution_m: float                 # Grid cell size in meters
    origin_lat: float                   # Top-left corner latitude
    origin_lon: float                   # Top-left corner longitude
    n_rows: int
    n_cols: int
    coordinate_system: str = "WGS84"
    source: str = "synthetic"
    nodata_value: float = -9999.0


@dataclass
class SlopeAspectData:
    """Slope and aspect grids derived from a DEM."""
    slope_deg: np.ndarray   # Slope angle in degrees (0=flat, 90=vertical)
    aspect_deg: np.ndarray  # Aspect in degrees (0=N, 90=E, 180=S, 270=W)


class DEMLoader:
    """
    Loads or synthesizes a DEM for a site.

    Usage:
        loader = DEMLoader()
        dem = loader.load(site_profile, dem_path="path/to/dem.tif")
        slope_aspect = loader.extract_slope_aspect(dem)
    """

    def load(
        self,
        site_profile: dict[str, Any],
        dem_path: str | None = None,
    ) -> DEMData:
        """
        Load DEM data.

        If dem_path is provided and the file exists, loads from GeoTIFF.
        Otherwise, synthesizes a plausible DEM from site profile data.

        Args:
            site_profile: Site profile dict with location and terrain features
            dem_path: Optional path to a GeoTIFF file

        Returns:
            DEMData with elevation grid
        """
        if dem_path:
            try:
                return self._load_from_file(dem_path)
            except Exception as e:
                logger.warning(f"DEM file load failed ({e}), falling back to synthetic DEM")

        return self._synthesize_from_profile(site_profile)

    def _load_from_file(self, dem_path: str) -> DEMData:
        """Load DEM from GeoTIFF using rasterio."""
        try:
            import rasterio
            from rasterio.transform import xy
        except ImportError:
            raise ImportError("rasterio is required for DEM file loading. Install it with: pip install rasterio")

        with rasterio.open(dem_path) as src:
            elevation_grid = src.read(1).astype(np.float32)
            transform = src.transform
            n_rows, n_cols = elevation_grid.shape
            resolution_m = abs(transform.a) * 111000  # Approximate degrees to meters
            origin_lon = transform.c
            origin_lat = transform.f

        logger.info(f"DEM loaded from {dem_path}: {n_rows}x{n_cols} grid, res={resolution_m:.0f}m")

        return DEMData(
            elevation_grid=elevation_grid,
            resolution_m=resolution_m,
            origin_lat=origin_lat,
            origin_lon=origin_lon,
            n_rows=n_rows,
            n_cols=n_cols,
            source=dem_path,
        )

    def _synthesize_from_profile(self, site_profile: dict[str, Any]) -> DEMData:
        """
        Synthesize a plausible DEM from site profile data.

        Creates a 50x50 grid centered on the site, with elevation derived from
        the site's known features (ridge elevations, valley floors, bowl locations).
        """
        location = site_profile.get("location", {})
        site_lat = location.get("lat", 35.492)
        site_lon = location.get("lon", -118.187)
        site_elev = location.get("elevation_m", 1340.0)

        n_rows, n_cols = 50, 50
        resolution_m = 100.0  # 100m grid cells

        # Create base elevation grid centered on site
        # Use a simple ridge model: elevation increases from south valley to north ridge
        grid = np.zeros((n_rows, n_cols), dtype=np.float32)
        valley_elev = 800.0
        ridge_elev = site_elev

        for row in range(n_rows):
            for col in range(n_cols):
                # Distance from ridge (northern rows are higher)
                ridge_proximity = (n_rows - row) / n_rows  # 1.0 at ridge, 0.0 at south
                base = valley_elev + (ridge_elev - valley_elev) * ridge_proximity

                # Add some spatial variation to create realistic terrain
                # Ridge runs diagonally NE-SW
                ridge_dist = abs((col - n_cols * 0.6) - (row - n_rows * 0.5))
                ridge_factor = np.exp(-0.5 * (ridge_dist / 8.0) ** 2)
                elevation = base + 80.0 * ridge_factor

                # Add bowl depression in south
                bowl_row, bowl_col = int(n_rows * 0.75), int(n_cols * 0.6)
                bowl_dist = np.sqrt((row - bowl_row) ** 2 + (col - bowl_col) ** 2)
                bowl_depth = 150.0 * np.exp(-0.5 * (bowl_dist / 5.0) ** 2)
                elevation -= bowl_depth * 0.5  # Subtle bowl depression

                grid[row, col] = max(valley_elev - 50, elevation)

        logger.info(
            f"Synthesized DEM: {n_rows}x{n_cols} grid, "
            f"elevation range {grid.min():.0f}–{grid.max():.0f}m"
        )

        return DEMData(
            elevation_grid=grid,
            resolution_m=resolution_m,
            origin_lat=site_lat + (n_rows / 2) * (resolution_m / 111000.0),
            origin_lon=site_lon - (n_cols / 2) * (resolution_m / 111000.0),
            n_rows=n_rows,
            n_cols=n_cols,
            source="synthetic_from_profile",
        )

    def extract_slope_aspect(self, dem_data: DEMData) -> SlopeAspectData:
        """
        Compute slope (degrees from horizontal) and aspect (compass degrees from N)
        from the elevation grid using central-difference finite differences.

        Returns:
            SlopeAspectData with slope_deg and aspect_deg grids
        """
        grid = dem_data.elevation_grid.astype(np.float64)
        res = dem_data.resolution_m

        # Gradient using central differences
        dz_dy, dz_dx = np.gradient(grid, res)  # [row, col] = [north-south, east-west]

        # Slope in degrees
        slope_rad = np.arctan(np.sqrt(dz_dx ** 2 + dz_dy ** 2))
        slope_deg = np.degrees(slope_rad)

        # Aspect in degrees (0=North, 90=East, 180=South, 270=West)
        # np.arctan2 returns angle from East going counter-clockwise
        # We need compass bearing: 0=N, 90=E, increasing clockwise
        aspect_rad = np.arctan2(dz_dx, -dz_dy)  # Convert to N=0 convention
        aspect_deg = (np.degrees(aspect_rad) + 360) % 360

        # Flat areas have undefined aspect — assign 0
        aspect_deg[slope_deg < 1.0] = 0.0

        logger.debug(
            f"Slope range: {slope_deg.min():.1f}°–{slope_deg.max():.1f}°, "
            f"mean {slope_deg.mean():.1f}°"
        )

        return SlopeAspectData(
            slope_deg=slope_deg.astype(np.float32),
            aspect_deg=aspect_deg.astype(np.float32),
        )
