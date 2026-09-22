/**
 * Centralized runtime configuration. Every other module reads backend
 * URLs from here instead of touching import.meta.env directly, so the
 * production backend URL is never hardcoded inside a component.
 *
 * Anything prefixed VITE_ is bundled into the client and visible to
 * anyone viewing the page — never put secrets here.
 */

function stripTrailingSlash(url: string): string {
  return url.endsWith("/") ? url.slice(0, -1) : url;
}

export const config = {
  apiUrl: stripTrailingSlash(
    import.meta.env.VITE_API_URL ?? "http://localhost:8000"
  ),
  wsUrl: import.meta.env.VITE_WS_URL ?? "ws://localhost:8000/ws",
  useMockData: import.meta.env.VITE_USE_MOCK_DATA === "true",
} as const;
