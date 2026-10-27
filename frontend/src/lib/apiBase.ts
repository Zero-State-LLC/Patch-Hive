// The API the browser talks to. Dev builds fall back to the local backend; a
// production build needs an https VITE_API_BASE_URL, or it has no API at all.
export function resolveApiBase(
  env: { DEV: boolean; VITE_API_BASE_URL?: string },
  devFallback: string | null = null,
): string | null {
  const configured = env.VITE_API_BASE_URL?.trim();
  if (configured) {
    return env.DEV || configured.startsWith("https://") ? configured : null;
  }
  return env.DEV ? devFallback : null;
}

// Sign-in is offered only when the operator says the API is live
// (VITE_ACCOUNTS_OPEN=true): a password form that posts nowhere reachable is
// both broken and what phishing scanners look for.
export function accountsOpen(
  env: { DEV: boolean; VITE_ACCOUNTS_OPEN?: string },
  apiBase: string | null,
): boolean {
  return apiBase !== null && (env.DEV || env.VITE_ACCOUNTS_OPEN?.trim() === "true");
}

// Vite folds DEV to false in production, so the localhost URL never ships.
export const API_BASE_URL = resolveApiBase(
  import.meta.env,
  import.meta.env.DEV ? "http://localhost:8000/api" : null,
);
export const ACCOUNTS_OPEN = accountsOpen(import.meta.env, API_BASE_URL);
