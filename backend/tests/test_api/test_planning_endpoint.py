"""
Integration tests for the planning endpoint in paraglide-backend.

Uses mock weather/cloud providers and does not require a real DB connection.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.mark.asyncio
async def test_planning_endpoint_returns_200(async_client):
    """POST /planning should return 200 with valid request body."""
    payload = {
        "site_id": "eagle_ridge",
        "target_date": "2024-07-15",
    }
    # Mock the planning service to avoid DB dependency
    mock_result = MagicMock()
    mock_result.session_id = 1
    mock_result.ranked_launch_windows = []
    mock_result.ranked_trigger_zones = []
    mock_result.ranked_ridge_corridors = []
    mock_result.caution_zones = []
    mock_result.evidence_traces = {}
    mock_result.uncertainty_summary = "Test uncertainty summary — advisory only."
    mock_result.agent_disagreements = []

    with patch("services.planning_service.PlanningService.run_planning_session", new_callable=AsyncMock) as mock_plan:
        mock_plan.return_value = mock_result
        response = await async_client.post("/planning", json=payload)

    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"


@pytest.mark.asyncio
async def test_planning_result_has_recommendations(async_client):
    """Planning result should contain recommendation keys."""
    payload = {"site_id": "eagle_ridge", "target_date": "2024-07-15"}

    mock_result = MagicMock()
    mock_result.session_id = 1
    mock_result.ranked_launch_windows = [MagicMock(
        rank=1,
        title="Launch Window #1",
        description="Good thermal window 10:00-14:00",
        confidence=0.72,
        uncertainty_note="Rule-based estimate",
        evidence_summary=["Weather forecast shows thermal index 0.62"],
        valid_from_hour=10,
        valid_to_hour=14,
    )]
    mock_result.ranked_trigger_zones = []
    mock_result.ranked_ridge_corridors = []
    mock_result.caution_zones = []
    mock_result.evidence_traces = {}
    mock_result.uncertainty_summary = "Advisory summary."
    mock_result.agent_disagreements = []

    with patch("services.planning_service.PlanningService.run_planning_session", new_callable=AsyncMock) as mock_plan:
        mock_plan.return_value = mock_result
        response = await async_client.post("/planning", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert "launch_windows" in data
    assert "trigger_zones" in data
    assert "caution_zones" in data
    assert len(data["launch_windows"]) >= 1


@pytest.mark.asyncio
async def test_planning_result_has_confidence_scores(async_client):
    """All recommendations should have numeric confidence scores in [0, 1]."""
    payload = {"site_id": "eagle_ridge", "target_date": "2024-07-15"}

    mock_window = MagicMock()
    mock_window.rank = 1
    mock_window.title = "Launch Window #1"
    mock_window.description = "Test window"
    mock_window.confidence = 0.65
    mock_window.uncertainty_note = ""
    mock_window.evidence_summary = []
    mock_window.valid_from_hour = 10
    mock_window.valid_to_hour = 14

    mock_result = MagicMock()
    mock_result.session_id = 1
    mock_result.ranked_launch_windows = [mock_window]
    mock_result.ranked_trigger_zones = []
    mock_result.ranked_ridge_corridors = []
    mock_result.caution_zones = []
    mock_result.evidence_traces = {}
    mock_result.uncertainty_summary = "Advisory."
    mock_result.agent_disagreements = []

    with patch("services.planning_service.PlanningService.run_planning_session", new_callable=AsyncMock) as mock_plan:
        mock_plan.return_value = mock_result
        response = await async_client.post("/planning", json=payload)

    data = response.json()
    for window in data.get("launch_windows", []):
        conf = window.get("confidence")
        if conf is not None:
            assert 0.0 <= conf <= 1.0, f"Confidence {conf} out of range"


@pytest.mark.asyncio
async def test_planning_result_has_evidence_summaries(async_client):
    """Planning response should include evidence_traces dict."""
    payload = {"site_id": "eagle_ridge", "target_date": "2024-07-15"}

    mock_result = MagicMock()
    mock_result.session_id = 1
    mock_result.ranked_launch_windows = []
    mock_result.ranked_trigger_zones = []
    mock_result.ranked_ridge_corridors = []
    mock_result.caution_zones = []
    mock_result.evidence_traces = {"launch_window_1": ["Weather forecast shows thermal index 0.62"]}
    mock_result.uncertainty_summary = "Advisory."
    mock_result.agent_disagreements = []

    with patch("services.planning_service.PlanningService.run_planning_session", new_callable=AsyncMock) as mock_plan:
        mock_plan.return_value = mock_result
        response = await async_client.post("/planning", json=payload)

    data = response.json()
    assert "evidence_traces" in data
    assert isinstance(data["evidence_traces"], dict)


@pytest.mark.asyncio
async def test_planning_result_has_advisory_disclaimer(async_client):
    """Planning response must include the advisory disclaimer."""
    payload = {"site_id": "eagle_ridge", "target_date": "2024-07-15"}

    mock_result = MagicMock()
    mock_result.session_id = 1
    mock_result.ranked_launch_windows = []
    mock_result.ranked_trigger_zones = []
    mock_result.ranked_ridge_corridors = []
    mock_result.caution_zones = []
    mock_result.evidence_traces = {}
    mock_result.uncertainty_summary = "Advisory."
    mock_result.agent_disagreements = []

    with patch("services.planning_service.PlanningService.run_planning_session", new_callable=AsyncMock) as mock_plan:
        mock_plan.return_value = mock_result
        response = await async_client.post("/planning", json=payload)

    data = response.json()
    assert "advisory_disclaimer" in data
    assert len(data["advisory_disclaimer"]) > 20
    assert "advisory" in data["advisory_disclaimer"].lower()
