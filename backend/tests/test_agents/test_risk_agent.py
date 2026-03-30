"""
Tests for RiskAgent in paraglide-backend.
"""

import pytest
from agents.base import Claim, ClaimType, Evidence, SpatialScope
from agents.risk_agent import RiskAgent


@pytest.fixture
def agent() -> RiskAgent:
    return RiskAgent()


@pytest.fixture
def conflicting_claims():
    """Two claims from different agents about the same region with conflicting types."""
    return [
        Claim(
            agent_name="terrain_agent",
            claim_type=ClaimType.RIDGE_LIFT,
            claim_text="Eagle Ridge Main: ridge lift expected",
            confidence=0.80,
            evidence=[Evidence(source="terrain_agent", description="Lift expected")],
            spatial_scope=SpatialScope(feature_name="Eagle Ridge Main"),
        ),
        Claim(
            agent_name="local_knowledge_agent",
            claim_type=ClaimType.SINK_ZONE,
            claim_text="Eagle Ridge Main: often sinks on SE wind",
            confidence=0.70,
            evidence=[Evidence(source="local_knowledge", description="Known sink area")],
            spatial_scope=SpatialScope(feature_name="Eagle Ridge Main"),
        ),
    ]


@pytest.fixture
def consistent_claims():
    """Multiple claims that agree (thermal zone in same area)."""
    return [
        Claim(
            agent_name="weather_agent",
            claim_type=ClaimType.THERMAL_ZONE,
            claim_text="Thermal development expected at noon",
            confidence=0.75,
            spatial_scope=SpatialScope(feature_name="South Bowl"),
        ),
        Claim(
            agent_name="terrain_agent",
            claim_type=ClaimType.THERMAL_ZONE,
            claim_text="South Bowl: south-facing bowl thermal trigger",
            confidence=0.72,
            spatial_scope=SpatialScope(feature_name="South Bowl"),
        ),
        Claim(
            agent_name="local_knowledge_agent",
            claim_type=ClaimType.THERMAL_ZONE,
            claim_text="South Bowl fires around 10:00-11:30",
            confidence=0.80,
            spatial_scope=SpatialScope(feature_name="South Bowl"),
        ),
    ]


@pytest.mark.asyncio
async def test_risk_agent_detects_conflicting_claims(agent, conflicting_claims):
    """RiskAgent should detect and report the conflict between RIDGE_LIFT and SINK_ZONE."""
    context = {"prior_claims": conflicting_claims, "site_profile": {}, "wind_speed_kmh": 15.0}
    risk_claims = await agent.run(context)
    conflict_claims = [
        c for c in risk_claims
        if "DISAGREEMENT" in c.claim_text or "disagrees" in c.claim_text.lower()
    ]
    assert len(conflict_claims) >= 1, "Expected conflict detection claim"


def test_detect_conflicts_returns_claims(agent, conflicting_claims):
    """detect_conflicts() should return caution claims for conflicting agent pairs."""
    conflict_claims = agent.detect_conflicts(conflicting_claims)
    assert len(conflict_claims) >= 1
    for c in conflict_claims:
        assert c.claim_type == ClaimType.CAUTION


@pytest.mark.asyncio
async def test_risk_agent_flags_low_confidence_region(agent):
    """Regions with only low-confidence claims from a single agent should be flagged."""
    low_conf_claims = [
        Claim(
            agent_name="terrain_agent",
            claim_type=ClaimType.THERMAL_ZONE,
            claim_text="Possible thermal here",
            confidence=0.25,  # Below trust threshold
            spatial_scope=SpatialScope(feature_name="Mystery Zone"),
        )
    ]
    context = {"prior_claims": low_conf_claims, "site_profile": {}, "wind_speed_kmh": 12.0}
    risk_claims = await agent.run(context)
    low_conf_flags = [c for c in risk_claims if "LOW CONFIDENCE" in c.claim_text.upper()]
    assert len(low_conf_flags) >= 1, "Expected low-confidence zone flag"


@pytest.mark.asyncio
async def test_risk_agent_escalates_high_wind_caution(agent, consistent_claims):
    """When wind exceeds 25 km/h, RiskAgent should produce a high-wind caution."""
    context = {
        "prior_claims": consistent_claims,
        "site_profile": {},
        "wind_speed_kmh": 30.0,  # Above HIGH_WIND_THRESHOLD
    }
    risk_claims = await agent.run(context)
    wind_cautions = [c for c in risk_claims if "HIGH WIND" in c.claim_text.upper()]
    assert len(wind_cautions) >= 1, "Expected high wind escalation caution"
    assert wind_cautions[0].confidence >= 0.85


@pytest.mark.asyncio
async def test_risk_agent_no_false_positives_on_consistent_claims(agent, consistent_claims):
    """Consistent claims about the same zone should not produce conflict cautions."""
    context = {
        "prior_claims": consistent_claims,
        "site_profile": {},
        "wind_speed_kmh": 12.0,
    }
    risk_claims = await agent.run(context)
    conflict_claims = [
        c for c in risk_claims
        if "DISAGREEMENT" in c.claim_text
    ]
    assert len(conflict_claims) == 0, "Should not flag consistent claims as conflicts"
