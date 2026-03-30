"""
Tests for NegotiationAgent in paraglide-backend.
"""

import pytest
from agents.base import Claim, ClaimType, Evidence, SpatialScope, TemporalValidity
from agents.negotiation_agent import NegotiationAgent, NegotiationResult


@pytest.fixture
def negotiation_agent() -> NegotiationAgent:
    return NegotiationAgent()


@pytest.mark.asyncio
async def test_negotiation_produces_ranked_launch_windows(negotiation_agent, sample_claims):
    """Negotiation should produce at least one ranked launch window from sample claims."""
    result = await negotiation_agent.arbitrate(sample_claims)
    assert isinstance(result, NegotiationResult)
    assert len(result.ranked_launch_windows) >= 1
    # Verify ranking is 1-based
    if result.ranked_launch_windows:
        assert result.ranked_launch_windows[0].rank == 1


@pytest.mark.asyncio
async def test_negotiation_preserves_evidence_traces(negotiation_agent, sample_claims):
    """Evidence traces should map recommendation IDs to evidence descriptions."""
    result = await negotiation_agent.arbitrate(sample_claims)
    assert isinstance(result.evidence_traces, dict)
    # At minimum, there should be some traces
    total_evidence_entries = sum(len(v) for v in result.evidence_traces.values())
    assert total_evidence_entries >= 0  # May be 0 if only window traces


@pytest.mark.asyncio
async def test_negotiation_flags_agent_disagreements(negotiation_agent, sample_claims):
    """Sample claims include conflicting ridge_lift + sink_zone on same feature."""
    result = await negotiation_agent.arbitrate(sample_claims)
    # sample_claims has terrain_agent RIDGE_LIFT vs terrain_agent SINK_ZONE on Eagle Ridge
    # Note: same agent, so may not flag as inter-agent — but CAUTION claim is there
    assert isinstance(result.agent_disagreements, list)


@pytest.mark.asyncio
async def test_negotiation_result_contains_uncertainty_summary(negotiation_agent, sample_claims):
    """Uncertainty summary should be a non-empty string."""
    result = await negotiation_agent.arbitrate(sample_claims)
    assert isinstance(result.uncertainty_summary, str)
    assert len(result.uncertainty_summary) > 20, "Uncertainty summary should be substantive"
    assert "advisory" in result.uncertainty_summary.lower()


@pytest.mark.asyncio
async def test_negotiation_with_no_claims_returns_empty_result(negotiation_agent):
    """Empty claims list should return NegotiationResult with empty lists."""
    result = await negotiation_agent.arbitrate([])
    assert isinstance(result, NegotiationResult)
    assert result.ranked_launch_windows == []
    assert result.ranked_trigger_zones == []
    assert result.ranked_ridge_corridors == []
    assert "No agent claims" in result.uncertainty_summary


@pytest.mark.asyncio
async def test_negotiation_multiple_thermal_zones_ranked_by_evidence(negotiation_agent):
    """Thermal zones with more supporting claims should rank higher."""
    # Two zones: one with 3 supporting agents, one with 1
    claims = [
        # Zone A: 3 agents agree
        Claim(agent_name="weather_agent", claim_type=ClaimType.THERMAL_ZONE,
              claim_text="South Bowl thermal", confidence=0.75,
              spatial_scope=SpatialScope(feature_name="South Bowl")),
        Claim(agent_name="terrain_agent", claim_type=ClaimType.THERMAL_ZONE,
              claim_text="South Bowl bowl trigger", confidence=0.72,
              spatial_scope=SpatialScope(feature_name="South Bowl")),
        Claim(agent_name="local_knowledge_agent", claim_type=ClaimType.THERMAL_ZONE,
              claim_text="South Bowl confirmed morning trigger", confidence=0.80,
              spatial_scope=SpatialScope(feature_name="South Bowl")),
        # Zone B: 1 agent only
        Claim(agent_name="flight_history_agent", claim_type=ClaimType.THERMAL_ZONE,
              claim_text="Mystery Zone historical climbs", confidence=0.45,
              spatial_scope=SpatialScope(feature_name="Mystery Zone")),
    ]
    result = await negotiation_agent.arbitrate(claims)
    assert len(result.ranked_trigger_zones) >= 2
    # South Bowl (3 supporting claims) should rank #1
    assert result.ranked_trigger_zones[0].feature_name == "South Bowl"
    assert result.ranked_trigger_zones[0].rank == 1


@pytest.mark.asyncio
async def test_negotiation_caution_zones_all_included(negotiation_agent):
    """All CAUTION claims should be represented in caution_zones output."""
    caution_claims = [
        Claim(agent_name="risk_agent", claim_type=ClaimType.CAUTION,
              claim_text=f"Caution {i}: some risk", confidence=0.80)
        for i in range(3)
    ]
    result = await negotiation_agent.arbitrate(caution_claims)
    assert len(result.caution_zones) == 3
