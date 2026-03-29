/**
 * Base fetch wrapper for the Nexus Sim orchestrator API.
 *
 * All API calls go through apiFetch() which handles:
 * - Base URL resolution (env var or localhost:8000 default)
 * - JSON content-type headers
 * - Error extraction with status code and detail text
 */

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
