/**
 * Typed API client for paraglide-frontend.
 *
 * All functions use fetch with proper error handling.
 * Base URL is configured via NEXT_PUBLIC_API_URL environment variable.
 */

import type {
  CloudObservation,
  KnowledgeItemCreate,
  PlanningRequest,
  PlanningResponse,
  SiteProfile,
  TerrainFeature,
  UnityOverlayPayload,
  WeatherForecast,
} from './types';

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

class ApiError extends Error {
  constructor(
    public status: number,
    public statusText: string,
    message: string
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

async function apiFetch<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${BASE_URL}${path}`;
  const response = await fetch(url, {
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
    ...options,
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new ApiError(
      response.status,
      response.statusText,
      `API error ${response.status} for ${path}: ${errorText}`
    );
  }

  return response.json() as Promise<T>;
}

// ---------------------------------------------------------------------------
// Site
// ---------------------------------------------------------------------------

export async function getSiteProfile(): Promise<SiteProfile> {
  return apiFetch<SiteProfile>('/site');
}

export async function getTerrain(): Promise<TerrainFeature[]> {
  const data = await apiFetch<{ features: TerrainFeature[] }>('/terrain');
  return data.features ?? [];
}

// ---------------------------------------------------------------------------
// Weather
// ---------------------------------------------------------------------------

export async function getForecast(): Promise<WeatherForecast> {
  return apiFetch<WeatherForecast>('/forecast');
}

// ---------------------------------------------------------------------------
// Clouds
// ---------------------------------------------------------------------------

export async function getClouds(): Promise<CloudObservation> {
  return apiFetch<CloudObservation>('/clouds');
}

// ---------------------------------------------------------------------------
// Planning
// ---------------------------------------------------------------------------

export async function runPlanning(
  request: PlanningRequest
): Promise<PlanningResponse> {
  return apiFetch<PlanningResponse>('/planning', {
    method: 'POST',
    body: JSON.stringify(request),
  });
}

export async function getPlanningSession(sessionId: number): Promise<PlanningResponse> {
  return apiFetch<PlanningResponse>(`/planning/${sessionId}`);
}

// ---------------------------------------------------------------------------
// Unity Overlays
// ---------------------------------------------------------------------------

export async function getUnityOverlays(sessionId?: string): Promise<UnityOverlayPayload> {
  const path = sessionId ? `/unity/overlays/${sessionId}` : '/unity/overlays';
  return apiFetch<UnityOverlayPayload>(path);
}

// ---------------------------------------------------------------------------
// Knowledge
// ---------------------------------------------------------------------------

export async function importKnowledge(item: KnowledgeItemCreate): Promise<void> {
  await apiFetch('/knowledge/import', {
    method: 'POST',
    body: JSON.stringify(item),
  });
}

// ---------------------------------------------------------------------------
// Tracks
// ---------------------------------------------------------------------------

export async function importTrack(file: File, siteId: string): Promise<void> {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('site_id', siteId);

  const url = `${BASE_URL}/tracks/import`;
  const response = await fetch(url, {
    method: 'POST',
    body: formData,
    // Do NOT set Content-Type header — let browser set multipart boundary
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new ApiError(response.status, response.statusText, errorText);
  }
}

export async function listTracks(): Promise<unknown[]> {
  return apiFetch<unknown[]>('/tracks');
}

// ---------------------------------------------------------------------------
// Health
// ---------------------------------------------------------------------------

export async function checkHealth(): Promise<{ status: string; site_id: string }> {
  return apiFetch('/health');
}
