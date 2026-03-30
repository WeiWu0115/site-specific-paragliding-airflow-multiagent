/**
 * UncertaintyPanel — surfaces epistemic uncertainty and data gaps.
 *
 * Shows which information sources are missing, confidence distribution
 * across claims, and any calibration warnings from the ML layer.
 */

import { UncertaintySummary } from '@/lib/types';

interface GapItemProps {
  label: string;
  severity: 'high' | 'medium' | 'low';
  note: string;
}

function GapItem({ label, severity, note }: GapItemProps) {
  const colors: Record<string, { bg: string; text: string; border: string }> = {
    high:   { bg: '#fef2f2', text: '#991b1b', border: '#fca5a5' },
    medium: { bg: '#fef3c7', text: '#92400e', border: '#fcd34d' },
    low:    { bg: '#f0fdf4', text: '#166534', border: '#86efac' },
  };
  const c = colors[severity];

  return (
    <div
      style={{
        background: c.bg,
        border: `1px solid ${c.border}`,
        borderLeft: `3px solid ${c.border}`,
        borderRadius: '4px',
        padding: '0.5rem 0.75rem',
        marginBottom: '0.4rem',
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span style={{ fontSize: '0.8rem', fontWeight: '600', color: c.text }}>{label}</span>
        <span style={{ fontSize: '0.7rem', color: c.text, textTransform: 'uppercase' }}>{severity}</span>
      </div>
      <p style={{ fontSize: '0.75rem', color: c.text, margin: '2px 0 0 0', opacity: 0.85 }}>{note}</p>
    </div>
  );
}

function ConfidenceHistogram({ distribution }: { distribution: Record<string, number> }) {
  const buckets = ['0–20', '20–40', '40–60', '60–80', '80–100'];
  const keys    = ['0_20', '20_40', '40_60', '60_80', '80_100'];
  const max = Math.max(...keys.map((k) => distribution[k] ?? 0), 1);

  const barColor = (idx: number) => {
    if (idx >= 3) return '#10b981';
    if (idx >= 2) return '#f59e0b';
    return '#ef4444';
  };

  return (
    <div>
      <div style={{ fontSize: '0.75rem', fontWeight: '600', color: '#64748b', marginBottom: '6px' }}>
        CONFIDENCE DISTRIBUTION
      </div>
      <div style={{ display: 'flex', alignItems: 'flex-end', gap: '4px', height: '64px' }}>
        {keys.map((k, i) => {
          const count = distribution[k] ?? 0;
          const heightPct = max > 0 ? (count / max) * 100 : 0;
          return (
            <div key={k} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '2px' }}>
              <span style={{ fontSize: '0.6rem', color: '#64748b' }}>{count}</span>
              <div
                style={{
                  width: '100%',
                  height: `${Math.max(heightPct, 4)}%`,
                  background: barColor(i),
                  borderRadius: '2px 2px 0 0',
                  minHeight: '4px',
                  transition: 'height 0.3s ease',
                }}
              />
            </div>
          );
        })}
      </div>
      <div style={{ display: 'flex', gap: '4px', marginTop: '4px' }}>
        {buckets.map((b) => (
          <div key={b} style={{ flex: 1, textAlign: 'center', fontSize: '0.6rem', color: '#94a3b8' }}>
            {b}%
          </div>
        ))}
      </div>
    </div>
  );
}

interface UncertaintyPanelProps {
  summary: UncertaintySummary | null;
}

export function UncertaintyPanel({ summary }: UncertaintyPanelProps) {
  if (!summary) {
    return (
      <div className="panel">
        <div className="panel-header">Uncertainty & Data Gaps</div>
        <p style={{ color: '#94a3b8', fontSize: '0.875rem' }}>
          No uncertainty data. Run planning to surface epistemic gaps.
        </p>
      </div>
    );
  }

  const gaps = summary.data_gaps ?? [];
  const distribution = summary.confidence_distribution ?? {};
  const calibrationNote = summary.calibration_note;
  const overallUncertainty = summary.overall_uncertainty ?? 0;

  return (
    <div className="panel">
      <div className="panel-header">Uncertainty & Data Gaps</div>

      {/* Overall uncertainty meter */}
      <div style={{ marginBottom: '1rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
          <span style={{ fontSize: '0.8rem', color: '#64748b' }}>Overall Uncertainty</span>
          <span style={{
            fontSize: '0.8rem',
            fontWeight: '600',
            color: overallUncertainty >= 0.5 ? '#ef4444' : overallUncertainty >= 0.3 ? '#f59e0b' : '#10b981',
          }}>
            {Math.round(overallUncertainty * 100)}%
          </span>
        </div>
        <div className="confidence-bar">
          <div
            className="confidence-bar-fill"
            style={{
              width: `${Math.round(overallUncertainty * 100)}%`,
              background: overallUncertainty >= 0.5 ? '#ef4444' : overallUncertainty >= 0.3 ? '#f59e0b' : '#10b981',
            }}
          />
        </div>
        <p style={{ fontSize: '0.7rem', color: '#94a3b8', marginTop: '4px' }}>
          Lower is better. High uncertainty may indicate missing data or conflicting agent signals.
        </p>
      </div>

      {/* Confidence histogram */}
      {Object.keys(distribution).length > 0 && (
        <div style={{ marginBottom: '1rem' }}>
          <ConfidenceHistogram distribution={distribution} />
        </div>
      )}

      {/* Data gaps */}
      {gaps.length > 0 && (
        <div style={{ marginBottom: '0.75rem' }}>
          <div style={{ fontSize: '0.75rem', fontWeight: '600', color: '#64748b', marginBottom: '6px' }}>
            DATA GAPS
          </div>
          {gaps.map((gap, i) => (
            <GapItem key={i} label={gap.label} severity={gap.severity} note={gap.note} />
          ))}
        </div>
      )}

      {/* Calibration note */}
      {calibrationNote && (
        <div className="advisory-banner" style={{ marginTop: '0.5rem' }}>
          <strong>Calibration:</strong> {calibrationNote}
        </div>
      )}
    </div>
  );
}
