/**
 * Read-only smoke of a deployed PatchHive: the API is healthy on the release this frontend
 * was built from, every page carries its security headers, deep links serve the app, and the
 * public pages render live data with no alerts and no console or CSP errors.
 */
import { readFileSync } from "node:fs";
import { expect, test, type Page } from "@playwright/test";

const BASE = (process.env.SMOKE_BASE_URL || "https://staging.patch-hive.com").replace(/\/+$/, "");

/** The API origin that serves this frontend. */
function apiOrigin(): string {
  if (process.env.SMOKE_API_URL) return process.env.SMOKE_API_URL.replace(/\/+$/, "");
  const host = new URL(BASE).hostname;
  if (host === "staging.patch-hive.com") return "https://api-staging.patch-hive.com";
  if (host === "patch-hive.com" || host === "www.patch-hive.com")
    return "https://api.patch-hive.com";
  throw new Error(`Set SMOKE_API_URL for ${host}`);
}

const API = apiOrigin();
const IS_STAGING = new URL(BASE).hostname.startsWith("staging.");
const RELEASE = JSON.parse(readFileSync(new URL("../../package.json", import.meta.url), "utf8"))
  .version as string;

/**
 * A signed-out visitor's session probe answers 401 by design, and the not-found page is
 * served with 404; any other failed response is a fault.
 */
function expectedFailure(status: number, method: string, url: string): boolean {
  if (status === 401 && method === "POST" && url.endsWith("/api/community/auth/refresh")) {
    return true;
  }
  return status === 404 && url.includes("/no-such-page-smoke");
}

/**
 * What went wrong while a page loaded: uncaught exceptions, console errors (a CSP violation
 * is one) and failed responses. The browser's own "Failed to load resource" line repeats a
 * failed response, so responses are checked by URL instead.
 */
function watchErrors(page: Page): string[] {
  const errors: string[] = [];
  page.on("console", (msg) => {
    if (msg.type() === "error" && !msg.text().startsWith("Failed to load resource")) {
      errors.push(msg.text());
    }
  });
  page.on("pageerror", (err) => errors.push(err.message));
  page.on("response", (res) => {
    const method = res.request().method();
    if (res.status() >= 400 && !expectedFailure(res.status(), method, res.url())) {
      errors.push(`${res.status()} ${method} ${res.url()}`);
    }
  });
  return errors;
}

test("the API is healthy, on the release this frontend was built from", async ({ request }) => {
  const res = await request.get(`${API}/health/ready`, { timeout: 60_000 });
  expect(res.status()).toBe(200);
  const body = await res.json();
  expect(body).toMatchObject({ status: "healthy", database: "ok", version: RELEASE });
});

test("pages carry their security headers", async ({ request }) => {
  const res = await request.get(`${BASE}/`);
  expect(res.status()).toBe(200);
  const headers = res.headers();
  expect(headers["content-security-policy"]).toContain("default-src 'self'");
  expect(headers["strict-transport-security"]).toContain("max-age=");
  expect(headers["x-content-type-options"]).toBe("nosniff");
  expect(headers["referrer-policy"]).toBeTruthy();
  // Staging must stay out of search results; production must not.
  if (IS_STAGING) expect(headers["x-robots-tag"]).toContain("noindex");
  else expect(headers["x-robots-tag"]).toBeUndefined();
});

test("deep links serve the app and unknown paths answer 404", async ({ request }) => {
  for (const path of [
    "/modules",
    "/cases",
    "/products",
    "/patches",
    "/racks",
    "/login",
    "/admin/leaderboards",
  ]) {
    const res = await request.get(`${BASE}${path}`);
    expect(res.status(), path).toBe(200);
    expect(await res.text(), path).toContain('id="root"');
  }
  const missing = await request.get(`${BASE}/no-such-page-smoke`);
  expect(missing.status()).toBe(404);
  expect(await missing.text()).toContain('id="root"');
});

const PAGES: { path: string; check: (page: Page) => Promise<void> }[] = [
  {
    path: "/",
    check: async (page) => {
      await expect(page.locator(".home-rig .patch-cable").first()).toBeVisible();
    },
  },
  {
    path: "/modules",
    check: async (page) => {
      await expect(page.locator(".results-meta").first()).toHaveText(
        /Showing \d+ of [1-9]\d* catalog modules/,
      );
    },
  },
  {
    path: "/products",
    check: async (page) => {
      await expect(page.locator(".side-item").first()).toBeVisible();
    },
  },
  {
    path: "/cases",
    check: async (page) => {
      await expect(page.locator(".results-meta").first()).toHaveText(
        /Showing \d+ of [1-9]\d* catalog cases/,
      );
    },
  },
  {
    path: "/login",
    check: async (page) => {
      await expect(page.getByRole("tab", { name: "Sign in" })).toBeVisible();
    },
  },
  {
    path: "/no-such-page-smoke",
    check: async (page) => {
      await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    },
  },
];

for (const { path, check } of PAGES) {
  test(`${path} renders live data without errors`, async ({ page }) => {
    const errors = watchErrors(page);
    await page.goto(path);
    await expect(page.locator("main")).toBeVisible();
    await check(page);
    await expect(page.locator(".skeleton")).toHaveCount(0);
    await expect(page.getByRole("alert")).toHaveCount(0);
    expect(errors, "console errors").toEqual([]);
  });
}
