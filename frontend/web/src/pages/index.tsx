/**
 * Main planning dashboard page.
 *
 * Orchestrates all panels: SiteOverview, TimeSlider, WeatherPanel,
 * TriggerZonePanel, LaunchTimingPanel, NegotiationPanel,
 * UncertaintyPanel, AgentExplanationPanel.
 *
 * Data is fetched from the backend API on load and on "Run Planning" click.
 */

import { useState, useEffect, useCallback } from 'react';
import Head from 'next/head';
import Link from 'next/link';
import {
  checkHealth,
  getSiteProfile,
  getForecast,
  getClouds,
  runPlanning,
} from '@/lib/api';
import type {
  SiteProfile,
  WeatherForecast,
  CloudObservation,
  NegotiationResult,
  NegotiationSummary,
  UncertaintySummary,
  AgentClaim,
  TriggerZone,
  LaunchWindow,
} from '@/lib/types';

import { SiteOverview } from '@/components/SiteOverview';
import { TimeSlider } from '@/components/TimeSlider';
import { WeatherPanel } from '@/components/WeatherPanel';
import { TriggerZonePanel } from '@/components/TriggerZonePanel';
import { LaunchTimingPanel } from '@/components/LaunchTimingPanel';
import { NegotiationPanel } from '@/components/NegotiationPanel';
import { UncertaintyPanel } from '@/components/UncertaintyPanel';
import { AgentExplanationPanel } from '@/components/AgentExplanationPanel';

// ---------------------------------------------------------------------------
// Helpers to derive panel data from NegotiationResult
// ---------------------------------------------------------------------------

function buildNegotiationSummary(result: NegotiationResult | null): NegotiationSummary | null {
  if (!result) return null;
  // Aggregate claim counts per agent from evidence_traces keys
  const claimsByAgent: Record<string, number> = {};
  for (const key of Object.keys(result.evidence_traces)) {
    const parts = key.split(':');
    const agent = parts[0] ?? 'unknown';
    claimsByAgent[agent] = (claimsByAgent[agent] ?? 0) + 1;
  }

  const conflictNotes = result.agent_disagreements.map(
    (d) => `${d.agent_a} ↔ ${d.agent_b}: ${d.description}`
  );

  return {
    claims_by_agent: claimsByAgent,
    conflict_count: result.agent_disagreements.length,
    overall_confidence:
      result.trigger_zones.length > 0
        ? result.trigger_zones.reduce((s, z) => s + z.confidence, 0) / result.trigger_zones.length
        : 0.5,
    conflict_notes: conflictNotes,
  };
}

function buildUncertaintySummary(result: NegotiationResult | null): UncertaintySummary | null {
  if (!result) return null;

  const allZones: TriggerZone[] = [
    ...result.trigger_zones,
    ...result.ridge_corridors,
  ];

  // Build confidence distribution
  const distribution: Record<string, number> = {
    '0_20': 0, '20_40': 0, '40_60': 0, '60_80': 0, '80_100': 0,
  };
  for (const z of allZones) {
    const pct = z.confidence * 100;
    if (pct < 20)       distribution['0_20']++;
    else if (pct < 40)  distribution['20_40']++;
    else if (pct < 60)  distribution['40_60']++;
    else if (pct < 80)  distribution['60_80']++;
    else                distribution['80_100']++;
  }

  const avgConf = allZones.length > 0
    ? allZones.reduce((s, z) => s + z.confidence, 0) / allZones.length
    : 0.5;

  return {
    overall_uncertainty: 1 - avgConf,
    data_gaps: result.agent_disagreements.slice(0, 3).map((d) => ({
      label: `Conflict: ${d.region}`,
      severity: 'medium' as const,
      note: d.description,
    })),
    confidence_distribution: distribution,
    calibration_note: result.uncertainty_summary || undefined,
  };
}

// ---------------------------------------------------------------------------
// Page component
// ---------------------------------------------------------------------------

type LoadState = 'idle' | 'loading' | 'error';

export default function HomePage() {
  const [siteProfile, setSiteProfile] = useState<SiteProfile | null>(null);
  const [forecast, setForecast] = useState<WeatherForecast | null>(null);
  const [_clouds, setClouds] = useState<CloudObservation | null>(null);
  const [planningResult, setPlanningResult] = useState<NegotiationResult | null>(null);
  const [selectedHour, setSelectedHour] = useState<number>(12);
  const [expandedClaimId, setExpandedClaimId] = useState<string | null>(null);
  const [loadState, setLoadState] = useState<LoadState>('idle');
  const [planState, setPlanState] = useState<LoadState>('idle');
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [siteId, setSiteId] = useState<string>('eagle_ridge');

  // Initial data fetch
  useEffect(() => {
    async function init() {
      setLoadState('loading');
      setErrorMsg(null);
      try {
        const [health, profile, wx, cl] = await Promise.all([
          checkHealth(),
          getSiteProfile(),
          getForecast(),
          getClouds(),
        ]);
        setSiteId(health.site_id);
        setSiteProfile(profile);
        setForecast(wx);
        setClouds(cl);
        setLoadState('idle');
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        setErrorMsg(msg);
        setLoadState('error');
      }
    }
    init();
  }, []);

  const handleRunPlanning = useCallback(async () => {
    setPlanState('loading');
    setErrorMsg(null);
    try {
      const result = await runPlanning({
        site_id: siteId,
        target_time_utc: `${String(selectedHour).padStart(2, '0')}:00`,
      });
      setPlanningResult(result);
      setPlanState('idle');
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setErrorMsg(msg);
      setPlanState('error');
    }
  }, [siteId, selectedHour]);

  const negSummary = buildNegotiationSummary(planningResult);
  const uncSummary = buildUncertaintySummary(planningResult);

  // Derive typed windows and claims for sub-panels
  const launchWindows: LaunchWindow[] = (planningResult?.launch_windows ?? []).map((w, i) => ({
    ...w,
    score: w.confidence,
    hour_start: w.valid_from_hour ?? 10,
    hour_end: w.valid_to_hour ?? 14,
    notes: w.evidence_summary,
  }));

  // Agent claims are not directly in NegotiationResult; use evidence_traces as proxy
  const agentClaims: AgentClaim[] = Object.entries(planningResult?.evidence_traces ?? {}).map(([key, traces]) => {
    const [agentId, ...rest] = key.split(':');
    return {
      id: key,
      agent_id: agentId ?? 'unknown',
      agent_name: agentId ?? 'Unknown Agent',
      claim_type: rest[0] ?? 'UNKNOWN',
      claim_text: traces.join('; '),
      confidence: 0.65,
      confidence_level: 'medium' as const,
      evidence: traces.map((t, i) => ({ source: `trace_${i}`, value: t, weight: 1 / traces.length })),
      reasoning: traces.join(' | '),
      assumptions: [],
      created_at: new Date().toISOString(),
    };
  });

  return (
    <>
      <Head>
        <title>Eagle Ridge Airflow Planning</title>
        <meta name="description" content="Site-specific multi-agent paragliding airflow planning dashboard" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
      </Head>

      <div style={{ maxWidth: '1400px', margin: '0 auto', padding: '1rem' }}>
        {/* Nav bar */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
          <div style={{ fontSize: '0.875rem', color: '#64748b' }}>
            Eagle Ridge · Multi-Agent Airflow Planning
          </div>
          <div style={{ display: 'flex', gap: '1rem', fontSize: '0.875rem' }}>
            <Link href="/" style={{ color: '#2563eb', fontWeight: '600', textDecoration: 'none' }}>
              Planning
            </Link>
            <Link href="/replay" style={{ color: '#64748b', textDecoration: 'none' }}>
              Replay
            </Link>
          </div>
        </div>

        {/* Error banner */}
        {errorMsg && (
          <div className="advisory-banner" style={{ marginBottom: '1rem', background: '#fef2f2', borderColor: '#fca5a5' }}>
            <strong>Error:</strong> {errorMsg}
          </div>
        )}

        {/* Loading indicator */}
        {loadState === 'loading' && (
          <div style={{ textAlign: 'center', padding: '2rem', color: '#64748b' }}>
            Loading site data…
          </div>
        )}

        {/* Main content */}
        {loadState !== 'loading' && (
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', alignItems: 'start' }}>
            {/* Left column */}
            <div>
              <SiteOverview site={siteProfile} forecast={forecast} selectedHour={selectedHour} />
              <TimeSlider value={selectedHour} onChange={setSelectedHour} />

              {/* Run planning button */}
              <div style={{ marginBottom: '1rem' }}>
                <button
                  onClick={handleRunPlanning}
                  disabled={planState === 'loading'}
                  style={{
                    width: '100%',
                    padding: '0.75rem',
                    background: planState === 'loading' ? '#93c5fd' : '#2563eb',
                    color: 'white',
                    border: 'none',
                    borderRadius: '8px',
                    fontSize: '0.9rem',
                    fontWeight: '700',
                    cursor: planState === 'loading' ? 'not-allowed' : 'pointer',
                    transition: 'background 0.15s',
                  }}
                >
                  {planState === 'loading' ? 'Running agents…' : 'Run Planning'}
                </button>
              </div>

              <WeatherPanel forecast={forecast} selectedHour={selectedHour} />
              <LaunchTimingPanel
                windows={launchWindows}
                selectedHour={selectedHour}
                onHourSelect={setSelectedHour}
              />
            </div>

            {/* Right column */}
            <div>
              <TriggerZonePanel zones={planningResult?.trigger_zones ?? []} />
              <NegotiationPanel summary={negSummary} />
              <UncertaintyPanel summary={uncSummary} />
              <AgentExplanationPanel
                claims={agentClaims}
                expandedId={expandedClaimId}
                onExpandToggle={(id) => setExpandedClaimId(expandedClaimId === id ? null : id)}
              />
            </div>
          </div>
        )}
      </div>
    </>
  );
}
