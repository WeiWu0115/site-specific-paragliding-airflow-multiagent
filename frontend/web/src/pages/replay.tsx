/**
 * Replay page — historical flight track review and multi-agent overlay comparison.
 *
 * Pilots and researchers can select a historical IGC/GPX track, play it back
 * with speed control, and compare the per-flight thermal sensemaking against
 * current agent recommendations.
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import Head from 'next/head';
import Link from 'next/link';
import { listTracks } from '@/lib/api';
import type { FlightTrackSummary } from '@/lib/types';
import { HistoricalReplayPanel } from '@/components/HistoricalReplayPanel';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatDuration(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  if (h > 0) return `${h}h ${m}m`;
  if (m > 0) return `${m}m ${s}s`;
  return `${s}s`;
}

function formatTimestamp(iso: string): string {
  return new Date(iso).toLocaleString('en-US', {
    month: 'short', day: 'numeric', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  });
}

// ---------------------------------------------------------------------------
// Replay progress bar
// ---------------------------------------------------------------------------

interface ReplayProgressProps {
  progress: number; // 0–1
  durationS: number;
}

function ReplayProgress({ progress, durationS }: ReplayProgressProps) {
  const elapsed = Math.round(progress * durationS);
  return (
    <div style={{ marginBottom: '0.75rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', color: '#64748b', marginBottom: '4px' }}>
        <span>{formatDuration(elapsed)}</span>
        <span>{formatDuration(durationS)}</span>
      </div>
      <div
        style={{
          height: '6px',
          borderRadius: '3px',
          background: '#e2e8f0',
          overflow: 'hidden',
        }}
      >
        <div
          style={{
            height: '100%',
            width: `${Math.round(progress * 100)}%`,
            background: '#2563eb',
            borderRadius: '3px',
            transition: 'width 0.5s linear',
          }}
        />
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Track detail card
// ---------------------------------------------------------------------------

interface TrackDetailProps {
  track: FlightTrackSummary;
  progress: number;
  isPlaying: boolean;
}

function TrackDetail({ track, progress, isPlaying }: TrackDetailProps) {
  return (
    <div className="panel">
      <div className="panel-header">Track Detail</div>
      <div style={{ marginBottom: '0.75rem' }}>
        <div style={{ fontWeight: '700', fontSize: '1rem', color: '#1e293b', marginBottom: '2px' }}>
          {formatTimestamp(track.date)}
        </div>
        <div style={{ fontSize: '0.75rem', color: '#64748b' }}>
          {track.track_type?.toUpperCase() ?? 'UNKNOWN'} · {formatDuration(track.duration_s)}
        </div>
      </div>
      <ReplayProgress progress={progress} durationS={track.duration_s} />
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '0.5rem' }}>
        {[
          { label: 'Max Alt', value: track.max_alt_m ? `${track.max_alt_m.toFixed(0)}m` : '—' },
          { label: 'Avg Climb', value: track.avg_climb_ms ? `${track.avg_climb_ms.toFixed(1)} m/s` : '—' },
          { label: 'Status', value: isPlaying ? 'Playing' : 'Paused' },
        ].map(({ label, value }) => (
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
            <div style={{ fontWeight: '700', color: '#1e293b' }}>{value}</div>
            <div style={{ fontSize: '0.65rem', color: '#94a3b8', textTransform: 'uppercase' }}>{label}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page component
// ---------------------------------------------------------------------------

export default function ReplayPage() {
  const [tracks, setTracks] = useState<FlightTrackSummary[]>([]);
  const [selectedTrackId, setSelectedTrackId] = useState<number | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [speed, setSpeed] = useState(1);
  const [progress, setProgress] = useState(0);
  const [loadError, setLoadError] = useState<string | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Load track list
  useEffect(() => {
    listTracks()
      .then((raw) => {
        // Cast raw unknown[] to FlightTrackSummary[] — API returns serialised DB rows
        setTracks(raw as FlightTrackSummary[]);
      })
      .catch((err) => {
        setLoadError(err instanceof Error ? err.message : String(err));
      });
  }, []);

  const selectedTrack = tracks.find((t) => t.id === selectedTrackId) ?? null;

  // Playback tick
  useEffect(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
    if (isPlaying && selectedTrack) {
      const tickMs = 500; // update every 500ms
      const durationS = selectedTrack.duration_s;
      const incrementPerTick = (speed * tickMs) / (durationS * 1000);
      intervalRef.current = setInterval(() => {
        setProgress((prev) => {
          const next = prev + incrementPerTick;
          if (next >= 1) {
            setIsPlaying(false);
            return 1;
          }
          return next;
        });
      }, tickMs);
    }
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [isPlaying, speed, selectedTrack]);

  const handleTrackSelect = useCallback((id: number) => {
    setSelectedTrackId(id);
    setProgress(0);
    setIsPlaying(false);
  }, []);

  const handlePlay = useCallback(() => setIsPlaying(true), []);
  const handlePause = useCallback(() => setIsPlaying(false), []);
  const handleReset = useCallback(() => {
    setIsPlaying(false);
    setProgress(0);
  }, []);

  return (
    <>
      <Head>
        <title>Flight Replay · Eagle Ridge</title>
        <meta name="description" content="Historical flight track replay for Eagle Ridge Flying Site" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
      </Head>

      <div style={{ maxWidth: '1400px', margin: '0 auto', padding: '1rem' }}>
        {/* Nav bar */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
          <div style={{ fontSize: '0.875rem', color: '#64748b' }}>
            Eagle Ridge · Historical Flight Replay
          </div>
          <div style={{ display: 'flex', gap: '1rem', fontSize: '0.875rem' }}>
            <Link href="/" style={{ color: '#64748b', textDecoration: 'none' }}>
              Planning
            </Link>
            <Link href="/replay" style={{ color: '#2563eb', fontWeight: '600', textDecoration: 'none' }}>
              Replay
            </Link>
          </div>
        </div>

        {/* Error */}
        {loadError && (
          <div className="advisory-banner" style={{ marginBottom: '1rem', background: '#fef2f2', borderColor: '#fca5a5' }}>
            <strong>Error loading tracks:</strong> {loadError}
          </div>
        )}

        {/* Advisory */}
        <div className="advisory-banner" style={{ marginBottom: '1rem' }}>
          <strong>Advisory only.</strong> Historical tracks are for research and debriefing purposes.
          Past conditions do not guarantee future flyability. Always conduct a fresh pre-flight assessment.
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '380px 1fr', gap: '1rem', alignItems: 'start' }}>
          {/* Left: track list */}
          <div>
            <HistoricalReplayPanel
              tracks={tracks}
              selectedTrackId={selectedTrackId}
              onTrackSelect={handleTrackSelect}
              isPlaying={isPlaying}
              onPlay={handlePlay}
              onPause={handlePause}
              onReset={handleReset}
              speed={speed}
              onSpeedChange={setSpeed}
            />
          </div>

          {/* Right: detail / map placeholder */}
          <div>
            {selectedTrack ? (
              <>
                <TrackDetail track={selectedTrack} progress={progress} isPlaying={isPlaying} />

                {/* Map placeholder */}
                <div className="panel">
                  <div className="panel-header">Track Map</div>
                  <div
                    style={{
                      height: '400px',
                      background: '#f1f5f9',
                      borderRadius: '6px',
                      display: 'flex',
                      flexDirection: 'column',
                      alignItems: 'center',
                      justifyContent: 'center',
                      color: '#94a3b8',
                      fontSize: '0.875rem',
                      textAlign: 'center',
                      gap: '0.5rem',
                    }}
                  >
                    <div style={{ fontSize: '2rem' }}>🗺</div>
                    <div style={{ fontWeight: '600' }}>Map View</div>
                    <div style={{ maxWidth: '280px', lineHeight: '1.5' }}>
                      Integrate react-leaflet here to render the GPS track overlaid on
                      terrain tiles. GeoJSON for Eagle Ridge: 35.492°N, 118.187°W.
                    </div>
                    <div style={{ fontSize: '0.75rem', color: '#cbd5e1' }}>
                      Track ID: {selectedTrack.id} · Progress: {Math.round(progress * 100)}%
                    </div>
                  </div>
                </div>
              </>
            ) : (
              <div className="panel">
                <div className="panel-header">Track Map</div>
                <div
                  style={{
                    height: '300px',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    color: '#94a3b8',
                    fontSize: '0.875rem',
                  }}
                >
                  Select a track from the list to begin replay.
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </>
  );
}
