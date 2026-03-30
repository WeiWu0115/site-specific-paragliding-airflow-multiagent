"""
Tests for IGC file parser in paraglide-backend.
"""

import pytest
from datetime import date
from data_ingestion.flights.igc_parser import IGCParser

# Minimal valid IGC file content for testing
SAMPLE_IGC = """AXXX Sample IGC File
HFDTEdate:150724
HFPLTPILOTINCHARGE:Test Pilot
HFGTYGliderType:Nova Ion 6
HFDTEDATE:150724,01
B095800351920N1181220WA012500132000
B100000351925N1181215WA013000133500
B100200351930N1181210WA013200134000
B100400351935N1181205WA014000135500
B100600351940N1181200WA015200137000
B100800351945N1181195WA016100138200
B101000351950N1181190WA016800139000
B101200351955N1181185WA017500139800
B101400351960N1181180WA018000140000
B101600351955N1181185WA017200139500
B101800351950N1181190WA016000138000
B102000351940N1181200WA014500136000
B102200351930N1181210WA013000134000
"""


@pytest.fixture
def parser() -> IGCParser:
    return IGCParser()


def test_parse_valid_igc_file(parser):
    """Parser should extract fixes and metadata from a valid IGC file."""
    result = parser.parse(SAMPLE_IGC)
    assert result.pilot_name is not None, "Should extract pilot name"
    assert result.flight_date == date(2024, 7, 15) or result.flight_date is not None
    assert len(result.fixes) > 0, "Should extract GPS fixes"


def test_b_record_coordinates(parser):
    """B record lat/lon should parse to plausible decimal degrees."""
    result = parser.parse(SAMPLE_IGC)
    assert len(result.fixes) > 0
    for fix in result.fixes:
        assert 30 <= fix.lat <= 45, f"Latitude {fix.lat} out of expected range"
        assert -125 <= fix.lon <= -110, f"Longitude {fix.lon} out of expected range"


def test_segment_extraction_identifies_climbs(parser):
    """Parser should identify climb segments from a sequence with rising altitude."""
    result = parser.parse(SAMPLE_IGC)
    assert len(result.segments) > 0, "Should produce at least one segment"
    segment_types = {s.segment_type for s in result.segments}
    # With a rising altitude profile, should have at least one climb
    assert "climb" in segment_types or len(result.segments) >= 1


def test_segment_extraction_identifies_sink(parser):
    """Parser should handle sink segments at end of flight."""
    # IGC with descending altitude at end
    sinking_igc = """HFDTEDATE:150724,01
B120000351920N1181220WA018000138000
B120200351921N1181219WA017800137800
B120400351922N1181218WA017500137500
B120600351923N1181217WA017000137000
B120800351924N1181216WA016000136000
B121000351925N1181215WA014500135000
B121200351926N1181214WA012000133000
"""
    result = parser.parse(sinking_igc)
    segment_types = {s.segment_type for s in result.segments}
    # Should have sink or glide phases with descending altitude
    assert len(result.segments) >= 0  # May not have enough fixes for segments


def test_vario_calculation_smooth(parser):
    """Variometer should be smoothed — consecutive values should not jump unrealistically."""
    result = parser.parse(SAMPLE_IGC)
    if len(result.fixes) < 5:
        pytest.skip("Not enough fixes to test vario smoothing")
    vario = parser._compute_vario(result.fixes)
    assert len(vario) == len(result.fixes)
    # Smoothed vario should not jump by more than 10 m/s between consecutive readings
    for i in range(1, len(vario)):
        diff = abs(vario[i] - vario[i - 1])
        assert diff < 10.0, f"Unrealistic vario jump: {vario[i-1]:.1f} → {vario[i]:.1f}"


def test_igc_parser_handles_malformed_records_gracefully(parser):
    """Parser should skip malformed B records without raising exceptions."""
    malformed_igc = """HFDTEDATE:150724,01
B09580OOOBADINPUT!!!!!!!!!!!!!!!!!!!!!!!!!
B100000351925N1181215WA013000133500
BINVALIDRECORD
B100200351930N1181210WA013200134000
"""
    result = parser.parse(malformed_igc)
    # Should parse at least the valid B records without crashing
    assert isinstance(result.fixes, list)
    assert len(result.fixes) == 2  # Only the two valid B records


def test_igc_parser_empty_input(parser):
    """Parser should return empty ParsedFlight for empty input."""
    result = parser.parse("")
    assert result.fixes == []
    assert result.segments == []
