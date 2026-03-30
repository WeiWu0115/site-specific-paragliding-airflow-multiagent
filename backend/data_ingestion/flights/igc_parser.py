"""
IGC flight log file parser for paraglide-backend.

Parses IGC format files (standard glider flight recorder format) to extract:
- Header records (pilot name, glider type, site, date)
- B records (GPS position fixes with altitude)
- Derived variometer from altitude differences
- Flight segments (climb/glide/sink) via vario thresholding
"""

import re
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any

from loguru import logger


@dataclass
class IGCFix:
    """A single GPS position fix from an IGC B record."""
    time: datetime
    lat: float          # Decimal degrees, positive=North
    lon: float          # Decimal degrees, positive=East
    altitude_gps_m: float
    altitude_baro_m: float
    validity: str       # 'A' = 3D fix, 'V' = 2D/invalid


@dataclass
class FlightSegmentData:
    """A contiguous segment of a flight with a consistent vario trend."""
    segment_type: str   # "climb", "glide", "sink"
    fixes: list[IGCFix] = field(default_factory=list)
    avg_vario_ms: float = 0.0
    duration_s: float = 0.0


@dataclass
class ParsedFlight:
    """Result of parsing an IGC file."""
    fixes: list[IGCFix] = field(default_factory=list)
    segments: list[FlightSegmentData] = field(default_factory=list)
    pilot_name: str | None = None
    glider: str | None = None
    site: str | None = None
    flight_date: date | None = None
    raw_metadata: dict[str, str] = field(default_factory=dict)


class IGCParser:
    """
    Parses IGC format flight recorder files.

    IGC format specification:
    - H records: Header information (date, pilot, glider, etc.)
    - B records: GPS fixes — BHHMMSSDDMMMMMNDDDMMMMMEVPPPPPGGGGG
      - HH:MM:SS = UTC time
      - DDMMmmmN = latitude (degrees, minutes, decimal minutes, N/S)
      - DDDMMmmmE = longitude (degrees, minutes, decimal minutes, E/W)
      - V = fix validity (A=valid, V=not valid)
      - PPPPP = pressure altitude (5 digits, meters)
      - GGGGG = GPS altitude (5 digits, meters)

    Variometer calculation:
    - Smooth altitude over 5-second window
    - Compute dm/dt between consecutive fixes
    - Segment: climb if vario > +0.3 m/s for 3+ seconds
               sink if vario < -0.8 m/s for 3+ seconds
               glide otherwise
    """

    CLIMB_THRESHOLD_MS = 0.3    # m/s above this = climbing
    SINK_THRESHOLD_MS = -0.8    # m/s below this = sinking
    MIN_SEGMENT_FIXES = 3       # Minimum fixes to form a segment

    def parse(self, content: str) -> ParsedFlight:
        """
        Parse an IGC file from string content.

        Args:
            content: Full content of an IGC file as UTF-8 string

        Returns:
            ParsedFlight with fixes, segments, and metadata
        """
        lines = content.splitlines()
        parsed = ParsedFlight()

        for line in lines:
            line = line.strip()
            if not line:
                continue

            if line.startswith("H"):
                self._parse_header_line(line, parsed)
            elif line.startswith("B"):
                fix = self._parse_b_record(line, parsed.flight_date)
                if fix:
                    parsed.fixes.append(fix)

        if not parsed.fixes:
            logger.warning("IGCParser: no valid B records found")
            return parsed

        # Compute smoothed variometer
        vario_ms = self._compute_vario(parsed.fixes)

        # Segment the flight
        parsed.segments = self._segment_flight(parsed.fixes, vario_ms)

        logger.info(
            f"IGC parsed: {len(parsed.fixes)} fixes, {len(parsed.segments)} segments, "
            f"pilot={parsed.pilot_name}, date={parsed.flight_date}"
        )
        return parsed

    def _parse_header_line(self, line: str, parsed: ParsedFlight) -> None:
        """Extract header information from H records."""
        # HFDTE record: date
        if "HFDTE" in line:
            date_match = re.search(r"HFDTE(?:DATE:)?(\d{2})(\d{2})(\d{2})", line)
            if date_match:
                try:
                    day = int(date_match.group(1))
                    month = int(date_match.group(2))
                    year = int(date_match.group(3))
                    year += 2000 if year < 80 else 1900
                    parsed.flight_date = date(year, month, day)
                    parsed.raw_metadata["date"] = line
                except ValueError as e:
                    logger.warning(f"Could not parse IGC date: {e}")

        # Pilot name
        elif "HFPLT" in line or "PILOT" in line.upper():
            parts = line.split(":", 1)
            if len(parts) > 1:
                parsed.pilot_name = parts[1].strip()
                parsed.raw_metadata["pilot"] = parsed.pilot_name

        # Glider type
        elif "HFGTY" in line or "GLIDERTYPE" in line.upper():
            parts = line.split(":", 1)
            if len(parts) > 1:
                parsed.glider = parts[1].strip()
                parsed.raw_metadata["glider"] = parsed.glider

        # Site
        elif "HFGID" in line or "SITE" in line.upper():
            parts = line.split(":", 1)
            if len(parts) > 1:
                parsed.site = parts[1].strip()

    def _parse_b_record(self, line: str, flight_date: date | None) -> IGCFix | None:
        """
        Parse a single IGC B record (position fix).

        B record format: BHHMMSSDDMMMMMNDDDMMMMMEVPPPPPGGGGG
        """
        if len(line) < 35:
            return None

        try:
            # Time: HHMMSS
            hh = int(line[1:3])
            mm = int(line[3:5])
            ss = int(line[5:7])

            # Latitude: DDMMmmmN (degrees, minutes, decimal minutes)
            lat_deg = int(line[7:9])
            lat_min = int(line[9:11])
            lat_dec = int(line[11:14])
            lat = lat_deg + (lat_min + lat_dec / 1000.0) / 60.0
            if line[14] == "S":
                lat = -lat

            # Longitude: DDDMMmmmE
            lon_deg = int(line[15:18])
            lon_min = int(line[18:20])
            lon_dec = int(line[20:23])
            lon = lon_deg + (lon_min + lon_dec / 1000.0) / 60.0
            if line[23] == "W":
                lon = -lon

            # Validity
            validity = line[24]

            # Pressure altitude and GPS altitude
            alt_baro = int(line[25:30])
            alt_gps = int(line[30:35])

            # Build datetime
            if flight_date:
                t = datetime(
                    flight_date.year, flight_date.month, flight_date.day,
                    hh, mm, ss, tzinfo=timezone.utc
                )
            else:
                t = datetime(2000, 1, 1, hh, mm, ss, tzinfo=timezone.utc)

            return IGCFix(
                time=t,
                lat=lat,
                lon=lon,
                altitude_gps_m=float(alt_gps),
                altitude_baro_m=float(alt_baro),
                validity=validity,
            )
        except (ValueError, IndexError) as e:
            logger.debug(f"Skipping malformed B record: {line[:35]!r} ({e})")
            return None

    def _compute_vario(self, fixes: list[IGCFix]) -> list[float]:
        """
        Compute variometer (m/s) from GPS altitude differences.

        Uses a 5-point running average to smooth GPS noise.
        Returns list of vario values (same length as fixes, edges are 0.0).
        """
        n = len(fixes)
        if n < 3:
            return [0.0] * n

        # Raw vario: dh/dt between consecutive fixes
        raw_vario = [0.0]
        for i in range(1, n):
            dt = (fixes[i].time - fixes[i - 1].time).total_seconds()
            dh = fixes[i].altitude_gps_m - fixes[i - 1].altitude_gps_m
            if dt > 0:
                raw_vario.append(dh / dt)
            else:
                raw_vario.append(0.0)

        # Smooth with 5-point window
        smooth_vario = []
        window = 5
        half = window // 2
        for i in range(n):
            start = max(0, i - half)
            end = min(n, i + half + 1)
            window_vals = raw_vario[start:end]
            smooth_vario.append(sum(window_vals) / len(window_vals))

        return smooth_vario

    def _segment_flight(
        self,
        fixes: list[IGCFix],
        vario_ms: list[float],
    ) -> list[FlightSegmentData]:
        """
        Segment the flight into climb/glide/sink phases using vario thresholds.

        Segments shorter than MIN_SEGMENT_FIXES are merged into the adjacent segment.
        """
        if not fixes or not vario_ms:
            return []

        # Classify each fix
        types: list[str] = []
        for v in vario_ms:
            if v > self.CLIMB_THRESHOLD_MS:
                types.append("climb")
            elif v < self.SINK_THRESHOLD_MS:
                types.append("sink")
            else:
                types.append("glide")

        # Build contiguous segments
        segments: list[FlightSegmentData] = []
        current_type = types[0]
        current_fixes = [fixes[0]]
        current_vario = [vario_ms[0]]

        for i in range(1, len(fixes)):
            if types[i] == current_type:
                current_fixes.append(fixes[i])
                current_vario.append(vario_ms[i])
            else:
                seg = FlightSegmentData(
                    segment_type=current_type,
                    fixes=current_fixes,
                    avg_vario_ms=sum(current_vario) / len(current_vario) if current_vario else 0.0,
                )
                if len(current_fixes) >= self.MIN_SEGMENT_FIXES:
                    segments.append(seg)

                current_type = types[i]
                current_fixes = [fixes[i]]
                current_vario = [vario_ms[i]]

        # Final segment
        if len(current_fixes) >= self.MIN_SEGMENT_FIXES:
            segments.append(FlightSegmentData(
                segment_type=current_type,
                fixes=current_fixes,
                avg_vario_ms=sum(current_vario) / len(current_vario) if current_vario else 0.0,
            ))

        climb_count = sum(1 for s in segments if s.segment_type == "climb")
        logger.debug(
            f"Flight segmented: {len(segments)} segments "
            f"({climb_count} climbs, {len(segments) - climb_count} others)"
        )
        return segments
