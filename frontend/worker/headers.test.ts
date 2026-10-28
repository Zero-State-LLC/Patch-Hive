import { describe, expect, it } from "vitest";
import { contentSecurityPolicy, securityHeaders } from "./headers";

describe("security headers", () => {
  it("lets each frontend reach only its own API", () => {
    expect(contentSecurityPolicy("patch-hive.com")).toContain(
      "connect-src 'self' https://api.patch-hive.com https://cloudflareinsights.com;",
    );
    expect(contentSecurityPolicy("staging.patch-hive.com")).toContain(
      "connect-src 'self' https://api-staging.patch-hive.com https://cloudflareinsights.com;",
    );
    expect(contentSecurityPolicy("unknown.example")).toContain(
      "connect-src 'self' https://cloudflareinsights.com;",
    );
  });

  it("forbids framing, plugins and inline script", () => {
    const csp = contentSecurityPolicy("patch-hive.com");
    expect(csp).toContain("frame-ancestors 'none'");
    expect(csp).toContain("object-src 'none'");
    // Only same-origin scripts and Cloudflare's analytics beacon; never 'unsafe-inline'.
    expect(csp).toContain("script-src 'self' https://static.cloudflareinsights.com;");
    expect(csp).not.toMatch(/script-src[^;]*unsafe-inline/);
  });

  it("enforces the policy", () => {
    const headers = securityHeaders("patch-hive.com");
    expect(headers["Content-Security-Policy"]).toBe(contentSecurityPolicy("patch-hive.com"));
    expect(headers).not.toHaveProperty("Content-Security-Policy-Report-Only");
    expect(headers["X-Content-Type-Options"]).toBe("nosniff");
  });
});
