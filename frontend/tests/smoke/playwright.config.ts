/**
 * Live smoke: read-only checks against a deployed host after `wrangler deploy`.
 * No dev server, no sign-in, no writes.
 *
 *   SMOKE_BASE_URL  the frontend, e.g. https://staging.patch-hive.com (default)
 *   SMOKE_API_URL   its API origin; derived for the two known hosts when unset
 */
import { defineConfig } from "@playwright/test";

const baseURL = (process.env.SMOKE_BASE_URL || "https://staging.patch-hive.com").replace(
  /\/+$/,
  "",
);

export default defineConfig({
  testDir: "./",
  timeout: 60_000,
  expect: { timeout: 20_000 },
  // A container that slept answers its first request slowly; one retry absorbs that.
  retries: 1,
  workers: 2,
  reporter: [["line"]],
  use: {
    baseURL,
    trace: "retain-on-failure",
  },
});
