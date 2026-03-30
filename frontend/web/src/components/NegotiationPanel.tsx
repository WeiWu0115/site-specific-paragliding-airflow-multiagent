/**
 * NegotiationPanel — shows multi-agent negotiation result summary.
 *
 * Displays per-agent claim counts, reliability weights, and conflict summary
 * from the NegotiationAgent arbitration step.
 */

import { NegotiationSummary } from '@/lib/types';

const AGENT_COLORS: Record<string, string> = {
  weather: '#2563eb',
  terrain: '#10b981',
  cloud: '#6366f1',
  local_knowledge: '#f59e0b',
  flight_history: '#f97316',
  risk: '#ef4444',
};

const AGENT_WEIGHTS: Record<string, number> = {
  weather: 0.85,
  terrain: 0.80,
  cloud: 0.65,
  local_knowledge: 0.75,
  flight_history: 0.70,
  risk: 0.90,
};

interface AgentRowProps {
  agent: string;
  claimCount: number;
  accepted: number;
  rejected: number;
}

function AgentRow({ agent, claimCount, accepted, rejected }: AgentRowProps) {
  const color = AGENT_COLORS[agent] ?? '#94a3b8';
  const weight = AGENT_WEIGHTS[agent] ?? 0.70;
  const label = agent.replace('_', ' ').replace(/\b\w/g, (c) => c.toUpperCase());

  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: '1fr auto auto auto auto',
        alignItems: 'center',
        gap: '8px',
        padding: '6px 0',
        borderBottom: '1px solid #f1f5f9',
        fontSize: '0.8rem',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
        <span
          style={{
            width: '8px',
            height: '8px',
            borderRadius: '50%',
            background: color,
            flexShrink: 0,
          }}
        />
        <span style={{ fontWeight: '500', color: '#1e293b' }}>{label}</span>
      </div>
      <span style={{ color: '#64748b', textAlign: 'right' }}>{claimCount} claims</span>
      <span style={{ color: '#10b981', textAlign: 'right' }}>✓ {accepted}</span>
      <span style={{ color: '#ef4444', textAlign: 'right' }}>✗ {rejected}</span>
      <span
        style={{
          color,
          fontWeight: '600',
          textAlign: 'right',
          minWidth: '3rem',
        }}
      >
        {Math.round(weight * 100)}%
      </span>
    </div>
  );
}

interface NegotiationPanelProps {
  summary: NegotiationSummary | null;
}

export function NegotiationPanel({ summary }: NegotiationPanelProps) {
  if (!summary) {
    return (
      <div className="panel">
        <div className="panel-header">Agent Negotiation</div>
        <p style={{ color: '#94a3b8', fontSize: '0.875rem' }}>
          No negotiation data. Run planning to see multi-agent arbitration results.
        </p>
      </div>
    );
  }

  const totalClaims = Object.values(summary.claims_by_agent).reduce((a, b) => a + b, 0);
  const totalConflicts = summary.conflict_count ?? 0;
  const overallConfidence = summary.overall_confidence ?? 0;

  return (
    <div className="panel">
      <div className="panel-header">Multi-Agent Negotiation</div>

      {/* Summary row */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(3, 1fr)',
          gap: '0.75rem',
          marginBottom: '1rem',
        }}
      >
        {[
          { label: 'Total Claims', value: totalClaims, color: '#2563eb' },
          { label: 'Conflicts', value: totalConflicts, color: totalConflicts > 0 ? '#f59e0b' : '#10b981' },
          { label: 'Consensus', value: `${Math.round(overallConfidence * 100)}%`, color: overallConfidence >= 0.65 ? '#10b981' : '#f59e0b' },
        ].map(({ label, value, color }) => (
          <div
            key={label}
            style={{
              textAlign: 'center',
              padding: '0.5rem',
              background: '#f8fafc',
              borderRadius: '6px',
              border: '1px solid #e2e8f0',
            }}
          >
            <div style={{ fontSize: '1.25rem', fontWeight: '700', color }}>{value}</div>
            <div style={{ fontSize: '0.7rem', color: '#94a3b8', marginTop: '2px' }}>{label}</div>
          </div>
        ))}
      </div>

      {/* Per-agent breakdown */}
      <div>
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: '1fr auto auto auto auto',
            gap: '8px',
            padding: '0 0 4px 0',
            fontSize: '0.7rem',
            color: '#94a3b8',
            textTransform: 'uppercase',
            letterSpacing: '0.03em',
          }}
        >
          <span>Agent</span>
          <span style={{ textAlign: 'right' }}>Total</span>
          <span style={{ textAlign: 'right' }}>Accept</span>
          <span style={{ textAlign: 'right' }}>Reject</span>
          <span style={{ textAlign: 'right' }}>Weight</span>
        </div>
        {Object.entries(summary.claims_by_agent).map(([agent, count]) => (
          <AgentRow
            key={agent}
            agent={agent}
            claimCount={count}
            accepted={summary.accepted_by_agent?.[agent] ?? count}
            rejected={summary.rejected_by_agent?.[agent] ?? 0}
          />
        ))}
      </div>

      {/* Conflict notes */}
      {summary.conflict_notes && summary.conflict_notes.length > 0 && (
        <div style={{ marginTop: '0.75rem' }}>
          <div style={{ fontSize: '0.75rem', fontWeight: '600', color: '#64748b', marginBottom: '4px' }}>
            CONFLICT NOTES
          </div>
          {summary.conflict_notes.slice(0, 3).map((note, i) => (
            <div
              key={i}
              className="advisory-banner"
              style={{ marginBottom: '4px', padding: '0.5rem 0.75rem' }}
            >
              {note}
            </div>
          ))}
        </div>
      )}

      <p style={{ fontSize: '0.7rem', color: '#94a3b8', marginTop: '0.5rem' }}>
        Reliability weights: Risk=90%, Weather=85%, Terrain=80%, Local Knowledge=75%,
        Flight History=70%, Cloud=65%.
      </p>
    </div>
  );
}
