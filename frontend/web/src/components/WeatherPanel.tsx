/**
 * WeatherPanel — shows hourly forecast table with thermal index column.
 */

import { WeatherHour } from '@/lib/types';

function computeThermalIndex(h: WeatherHour): number {
  // Simplified version of WeatherAgent.score_hour()
  const spread = Math.max(0, h.temp_c - h.dewpoint_c);
  const dew = Math.min(1, spread / 20);
  const windFactor = Math.exp(-0.5 * Math.pow((h.wind_speed_kmh - 15) / 7, 2));
  const hour = new Date(h.time).getUTCHours();
  const timeFactor = Math.exp(-0.5 * Math.pow((hour - 13) / 2.5, 2));
  const cloudFactor = h.cloud_cover_pct < 10 ? 0.75
    : h.cloud_cover_pct <= 60 ? Math.max(0.4, 1 - Math.abs(h.cloud_cover_pct - 35) / 60)
    : Math.max(0.1, 1 - (h.cloud_cover_pct - 60) / 50);
  return Math.round(dew * windFactor * timeFactor * cloudFactor * 100) / 100;
}

function windDirLabel(deg: number): string {
  const dirs = ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE', 'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW'];
  return dirs[Math.round(deg / 22.5) % 16];
}

function thermalIndexColor(score: number): string {
  if (score >= 0.55) return '#16a34a';
  if (score >= 0.35) return '#d97706';
  return '#dc2626';
}

interface WeatherPanelProps {
  forecast: { hourly: WeatherHour[] } | null;
  selectedHour?: number;
}

export function WeatherPanel({ forecast, selectedHour }: WeatherPanelProps) {
  if (!forecast || forecast.hourly.length === 0) {
    return (
      <div className="panel">
        <div className="panel-header">Weather Forecast</div>
        <p style={{ color: '#94a3b8', fontSize: '0.875rem' }}>No forecast data. Run planning to fetch.</p>
      </div>
    );
  }

  // Show only daytime hours
  const dayHours = forecast.hourly.filter((h) => {
    const hour = new Date(h.time).getUTCHours();
    return hour >= 6 && hour <= 20;
  });

  return (
    <div className="panel">
      <div className="panel-header">Hourly Weather Forecast</div>
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.8rem' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid #e2e8f0', color: '#64748b' }}>
              <th style={{ textAlign: 'left', padding: '4px 6px' }}>Hour</th>
              <th style={{ textAlign: 'right', padding: '4px 6px' }}>°C</th>
              <th style={{ textAlign: 'right', padding: '4px 6px' }}>Dew</th>
              <th style={{ textAlign: 'right', padding: '4px 6px' }}>Wind</th>
              <th style={{ textAlign: 'left', padding: '4px 6px' }}>Dir</th>
              <th style={{ textAlign: 'right', padding: '4px 6px' }}>☁️</th>
              <th style={{ textAlign: 'right', padding: '4px 6px' }}>Index</th>
            </tr>
          </thead>
          <tbody>
            {dayHours.map((h) => {
              const hour = new Date(h.time).getUTCHours();
              const thermalIdx = computeThermalIndex(h);
              const isSelected = hour === selectedHour;
              return (
                <tr
                  key={h.time}
                  style={{
                    background: isSelected ? '#eff6ff' : 'transparent',
                    borderBottom: '1px solid #f1f5f9',
                  }}
                >
                  <td style={{ padding: '4px 6px', fontWeight: isSelected ? '600' : '400' }}>
                    {hour.toString().padStart(2, '0')}:00
                  </td>
                  <td style={{ textAlign: 'right', padding: '4px 6px' }}>{h.temp_c.toFixed(0)}</td>
                  <td style={{ textAlign: 'right', padding: '4px 6px', color: '#64748b' }}>
                    {h.dewpoint_c.toFixed(0)}
                  </td>
                  <td style={{ textAlign: 'right', padding: '4px 6px' }}>
                    {h.wind_speed_kmh.toFixed(0)} km/h
                  </td>
                  <td style={{ padding: '4px 6px', color: '#64748b' }}>
                    {windDirLabel(h.wind_dir_deg)}
                  </td>
                  <td style={{ textAlign: 'right', padding: '4px 6px', color: '#64748b' }}>
                    {h.cloud_cover_pct.toFixed(0)}%
                  </td>
                  <td style={{ textAlign: 'right', padding: '4px 6px' }}>
                    <span style={{ color: thermalIndexColor(thermalIdx), fontWeight: '600' }}>
                      {thermalIdx.toFixed(2)}
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p style={{ fontSize: '0.7rem', color: '#94a3b8', marginTop: '0.5rem' }}>
        Thermal index: simplified heuristic. Green ≥ 0.55, amber 0.35–0.55, red &lt; 0.35
      </p>
    </div>
  );
}
