// Response headers the edge adds to every page.
//
// The Content-Security-Policy ships in report-only mode first: browsers log what it would
// block without blocking anything. Promote it to `Content-Security-Policy` once the
// console stays clean on both hosts.

// The API each frontend host talks to (frontend/.env.production, .env.staging).
const API_ORIGINS: Record<string, string> = {
  "patch-hive.com": "https://api.patch-hive.com",
  "staging.patch-hive.com": "https://api-staging.patch-hive.com",
};

export function contentSecurityPolicy(hostname: string): string {
  const api = API_ORIGINS[hostname] ?? "";
  return [
    "default-src 'self'",
    "script-src 'self'",
    // Inline style attributes are used by React components; fonts come from Google.
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
    "font-src 'self' https://fonts.gstatic.com",
    "img-src 'self' data: blob: https:",
    `connect-src 'self'${api ? ` ${api}` : ""}`,
    "frame-ancestors 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "object-src 'none'",
  ].join("; ");
}

export function securityHeaders(hostname: string): Record<string, string> {
  return {
    "Content-Security-Policy-Report-Only": contentSecurityPolicy(hostname),
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "strict-origin-when-cross-origin",
  };
}
