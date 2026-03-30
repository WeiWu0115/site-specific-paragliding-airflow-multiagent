/**
 * LaunchTimingPanel — shows recommended launch windows with confidence bars.
 */

import { LaunchWindow } from '@/lib/types';

function ConfidenceBar({ score, color }: { score: number; color: string }) {
  const pct = Math.round(score * 100);
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

function formatHour(h: number): string {
  const ampm = h < 12 ? 'AM' : 'PM';
  const display = h === 0 ? 12 : h > 12 ? h - 12 : h;
  return `${display}:00 ${ampm}`;
}

function windowColor(score: number): string {
  if (score >= 0.70) return '#10b981';
  if (score >= 0.45) return '#f59e0b';
  return '#ef4444';
}

function qualityLabel(score: number): string {
  if (score >= 0.75) return 'Excellent';
  if (score >= 0.60) return 'Good';
  if (score >= 0.45) return 'Marginal';
  return 'Poor';
}

interface LaunchTimingPanelProps {
  windows: LaunchWindow[];
  selectedHour?: number;
  onHourSelect?: (hour: number) => void;
}

export function LaunchTimingPanel({ windows, selectedHour, onHourSelect }: LaunchTimingPanelProps) {
  if (!windows || windows.length === 0) {
    return (
      <div className="panel">
        <div className="panel-header">Launch Timing</div>
        <p style={{ color: '#94a3b8', fontSize: '0.875rem' }}>
          No launch windows computed. Run planning to generate timing recommendations.
        </p>
      </div>
    );
  }

  const sorted = [...windows].sort((a, b) => b.score - a.score);

  return (
    <div className="panel">
      <div className="panel-header">Recommended Launch Windows</div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
        {sorted.map((win) => {
          const color = windowColor(win.score);
          const isSelected = selectedHour !== undefined &&
            selectedHour >= win.hour_start && selectedHour < win.hour_end;

          return (
            <div
              key={`${win.hour_start}-${win.hour_end}`}
              onClick={() => onHourSelect && onHourSelect(win.hour_start)}
              style={{
                padding: '0.75rem',
                background: isSelected ? '#eff6ff' : '#f8fafc',
                borderRadius: '6px',
                border: isSelected ? '1px solid #2563eb' : '1px solid #e2e8f0',
                cursor: onHourSelect ? 'pointer' : 'default',
                transition: 'background 0.15s, border-color 0.15s',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                <span style={{ fontWeight: '600', fontSize: '0.875rem', color: '#1e293b' }}>
                  {formatHour(win.hour_start)} – {formatHour(win.hour_end)}
                </span>
                <span
                  style={{
                    fontSize: '0.75rem',
                    fontWeight: '600',
                    color,
                    background: `${color}18`,
                    padding: '2px 8px',
                    borderRadius: '12px',
                  }}
                >
                  {qualityLabel(win.score)}
                </span>
              </div>
              <ConfidenceBar score={win.score} color={color} />
              {win.notes && win.notes.length > 0 && (
                <div style={{ marginTop: '6px' }}>
                  {win.notes.slice(0, 2).map((note, i) => (
                    <p key={i} style={{ fontSize: '0.75rem', color: '#64748b', margin: '2px 0' }}>
                      • {note}
                    </p>
                  ))}
                </div>
              )}
              <div style={{ display: 'flex', gap: '1rem', marginTop: '4px', fontSize: '0.7rem', color: '#94a3b8' }}>
                {win.wind_speed_kmh !== undefined && (
                  <span>Wind: {win.wind_speed_kmh.toFixed(0)} km/h</span>
                )}
                {win.thermal_index !== undefined && (
                  <span>Thermal idx: {win.thermal_index.toFixed(2)}</span>
                )}
              </div>
            </div>
          );
        })}
      </div>
      <p style={{ fontSize: '0.7rem', color: '#94a3b8', marginTop: '0.5rem' }}>
        Click a window to highlight it on the time slider. Windows are ranked by composite score.
      </p>
    </div>
  );
}
