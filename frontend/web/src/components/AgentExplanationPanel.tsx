/**
 * AgentExplanationPanel — shows per-agent reasoning chains for a selected claim.
 *
 * Renders the chain of evidence each agent used to arrive at its claim,
 * enabling pilots and researchers to inspect the sensemaking process.
 */

import { AgentClaim } from '@/lib/types';

const AGENT_META: Record<string, { label: string; color: string; icon: string }> = {
  weather:         { label: 'Weather Agent',         color: '#2563eb', icon: 'W' },
  terrain:         { label: 'Terrain Agent',         color: '#10b981', icon: 'T' },
  cloud:           { label: 'Cloud Agent',           color: '#6366f1', icon: 'C' },
  local_knowledge: { label: 'Local Knowledge Agent', color: '#f59e0b', icon: 'L' },
  flight_history:  { label: 'Flight History Agent',  color: '#f97316', icon: 'F' },
  risk:            { label: 'Risk Agent',            color: '#ef4444', icon: 'R' },
};

const CLAIM_TYPE_LABELS: Record<string, string> = {
  THERMAL_ZONE:  'Thermal Zone',
  RIDGE_LIFT:    'Ridge Lift',
  SINK_ZONE:     'Sink Zone',
  CAUTION:       'Caution',
  LAUNCH_WINDOW: 'Launch Window',
  ROTOR_RISK:    'Rotor Risk',
};

interface EvidenceCardProps {
  source: string;
  value: string | number;
  weight: number;
  unit?: string;
}

function EvidenceCard({ source, value, weight, unit }: EvidenceCardProps) {
  const weightPct = Math.round(weight * 100);
  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: '1fr auto',
        gap: '4px',
        padding: '6px 8px',
        background: '#f8fafc',
        borderRadius: '4px',
        border: '1px solid #e2e8f0',
        marginBottom: '4px',
      }}
    >
      <div>
        <span style={{ fontSize: '0.75rem', fontWeight: '500', color: '#475569' }}>{source}</span>
        <div style={{ fontSize: '0.8rem', color: '#1e293b', fontWeight: '600' }}>
          {typeof value === 'number' ? value.toFixed(2) : value}
          {unit && <span style={{ fontWeight: '400', color: '#64748b' }}> {unit}</span>}
        </div>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end' }}>
        <span style={{ fontSize: '0.65rem', color: '#94a3b8' }}>weight</span>
        <span style={{ fontSize: '0.8rem', fontWeight: '600', color: '#64748b' }}>{weightPct}%</span>
      </div>
    </div>
  );
}

interface ClaimCardProps {
  claim: AgentClaim;
  isExpanded: boolean;
  onToggle: () => void;
}

function ClaimCard({ claim, isExpanded, onToggle }: ClaimCardProps) {
  const meta = AGENT_META[claim.agent_id] ?? { label: claim.agent_id, color: '#64748b', icon: '?' };
  const confidencePct = Math.round(claim.confidence * 100);
  const confColor = claim.confidence >= 0.70 ? '#10b981' : claim.confidence >= 0.45 ? '#f59e0b' : '#ef4444';
  const claimLabel = CLAIM_TYPE_LABELS[claim.claim_type] ?? claim.claim_type;

  return (
    <div
      style={{
        border: '1px solid #e2e8f0',
        borderRadius: '6px',
        overflow: 'hidden',
        marginBottom: '0.5rem',
      }}
    >
      {/* Header row */}
      <div
        onClick={onToggle}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '10px',
          padding: '0.625rem 0.75rem',
          cursor: 'pointer',
          background: '#f8fafc',
          userSelect: 'none',
        }}
      >
        <div
          style={{
            width: '28px',
            height: '28px',
            borderRadius: '50%',
            background: meta.color,
            color: 'white',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: '0.75rem',
            fontWeight: '700',
            flexShrink: 0,
          }}
        >
          {meta.icon}
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontWeight: '600', fontSize: '0.8rem', color: '#1e293b' }}>
            {meta.label}
          </div>
          <div style={{ fontSize: '0.75rem', color: '#64748b' }}>
            {claimLabel}
            {claim.feature_name && ` · ${claim.feature_name}`}
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <span style={{ fontSize: '0.8rem', fontWeight: '700', color: confColor }}>
            {confidencePct}%
          </span>
          <span style={{ color: '#94a3b8', fontSize: '0.75rem' }}>
            {isExpanded ? '▲' : '▼'}
          </span>
        </div>
      </div>

      {/* Expanded reasoning */}
      {isExpanded && (
        <div style={{ padding: '0.75rem', borderTop: '1px solid #e2e8f0', background: 'white' }}>
          {/* Reasoning text */}
          {claim.reasoning && (
            <p style={{ fontSize: '0.8rem', color: '#475569', marginBottom: '8px', lineHeight: '1.5' }}>
              {claim.reasoning}
            </p>
          )}

          {/* Evidence list */}
          {claim.evidence && claim.evidence.length > 0 && (
            <div>
              <div style={{ fontSize: '0.7rem', fontWeight: '600', color: '#94a3b8', textTransform: 'uppercase', marginBottom: '4px' }}>
                Evidence
              </div>
              {claim.evidence.map((ev, i) => (
                <EvidenceCard
                  key={i}
                  source={ev.source}
                  value={ev.value}
                  weight={ev.weight}
                  unit={ev.unit}
                />
              ))}
            </div>
          )}

          {/* Temporal validity */}
          {claim.valid_from && claim.valid_until && (
            <div style={{ marginTop: '6px', fontSize: '0.7rem', color: '#94a3b8' }}>
              Valid: {claim.valid_from} – {claim.valid_until}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

interface AgentExplanationPanelProps {
  claims: AgentClaim[];
  expandedId?: string | null;
  onExpandToggle?: (id: string) => void;
}

export function AgentExplanationPanel({ claims, expandedId, onExpandToggle }: AgentExplanationPanelProps) {
  if (!claims || claims.length === 0) {
    return (
      <div className="panel">
        <div className="panel-header">Agent Reasoning</div>
        <p style={{ color: '#94a3b8', fontSize: '0.875rem' }}>
          No agent claims to display. Run planning to see reasoning chains.
        </p>
      </div>
    );
  }

  // Group by agent for ordering: risk → weather → terrain → cloud → local_knowledge → flight_history
  const agentOrder = ['risk', 'weather', 'terrain', 'cloud', 'local_knowledge', 'flight_history'];
  const sorted = [...claims].sort((a, b) => {
    const ai = agentOrder.indexOf(a.agent_id);
    const bi = agentOrder.indexOf(b.agent_id);
    return (ai === -1 ? 99 : ai) - (bi === -1 ? 99 : bi);
  });

  return (
    <div className="panel">
      <div className="panel-header">Agent Reasoning Chains</div>
      <p style={{ fontSize: '0.75rem', color: '#94a3b8', marginBottom: '0.75rem' }}>
        Click any claim to expand its evidence chain. Confidence shown reflects post-arbitration weight.
      </p>
      <div>
        {sorted.map((claim) => {
          const id = `${claim.agent_id}-${claim.claim_type}-${claim.feature_name ?? ''}`;
          return (
            <ClaimCard
              key={id}
              claim={claim}
              isExpanded={expandedId === id}
              onToggle={() => onExpandToggle && onExpandToggle(id)}
            />
          );
        })}
      </div>
    </div>
  );
}
