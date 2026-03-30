/**
 * TriggerZonePanel — shows ranked thermal trigger zones from recommendations.
 */

import { TriggerZone } from '@/lib/types';

function ConfidenceBar({ confidence }: { confidence: number }) {
  const pct = Math.round(confidence * 100);
  const color = confidence >= 0.70 ? '#10b981' : confidence >= 0.45 ? '#f59e0b' : '#ef4444';
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
      <div className="confidence-bar" style={{ flex: 1 }}>
        <div className="confidence-bar-fill" style={{ width: `${pct}%`, background: color }} />
      </div>
      <span style={{ fontSize: '0.75rem', fontWeight: '600', color, minWidth: '2.5rem' }}>
        {pct}%
      </span>
    </div>
  );
}

interface TriggerZonePanelProps {
  zones: TriggerZone[];
}

export function TriggerZonePanel({ zones }: TriggerZonePanelProps) {
  if (!zones || zones.length === 0) {
    return (
      <div className="panel">
        <div className="panel-header">Trigger Zones</div>
        <p style={{ color: '#94a3b8', fontSize: '0.875rem' }}>
          No trigger zones identified. Run planning to generate recommendations.
        </p>
      </div>
    );
  }

  return (
    <div className="panel">
      <div className="panel-header">Thermal Trigger Zones</div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
        {zones.map((zone) => (
          <div
            key={zone.rank}
            style={{
              padding: '0.75rem',
              background: '#f8fafc',
              borderRadius: '6px',
              border: '1px solid #e2e8f0',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
              <span style={{ fontWeight: '600', fontSize: '0.875rem' }}>
                #{zone.rank} {zone.feature_name || zone.title}
              </span>
              <span className="claim-badge badge-thermal">
                {zone.zone_type.replace('_', ' ')}
              </span>
            </div>
            <ConfidenceBar confidence={zone.confidence} />
            <p style={{ fontSize: '0.8rem', color: '#475569', margin: '6px 0 4px 0', lineHeight: '1.4' }}>
              {zone.description.substring(0, 150)}{zone.description.length > 150 ? '...' : ''}
            </p>
            {zone.uncertainty_note && (
              <p style={{ fontSize: '0.75rem', color: '#f59e0b', margin: '0' }}>
                ⚠ {zone.uncertainty_note}
              </p>
            )}
            {zone.evidence_summary.length > 0 && (
              <div style={{ marginTop: '4px' }}>
                {zone.evidence_summary.slice(0, 2).map((ev, i) => (
                  <p key={i} style={{ fontSize: '0.7rem', color: '#94a3b8', margin: '2px 0' }}>
                    • {ev}
                  </p>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
