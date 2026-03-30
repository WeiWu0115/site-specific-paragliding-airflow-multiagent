/**
 * SiteOverview — renders Eagle Ridge site header with weather summary and status badge.
 *
 * Displays site name, coordinates, today's conditions at a glance,
 * and a colored status pill (Flyable / Marginal / Grounded).
 */

import { SiteProfile, WeatherForecast } from '@/lib/types';

function computeCurrentConditions(forecast: WeatherForecast | null, hourUTC: number) {
  if (!forecast || forecast.hourly.length === 0) return null;
  return forecast.hourly.find((h) => new Date(h.time).getUTCHours() === hourUTC) ?? null;
}

function flyabilityStatus(wind_kmh: number | undefined, thermal_idx: number | undefined) {
  if (wind_kmh === undefined || thermal_idx === undefined) {
    return { label: 'Unknown', color: '#94a3b8', bg: '#f1f5f9' };
  }
  if (wind_kmh > 35) {
    return { label: 'Grounded', color: '#991b1b', bg: '#fef2f2' };
  }
  if (wind_kmh > 25 || thermal_idx < 0.25) {
    return { label: 'Marginal', color: '#92400e', bg: '#fef3c7' };
  }
  if (thermal_idx >= 0.45 && wind_kmh <= 25) {
    return { label: 'Flyable', color: '#166534', bg: '#f0fdf4' };
  }
  return { label: 'Marginal', color: '#92400e', bg: '#fef3c7' };
}

function computeThermalIndex(temp_c: number, dewpoint_c: number, wind_kmh: number, cloud_pct: number, hourUTC: number): number {
  const spread = Math.max(0, temp_c - dewpoint_c);
  const dew = Math.min(1, spread / 20);
  const windFactor = Math.exp(-0.5 * Math.pow((wind_kmh - 15) / 7, 2));
  const timeFactor = Math.exp(-0.5 * Math.pow((hourUTC - 13) / 2.5, 2));
  const cloudFactor = cloud_pct < 10 ? 0.75
    : cloud_pct <= 60 ? Math.max(0.4, 1 - Math.abs(cloud_pct - 35) / 60)
    : Math.max(0.1, 1 - (cloud_pct - 60) / 50);
  return Math.round(dew * windFactor * timeFactor * cloudFactor * 100) / 100;
}

interface StatTileProps {
  label: string;
  value: string;
  sub?: string;
}

function StatTile({ label, value, sub }: StatTileProps) {
  return (
    <div
      style={{
        textAlign: 'center',
        padding: '0.5rem 0.75rem',
        background: '#f8fafc',
        borderRadius: '6px',
        border: '1px solid #e2e8f0',
        flex: '1 1 80px',
        minWidth: '80px',
      }}
    >
      <div style={{ fontSize: '1.1rem', fontWeight: '700', color: '#1e293b' }}>{value}</div>
      {sub && <div style={{ fontSize: '0.65rem', color: '#94a3b8' }}>{sub}</div>}
      <div style={{ fontSize: '0.65rem', color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.04em', marginTop: '2px' }}>
        {label}
      </div>
    </div>
  );
}

interface SiteOverviewProps {
  site: SiteProfile | null;
  forecast: WeatherForecast | null;
  selectedHour: number;
}

export function SiteOverview({ site, forecast, selectedHour }: SiteOverviewProps) {
  const currentHour = computeCurrentConditions(forecast, selectedHour);
  const thermalIdx = currentHour
    ? computeThermalIndex(
        currentHour.temp_c,
        currentHour.dewpoint_c,
        currentHour.wind_speed_kmh,
        currentHour.cloud_cover_pct,
        selectedHour
      )
    : undefined;

  const status = flyabilityStatus(currentHour?.wind_speed_kmh, thermalIdx);

  const siteName = site?.name ?? 'Eagle Ridge Flying Site';
  const lat = site?.location?.lat ?? 35.492;
  const lon = site?.location?.lon ?? -118.187;
  const elevM = site?.location?.elevation_m ?? 1340;

  const dirLabel = (deg: number | undefined) => {
    if (deg === undefined) return '—';
    const dirs = ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE', 'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW'];
    return dirs[Math.round(deg / 22.5) % 16];
  };

  return (
    <div
      style={{
        background: 'white',
        border: '1px solid #e2e8f0',
        borderRadius: '8px',
        padding: '1.25rem',
        marginBottom: '1rem',
        boxShadow: '0 1px 3px rgba(0,0,0,0.05)',
      }}
    >
      {/* Site header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.75rem' }}>
        <div>
          <h1 style={{ margin: 0, fontSize: '1.1rem', fontWeight: '700', color: '#1e293b' }}>
            {siteName}
          </h1>
          <div style={{ fontSize: '0.75rem', color: '#94a3b8', marginTop: '2px' }}>
            {lat.toFixed(3)}°N, {Math.abs(lon).toFixed(3)}°W · {elevM}m AMSL · Tehachapi Mountains, CA
          </div>
        </div>
        <span
          style={{
            fontSize: '0.8rem',
            fontWeight: '700',
            color: status.color,
            background: status.bg,
            padding: '4px 12px',
            borderRadius: '12px',
            border: `1px solid ${status.color}40`,
            flexShrink: 0,
          }}
        >
          {status.label}
        </span>
      </div>

      {/* Condition tiles */}
      <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
        <StatTile
          label="Temp"
          value={currentHour ? `${currentHour.temp_c.toFixed(0)}°C` : '—'}
          sub={currentHour ? `Dew ${currentHour.dewpoint_c.toFixed(0)}°C` : undefined}
        />
        <StatTile
          label="Wind"
          value={currentHour ? `${currentHour.wind_speed_kmh.toFixed(0)} km/h` : '—'}
          sub={currentHour ? dirLabel(currentHour.wind_dir_deg) : undefined}
        />
        <StatTile
          label="Cloud"
          value={currentHour ? `${currentHour.cloud_cover_pct.toFixed(0)}%` : '—'}
        />
        <StatTile
          label="Thermal Idx"
          value={thermalIdx !== undefined ? thermalIdx.toFixed(2) : '—'}
          sub="heuristic"
        />
      </div>

      {/* Advisory disclaimer */}
      <div className="advisory-banner" style={{ marginTop: '0.75rem', fontSize: '0.75rem' }}>
        <strong>Advisory only.</strong> This tool does not replace a qualified briefing.
        Always verify conditions on-site and exercise independent pilot judgment.
        Not certified for flight operations.
      </div>
    </div>
  );
}
