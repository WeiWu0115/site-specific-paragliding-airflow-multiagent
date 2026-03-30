/**
 * TimeSlider component for selecting hour of day (6-20 local).
 *
 * Used to filter planning recommendations and overlay data by time window.
 */

interface TimeSliderProps {
  value: number;
  onChange: (hour: number) => void;
  min?: number;
  max?: number;
}

export function TimeSlider({ value, onChange, min = 6, max = 20 }: TimeSliderProps) {
  const formatHour = (h: number) => {
    const ampm = h < 12 ? 'AM' : 'PM';
    const display = h === 0 ? 12 : h > 12 ? h - 12 : h;
    return `${display}:00 ${ampm}`;
  };

  return (
    <div className="panel">
      <div className="panel-header">Time of Day</div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span style={{ fontSize: '0.875rem', color: '#64748b' }}>{formatHour(min)}</span>
          <span style={{
            fontSize: '1.125rem',
            fontWeight: '700',
            color: '#1e293b',
            padding: '4px 12px',
            background: '#eff6ff',
            borderRadius: '6px',
          }}>
            {formatHour(value)}
          </span>
          <span style={{ fontSize: '0.875rem', color: '#64748b' }}>{formatHour(max)}</span>
        </div>
        <input
          type="range"
          min={min}
          max={max}
          step={1}
          value={value}
          onChange={(e) => onChange(parseInt(e.target.value, 10))}
          style={{
            width: '100%',
            accentColor: 'var(--color-primary)',
            cursor: 'pointer',
          }}
        />
        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
          {[6, 8, 10, 12, 14, 16, 18, 20].map((h) => (
            <span
              key={h}
              style={{
                fontSize: '0.7rem',
                color: h === value ? '#2563eb' : '#94a3b8',
                fontWeight: h === value ? '600' : '400',
                cursor: 'pointer',
              }}
              onClick={() => onChange(h)}
            >
              {h}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}
