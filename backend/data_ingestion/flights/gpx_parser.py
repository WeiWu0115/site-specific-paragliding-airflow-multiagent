"""
GPX flight track parser for paraglide-backend.

Parses GPX 1.0 and GPX 1.1 files to extract track points and then applies
the same segmentation logic as the IGC parser to identify climb/glide/sink phases.

GPX trkpt elements: lat, lon, ele, time (time optional but needed for vario).
"""

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any

from loguru import logger

# Import the same data types as IGC parser so they share the same interface
from data_ingestion.flights.igc_parser import (
    FlightSegmentData,
    IGCFix,
    IGCParser,
    ParsedFlight,
)

# GPX namespace URIs
GPX_NS_10 = ""  # GPX 1.0 has no namespace
GPX_NS_11 = "http://www.topografix.com/GPX/1/1"


class GPXParser:
    """
    Parses GPX track files into the same ParsedFlight format as IGCParser.

    Handles GPX 1.0 (no namespace) and GPX 1.1 (full namespace).
    Extracts:
    - trkpt lat/lon/ele/time elements
    - metadata/name for pilot/site hints
    - Applies identical segmentation logic to IGC parser
    """

    CLIMB_THRESHOLD_MS = 0.3
    SINK_THRESHOLD_MS = -0.8
    MIN_SEGMENT_FIXES = 3

    def parse(self, content: str) -> ParsedFlight:
        """
        Parse a GPX file from string content.

        Args:
            content: Full content of a GPX file as UTF-8 string

        Returns:
            ParsedFlight in the same format as IGCParser.parse()
        """
        try:
            root = ET.fromstring(content)
        except ET.ParseError as e:
            logger.error(f"GPX parse error: {e}")
            return ParsedFlight()

        # Detect namespace
        ns = ""
        if root.tag.startswith("{"):
            ns = root.tag.split("}")[0][1:]
            logger.debug(f"GPX namespace detected: {ns}")

        ns_prefix = f"{{{ns}}}" if ns else ""

        parsed = ParsedFlight()
        parsed.raw_metadata["format"] = "gpx"

        # Extract metadata
        metadata = root.find(f"{ns_prefix}metadata")
        if metadata is not None:
            name_elem = metadata.find(f"{ns_prefix}name")
            if name_elem is not None and name_elem.text:
                parsed.site = name_elem.text.strip()

        # Look for creator attribute as pilot hint
        creator = root.get("creator", "")
        if creator:
            parsed.raw_metadata["creator"] = creator

        # Extract all track points from all tracks and segments
        fixes: list[IGCFix] = []

        for trk in root.findall(f"{ns_prefix}trk"):
            trk_name_elem = trk.find(f"{ns_prefix}name")
            if trk_name_elem is not None and trk_name_elem.text:
                if not parsed.pilot_name:
                    parsed.pilot_name = trk_name_elem.text.strip()

            for trkseg in trk.findall(f"{ns_prefix}trkseg"):
                for trkpt in trkseg.findall(f"{ns_prefix}trkpt"):
                    fix = self._parse_trkpt(trkpt, ns_prefix)
                    if fix:
                        fixes.append(fix)

        if not fixes:
            logger.warning("GPXParser: no valid track points found")
            return parsed

        # Set flight date from first fix
        if fixes[0].time:
            parsed.flight_date = fixes[0].time.date()

        parsed.fixes = fixes

        # Reuse IGC segmentation logic
        igc_logic = IGCParser()
        vario_ms = igc_logic._compute_vario(fixes)
        parsed.segments = igc_logic._segment_flight(fixes, vario_ms)

        logger.info(
            f"GPX parsed: {len(parsed.fixes)} fixes, {len(parsed.segments)} segments, "
            f"pilot={parsed.pilot_name}, date={parsed.flight_date}"
        )
        return parsed

    def _parse_trkpt(self, trkpt: ET.Element, ns_prefix: str) -> IGCFix | None:
        """Extract a single track point from a trkpt element."""
        try:
            lat_str = trkpt.get("lat")
            lon_str = trkpt.get("lon")
            if lat_str is None or lon_str is None:
                return None

            lat = float(lat_str)
            lon = float(lon_str)

            # Elevation
            ele_elem = trkpt.find(f"{ns_prefix}ele")
            elevation_m = float(ele_elem.text.strip()) if ele_elem is not None and ele_elem.text else 0.0

            # Time
            time_elem = trkpt.find(f"{ns_prefix}time")
            fix_time = datetime(2000, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
            if time_elem is not None and time_elem.text:
                time_str = time_elem.text.strip()
                # Handle ISO 8601 with Z or +00:00
                time_str = time_str.replace("Z", "+00:00")
                try:
                    fix_time = datetime.fromisoformat(time_str)
                    if fix_time.tzinfo is None:
                        fix_time = fix_time.replace(tzinfo=timezone.utc)
                except ValueError:
                    # Try without timezone
                    try:
                        fix_time = datetime.fromisoformat(time_str.split("+")[0]).replace(
                            tzinfo=timezone.utc
                        )
                    except ValueError:
                        pass

            return IGCFix(
                time=fix_time,
                lat=lat,
                lon=lon,
                altitude_gps_m=elevation_m,
                altitude_baro_m=elevation_m,  # GPX doesn't have pressure altitude
                validity="A",
            )

        except (ValueError, AttributeError) as e:
            logger.debug(f"Skipping malformed trkpt: {e}")
            return None
