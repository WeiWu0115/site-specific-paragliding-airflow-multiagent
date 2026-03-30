/**
 * HistoricalReplayPanel — controls and summary for flight track replay.
 *
 * Shows a list of historical IGC/GPX tracks with metadata and a simple
 * playback control for the replay page. Segment statistics (climb/glide/sink)
 * are displayed per track.
 */

import { FlightTrackSummary } from '@/lib/types';

function formatDuration(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  if (h > 0) return `${h}h ${m}m`;
  return `${m}m`;
}

function formatDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

interface SegmentBarProps {
  climb: number;
  glide: number;
  sink: number;
}

function SegmentBar({ climb, glide, sink }: SegmentBarProps) {
  const total = climb + glide + sink;
  if (total === 0) return null;
  const climbPct = (climb / total) * 100;
  const glidePct = (glide / total) * 100;
  const sinkPct  = (sink / total) * 100;

  return (
    <div>
      <div style={{ display: 'flex', height: '6px', borderRadius: '3px', overflow: 'hidden', marginBottom: '3px' }}>
        <div style={{ width: `${climbPct}%`, background: '#10b981' }} />
        <div style={{ width: `${glidePct}%`, background: '#2563eb' }} />
        <div style={{ width: `${sinkPct}%`, background: '#ef4444' }} />
      </div>
      <div style={{ display: 'flex', gap: '8px', fontSize: '0.65rem', color: '#94a3b8' }}>
        <span style={{ color: '#10b981' }}>▲ {Math.round(climbPct)}%</span>
        <span style={{ color: '#2563eb' }}>→ {Math.round(glidePct)}%</span>
        <span style={{ color: '#ef4444' }}>▼ {Math.round(sinkPct)}%</span>
      </div>
    </div>
  );
}

interface TrackRowProps {
  track: FlightTrackSummary;
  isSelected: boolean;
  onSelect: () => void;
}

function TrackRow({ track, isSelected, onSelect }: TrackRowProps) {
  return (
    <div
      onClick={onSelect}
      style={{
        padding: '0.75rem',
        border: isSelected ? '1px solid #2563eb' : '1px solid #e2e8f0',
        borderRadius: '6px',
        background: isSelected ? '#eff6ff' : '#f8fafc',
        cursor: 'pointer',
        marginBottom: '0.5rem',
        transition: 'background 0.15s, border-color 0.15s',
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
        <span style={{ fontWeight: '600', fontSize: '0.8rem', color: '#1e293b' }}>
          {formatDate(track.date)}
        </span>
        <span style={{ fontSize: '0.75rem', color: '#64748b' }}>
          {formatDuration(track.duration_s)}
        </span>
      </div>
      <div style={{ display: 'flex', gap: '1rem', fontSize: '0.75rem', color: '#64748b', marginBottom: '6px' }}>
        {track.max_alt_m && (
          <span>Max {track.max_alt_m.toFixed(0)}m</span>
        )}
        {track.avg_climb_ms && (
          <span>Avg climb {track.avg_climb_ms.toFixed(1)} m/s</span>
        )}
        {track.track_type && (
          <span style={{ textTransform: 'uppercase', fontSize: '0.65rem', letterSpacing: '0.04em' }}>
            {track.track_type}
          </span>
        )}
      </div>
      <SegmentBar
        climb={track.climb_seconds ?? 0}
        glide={track.glide_seconds ?? 0}
        sink={track.sink_seconds ?? 0}
      />
    </div>
  );
}

interface ReplayControlsProps {
  isPlaying: boolean;
  onPlay: () => void;
  onPause: () => void;
  onReset: () => void;
  speed: number;
  onSpeedChange: (s: number) => void;
}

function ReplayControls({ isPlaying, onPlay, onPause, onReset, speed, onSpeedChange }: ReplayControlsProps) {
  const btnStyle = (primary: boolean): React.CSSProperties => ({
    padding: '6px 14px',
    borderRadius: '5px',
    border: 'none',
    cursor: 'pointer',
    fontSize: '0.8rem',
    fontWeight: '600',
    background: primary ? '#2563eb' : '#e2e8f0',
    color: primary ? 'white' : '#475569',
  });

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
      <button style={btnStyle(false)} onClick={onReset}>⏮ Reset</button>
      {isPlaying
        ? <button style={btnStyle(true)} onClick={onPause}>⏸ Pause</button>
        : <button style={btnStyle(true)} onClick={onPlay}>▶ Play</button>
      }
      <div style={{ display: 'flex', alignItems: 'center', gap: '4px', marginLeft: 'auto' }}>
        <span style={{ fontSize: '0.75rem', color: '#64748b' }}>Speed</span>
        {[1, 2, 5, 10].map((s) => (
          <button
            key={s}
            onClick={() => onSpeedChange(s)}
            style={{
              padding: '3px 8px',
              borderRadius: '4px',
              border: 'none',
              cursor: 'pointer',
              fontSize: '0.75rem',
              fontWeight: '600',
              background: speed === s ? '#2563eb' : '#e2e8f0',
              color: speed === s ? 'white' : '#475569',
            }}
          >
            {s}x
          </button>
        ))}
      </div>
    </div>
  );
}

interface HistoricalReplayPanelProps {
  tracks: FlightTrackSummary[];
  selectedTrackId?: number | null;
  onTrackSelect?: (id: number) => void;
  isPlaying?: boolean;
  onPlay?: () => void;
  onPause?: () => void;
  onReset?: () => void;
  speed?: number;
  onSpeedChange?: (s: number) => void;
}

export function HistoricalReplayPanel({
  tracks,
  selectedTrackId,
  onTrackSelect,
  isPlaying = false,
  onPlay = () => {},
  onPause = () => {},
  onReset = () => {},
  speed = 1,
  onSpeedChange = () => {},
}: HistoricalReplayPanelProps) {
  return (
    <div className="panel">
      <div className="panel-header">Historical Flight Replay</div>

      {selectedTrackId !== null && selectedTrackId !== undefined && (
        <div style={{ marginBottom: '0.75rem' }}>
          <ReplayControls
            isPlaying={isPlaying}
            onPlay={onPlay}
            onPause={onPause}
            onReset={onReset}
            speed={speed}
            onSpeedChange={onSpeedChange}
          />
        </div>
      )}

      {tracks.length === 0 ? (
        <p style={{ color: '#94a3b8', fontSize: '0.875rem' }}>
          No flight tracks imported. Use the CLI to import IGC or GPX files.
        </p>
      ) : (
        <>
          <p style={{ fontSize: '0.75rem', color: '#94a3b8', marginBottom: '0.5rem' }}>
            {tracks.length} track{tracks.length !== 1 ? 's' : ''} available. Select one to replay.
          </p>
          <div style={{ maxHeight: '320px', overflowY: 'auto', paddingRight: '2px' }}>
            {tracks.map((t) => (
              <TrackRow
                key={t.id}
                track={t}
                isSelected={selectedTrackId === t.id}
                onSelect={() => onTrackSelect && onTrackSelect(t.id)}
              />
            ))}
          </div>
        </>
      )}
    </div>
  );
}
