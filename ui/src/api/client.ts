/**
 * Base fetch wrapper for the A.R.C Studio orchestrator API.
 *
 * All API calls go through apiFetch() which handles:
 * - Base URL resolution (env var or localhost:8000 default)
 * - JSON content-type headers
 * - Error extraction with status code and detail text
 */

import type { MediaUploadResponse } from './types';

export const API_BASE =
  import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export async function apiFetch<T>(
  path: string,
  options?: RequestInit,
): Promise<T> {
  const url = `${API_BASE}${path}`;

  const res = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  });

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      if (body.detail) {
        detail = typeof body.detail === 'string'
          ? body.detail
          : JSON.stringify(body.detail);
      }
    } catch {
      // Response body not JSON — use statusText
    }
    throw new Error(`${res.status}: ${detail}`);
  }

  // Handle 204 No Content (e.g., DELETE responses)
  if (res.status === 204) {
    return undefined as T;
  }

  return res.json() as Promise<T>;
}

/**
 * Upload a media file (Phase 2 A.1 — audio input support).
 *
 * The backend (parallel agent track) exposes POST /api/campaigns/upload
 * which accepts a multipart/form-data body and returns { media_path }.
 * The returned path is then submitted with the campaign create request
 * together with `media_type: "audio"`.
 *
 * If the endpoint is not yet live this will raise a 404 — callers should
 * surface that error directly (do NOT work around it).
 */
export async function uploadMedia(file: File): Promise<MediaUploadResponse> {
  const url = `${API_BASE}/api/campaigns/upload`;
  const form = new FormData();
  form.append('file', file);

  const res = await fetch(url, {
    method: 'POST',
    body: form,
    // Deliberately NO Content-Type header — the browser sets the
    // multipart boundary automatically.
  });

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      if (body.detail) {
        detail =
          typeof body.detail === 'string'
            ? body.detail
            : JSON.stringify(body.detail);
      }
    } catch {
      // Response body not JSON — use statusText
    }
    throw new Error(`${res.status}: ${detail}`);
  }

  return res.json() as Promise<MediaUploadResponse>;
}
