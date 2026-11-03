/**
 * Design guard: every screen, in both themes, on a desktop and a phone, must pass axe (colour
 * contrast included), keep every element inside the viewport, and keep its signature drawing.
 * No backend: the API is mocked here, and anything not mocked answers 404, so a screen is
 * checked in its loaded, empty or error state.
 */
import { createRequire } from "node:module";
import { expect, test, type Page } from "@playwright/test";

const axePath = createRequire(import.meta.url).resolve("axe-core/axe.min.js");

const STAMP = "2026-01-01T00:00:00Z";
const ADMIN = {
  id: 1,
  username: "design_admin",
  email: "design_admin@example.test",
  role: "Admin",
  created_at: STAMP,
  updated_at: STAMP,
};

const placed = (id: number, moduleId: number, startHp: number, name: string, hp: number) => ({
  id,
  module_id: moduleId,
  row_index: 0,
  start_hp: startHp,
  module: {
    id: moduleId,
    brand: "Sim Co",
    name,
    hp,
    module_type: "VCO",
    power_12v_ma: 40,
    power_neg12v_ma: 10,
    power_5v_ma: 0,
  },
});

const RIG_SUMMARY = {
  rig_id: 1,
  rack_id: 1,
  user_id: 1,
  case_id: 1,
  name: "Bench rig",
  name_suggested: null,
  description: "A small rig for the design guard",
  tags: [],
  is_public: false,
  module_count: 3,
  created_at: STAMP,
  updated_at: STAMP,
};

const RIG_DETAIL = {
  ...RIG_SUMMARY,
  generation_seed: 1,
  vote_count: 0,
  modules: [
    placed(101, 11, 0, "Oscillator", 12),
    placed(102, 12, 14, "Filter", 10),
    placed(103, 13, 30, "Envelope", 8),
  ],
  case: { id: 1, brand: "Sim Co", name: "Sim 84", total_hp: 84, rows: 1, hp_per_row: [84] },
};

const RUN = {
  id: 11,
  rack_id: 1,
  status: "succeeded",
  created_at: STAMP,
  rig_revision_id: "rig-rev-" + "a".repeat(32),
  source_run_id: "gen-run-11-" + "a".repeat(16),
  artifact_manifest_hash: "a".repeat(64),
  export_bridge_ready: true,
};

const cable = (from: number, to: number, type: string) => ({
  from_module_id: from,
  from_port: "Out",
  to_module_id: to,
  to_port: "In",
  cable_type: type,
});

const PATCH = {
  id: 501,
  rack_id: 1,
  run_id: 11,
  name: "Slow drift",
  suggested_name: "Slow drift",
  category: "Voice",
  description: "A filtered voice with a slow envelope",
  connections: [cable(11, 12, "audio"), cable(13, 12, "cv"), cable(13, 11, "gate")],
  generation_seed: 1,
  generation_version: "test",
  is_public: false,
  vote_count: 0,
  created_at: STAMP,
  updated_at: STAMP,
};

const CASE_DETAIL = {
  slug: "sim-co-sim-84",
  manufacturer: "Sim Co",
  model: "Sim 84",
  format_family: "eurorack",
  production_status: "current",
  powered: true,
  revisions: [
    {
      revision_key: "default",
      row_count: 1,
      capacity_value: 84,
      capacity_unit: "hp",
      depth_min_mm: 60,
      depth_max_mm: 60,
      confidence: "observed",
      rows: [{ row_index: 0, format_family: "eurorack", capacity_value: 84, capacity_unit: "hp" }],
      power_systems: [],
      features: [],
    },
  ],
  sources: [],
  prices: [],
};

/** One module per category band: a source (amber), a shaper (cyan) and a controller (grey). */
const CATALOG_MODULES = [
  {
    id: 1,
    slug: "sim-co-oscillator",
    brand: "Sim Co",
    name: "Oscillator",
    hp: 12,
    category: "VCO",
  },
  { id: 2, slug: "sim-co-filter", brand: "Sim Co", name: "Filter", hp: 8, category: "VCF" },
  { id: 3, slug: "sim-co-mixer", brand: "Sim Co", name: "Mixer", hp: 6, category: "MIX" },
].map((m) => ({ ...m, is_available: "available" }));

const json = (body: unknown) => ({ json: body });

/** Mock the API. Routes run newest first, so the 404 catch-all is registered first. */
async function mockApi(page: Page, { signedIn }: { signedIn: boolean }) {
  await page.route("**/api/**", (route) =>
    route.fulfill({ status: 404, json: { detail: "not mocked" } }),
  );
  if (signedIn) {
    await page.route("**/api/community/auth/refresh", (route) =>
      route.fulfill(json({ access_token: "design-token", token_type: "bearer", user: ADMIN })),
    );
    await page.route("**/api/community/users/me", (route) => route.fulfill(json(ADMIN)));
  }
  await page.route(
    (url) => url.pathname.endsWith("/api/canon/rigs"),
    (route) => route.fulfill(json({ total: 1, rigs: [RIG_SUMMARY] })),
  );
  await page.route("**/api/canon/rigs/1", (route) => route.fulfill(json(RIG_DETAIL)));
  await page.route("**/api/canon/rigs/1/revisions", (route) =>
    route.fulfill(
      json({
        total: 1,
        revisions: [
          {
            rig_revision_id: RUN.rig_revision_id,
            run_count: 1,
            latest_run_id: RUN.id,
            latest_run_at: STAMP,
            export_bridge_ready: true,
          },
        ],
      }),
    ),
  );
  await page.route(
    (url) => url.pathname.endsWith("/api/canon/runs"),
    (route) => route.fulfill(json({ total: 1, runs: [RUN] })),
  );
  await page.route("**/api/runs/11/patches**", (route) =>
    route.fulfill(json({ total: 1, created_at: STAMP, patches: [PATCH] })),
  );
  await page.route("**/api/modules/catalog**", (route) => {
    const path = new URL(route.request().url()).pathname.replace(/\/+$/, "");
    if (path.endsWith("/catalog/stats")) {
      return route.fulfill(
        json({
          total_modules: 3,
          total_brands: 1,
          total_categories: 3,
          hp_stats: { average: 9, min: 6, max: 12, known: 3, unknown: 0, coverage_pct: 100 },
          availability: { available: 3, discontinued: 0 },
        }),
      );
    }
    if (path.endsWith("/catalog/brands")) {
      return route.fulfill(json({ total: 1, brands: [{ name: "Sim Co", module_count: 3 }] }));
    }
    if (path.endsWith("/catalog/categories")) {
      return route.fulfill(
        json({
          total: 3,
          categories: ["VCO", "VCF", "MIX"].map((name) => ({ name, module_count: 1 })),
        }),
      );
    }
    return route.fulfill(json({ total: 3, skip: 0, limit: 48, modules: CATALOG_MODULES }));
  });
  await page.route("**/api/canon/credits/balance", (route) => route.fulfill(json({ balance: 3 })));
  await page.route("**/api/canon/credits/summary", (route) =>
    route.fulfill(json({ balance: 3, entries: [] })),
  );
  await page.route("**/api/canon/exports", (route) => route.fulfill(json([])));
  await page.route(
    (url) => url.pathname.endsWith("/api/cases/catalog"),
    (route) =>
      route.fulfill(
        json({
          total: 1,
          skip: 0,
          limit: 200,
          cases: [
            {
              slug: CASE_DETAIL.slug,
              manufacturer: CASE_DETAIL.manufacturer,
              model: CASE_DETAIL.model,
              format_family: "eurorack",
              production_status: "current",
              powered: true,
              primary_revision: {
                revision_key: "default",
                capacity_value: 84,
                capacity_unit: "hp",
                row_count: 1,
                confidence: "observed",
              },
            },
          ],
        }),
      ),
  );
  await page.route(`**/api/cases/catalog/${CASE_DETAIL.slug}`, (route) =>
    route.fulfill(json(CASE_DETAIL)),
  );
}

interface Screen {
  path: string;
  name: string;
  signedIn: boolean;
  /** A selector the screen must draw once loaded. */
  signature?: string;
  /** Steps after arriving, such as opening a tab. */
  open?: (page: Page) => Promise<void>;
}

const SCREENS: Screen[] = [
  { path: "/", name: "home", signedIn: false, signature: ".home-rig .patch-cable" },
  { path: "/login", name: "sign in", signedIn: false },
  { path: "/no-such-route", name: "not found", signedIn: false, signature: ".broken-patch" },
  { path: "/modules", name: "modules", signedIn: true, signature: ".module-mockup" },
  { path: "/cases", name: "cases", signedIn: true },
  {
    path: `/cases/${CASE_DETAIL.slug}`,
    name: "case detail",
    signedIn: true,
    signature: ".capacity-rail",
  },
  { path: "/products", name: "products", signedIn: true },
  { path: "/patches", name: "patches", signedIn: true },
  { path: "/account", name: "account", signedIn: true },
  { path: "/admin", name: "ops", signedIn: true },
  { path: "/admin/users", name: "ops users", signedIn: true },
  { path: "/rigs/1", name: "rig detail", signedIn: true, signature: ".signal-chain" },
  { path: "/rigs/1/patchbook-studio", name: "style studio", signedIn: true },
  {
    path: "/racks",
    name: "rigs, patches tab",
    signedIn: true,
    signature: ".patch-rail .patch-cable",
    open: async (page) => {
      await page.getByRole("tab", { name: "Patches" }).click();
    },
  },
];

/** Signed-in screens are reached in-app after the session restores, as a person would. */
async function arrive(page: Page, screen: Screen) {
  if (!screen.signedIn) {
    await page.goto(screen.path);
    return;
  }
  await page.goto("/");
  await expect(page.getByRole("button", { name: /Sign out/ })).toBeVisible();
  await page.evaluate((path) => {
    window.history.pushState({}, "", path);
    window.dispatchEvent(new PopStateEvent("popstate"));
  }, screen.path);
}

/** Elements past the viewport's right edge, outside any container that scrolls or clips them. */
function overflowing(page: Page) {
  return page.evaluate(() => {
    const vw = document.documentElement.clientWidth;
    const clips = (el: Element | null): boolean => {
      for (
        let node = el?.parentElement;
        node && node !== document.body;
        node = node.parentElement
      ) {
        if (["auto", "scroll", "hidden", "clip"].includes(getComputedStyle(node).overflowX)) {
          return true;
        }
      }
      return false;
    };
    return Array.from(document.body.querySelectorAll("*"))
      .filter((el) => {
        const r = el.getBoundingClientRect();
        return r.width > 1 && r.right > vw + 1 && !clips(el);
      })
      .slice(0, 5)
      .map(
        (el) => `${el.tagName.toLowerCase()}.${String(el.className).trim().split(/\s+/).join(".")}`,
      );
  });
}

interface AxeNode {
  target: string[];
  any: { message: string }[];
}

/** Each violation as "rule: element (why)", so a CI log names the colours and ratio. */
async function axeViolations(page: Page) {
  await page.addScriptTag({ path: axePath });
  return page.evaluate(async () => {
    const { axe } = window as unknown as {
      axe: {
        run: (
          context: Document,
          options: object,
        ) => Promise<{ violations: { id: string; nodes: AxeNode[] }[] }>;
      };
    };
    const result = await axe.run(document, { resultTypes: ["violations"] });
    return result.violations.flatMap((v) =>
      v.nodes
        .slice(0, 3)
        .map((n) => `${v.id}: ${n.target.join(" ")} (${n.any[0]?.message ?? "see axe"})`),
    );
  });
}

for (const theme of ["dark", "light"] as const) {
  for (const viewport of [
    { width: 1440, height: 900 },
    { width: 375, height: 812 },
  ]) {
    test.describe(`design guard, ${theme}, ${viewport.width}`, () => {
      test.use({ viewport });

      for (const screen of SCREENS) {
        test(screen.name, async ({ page }) => {
          await page.emulateMedia({ reducedMotion: "reduce" });
          await page.addInitScript((value) => {
            window.localStorage.setItem("patchhive-theme", value);
          }, theme);
          await mockApi(page, { signedIn: screen.signedIn });
          await arrive(page, screen);
          await screen.open?.(page);
          await expect(page.locator("main")).toBeVisible();
          await expect(page.locator(".skeleton")).toHaveCount(0);
          await expect(page.locator("html")).toHaveAttribute("data-theme", theme);
          if (screen.signature) {
            await expect(page.locator(screen.signature).first()).toBeVisible();
          }

          expect(await overflowing(page), "elements past the viewport").toEqual([]);
          expect(await axeViolations(page), "axe violations").toEqual([]);
        });
      }
    });
  }
}

test.describe("theme memory", () => {
  test("a remembered light theme applies before the app loads", async ({ page }) => {
    await page.addInitScript(() => window.localStorage.setItem("patchhive-theme", "light"));
    await mockApi(page, { signedIn: false });
    // Without the app bundle, only public/theme-init.js can set the theme.
    await page.route("**/src/main.tsx", (route) => route.abort());
    await page.goto("/");
    await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
    await expect(page.locator('meta[name="theme-color"]')).toHaveAttribute("content", "#e9ebef");
  });

  test("the toggle sets the theme everywhere and survives a reload", async ({ page }) => {
    await mockApi(page, { signedIn: false });
    await page.goto("/");
    const html = page.locator("html");
    const themeColor = page.locator('meta[name="theme-color"]');
    await expect(html).toHaveAttribute("data-theme", "dark");

    await page.getByRole("button", { name: "Use light theme" }).click();
    await expect(html).toHaveAttribute("data-theme", "light");
    await expect(page.locator(".app-shell")).toHaveAttribute("data-theme", "light");
    await expect(themeColor).toHaveAttribute("content", "#e9ebef");
    expect(await page.evaluate(() => window.localStorage.getItem("patchhive-theme"))).toBe("light");

    await page.reload();
    await expect(html).toHaveAttribute("data-theme", "light");
    await page.getByRole("button", { name: "Use dark theme" }).click();
    await expect(html).toHaveAttribute("data-theme", "dark");
    await expect(themeColor).toHaveAttribute("content", "#08090b");
  });
});
