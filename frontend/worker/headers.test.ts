import { describe, expect, it } from "vitest";
import { contentSecurityPolicy, securityHeaders } from "./headers";

describe("security headers", () => {
  it("lets each frontend reach only its own API", () => {
    expect(contentSecurityPolicy("patch-hive.com")).toContain("connect-src 'self' https://api.patch-hive.com;");
    expect(contentSecurityPolicy("staging.patch-hive.com")).toContain(
      "connect-src 'self' https://api-staging.patch-hive.com;",
    );
    expect(contentSecurityPolicy("unknown.example")).toContain("connect-src 'self';");
  });

  it("forbids framing, plugins and inline script", () => {
    const csp = contentSecurityPolicy("patch-hive.com");
    expect(csp).toContain("frame-ancestors 'none'");
    expect(csp).toContain("object-src 'none'");
    expect(csp).toContain("script-src 'self';");
  });

  it("ships the policy in report-only mode first", () => {
    const headers = securityHeaders("patch-hive.com");
    expect(headers["Content-Security-Policy-Report-Only"]).toBeTruthy();
    expect(headers).not.toHaveProperty("Content-Security-Policy");
    expect(headers["X-Content-Type-Options"]).toBe("nosniff");
  });
});
