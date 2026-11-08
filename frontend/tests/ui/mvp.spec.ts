import { expect, test, type Page } from "@playwright/test";

/** The app restores a session through the refresh endpoint, so a signed-in page mocks it. */
async function signIn(page: Page, role = "User") {
  await page.route("**/api/community/auth/refresh", async (route) => {
    await route.fulfill({
      json: {
        access_token: "e2e-token",
        token_type: "bearer",
        user: {
          id: 1,
          username: "e2e-user",
          email: "e2e-user@example.com",
          role,
          created_at: "2026-01-01T00:00:00Z",
          updated_at: "2026-01-01T00:00:00Z",
        },
      },
    });
  });
}

/** Rig 7 as the builder reads it: its canon detail (F5) and the legacy rack routes it writes. */
const RIG_7 = (url: URL) => /\/api\/(racks|canon\/rigs)\/7(\/|$)/.test(url.pathname);

test.describe("PatchHive canonical workspace", () => {
  test.beforeEach(async ({ page }) => {
    // Slice B: run list is served from /api/canon/runs?rig_id=
    await page.route("**/api/canon/runs**", async (route) => {
      const url = route.request().url();
      // Do not intercept revision/export subpaths that also contain "runs" substrings incorrectly.
      if (url.includes("/rigs/")) {
        return route.fallback();
      }
      const rigId = new URL(url).searchParams.get("rig_id");
      const runs =
        rigId === "99999"
          ? []
          : [
              {
                id: 11,
                rack_id: 1,
                status: "succeeded",
                created_at: "2025-01-01T00:00:00Z",
                rig_revision_id: "rig-rev-" + "a".repeat(32),
                source_run_id: "gen-run-11-" + "a".repeat(16),
                artifact_manifest_hash: "a".repeat(64),
                export_bridge_ready: true,
              },
              {
                id: 12,
                rack_id: 1,
                status: "succeeded",
                created_at: "2025-02-01T00:00:00Z",
                rig_revision_id: "rig-rev-" + "b".repeat(32),
                source_run_id: "gen-run-12-" + "b".repeat(16),
                artifact_manifest_hash: "b".repeat(64),
                export_bridge_ready: true,
              },
            ];
      await route.fulfill({ json: { total: runs.length, runs } });
    });
    // Revision picker (groups runs by bridge rig_revision_id)
    await page.route("**/api/canon/rigs/*/revisions**", async (route) => {
      const url = route.request().url();
      if (url.includes("/rigs/99999/")) {
        await route.fulfill({ json: { total: 0, revisions: [] } });
        return;
      }
      await route.fulfill({
        json: {
          total: 2,
          revisions: [
            {
              rig_revision_id: "rig-rev-" + "b".repeat(32),
              run_count: 1,
              latest_run_id: 12,
              latest_run_at: "2025-02-01T00:00:00Z",
              export_bridge_ready: true,
            },
            {
              rig_revision_id: "rig-rev-" + "a".repeat(32),
              run_count: 1,
              latest_run_id: 11,
              latest_run_at: "2025-01-01T00:00:00Z",
              export_bridge_ready: true,
            },
          ],
        },
      });
    });
    await page.route("**/api/runs/*/patches**", (route) =>
      route.fulfill({ json: { total: 0, patches: [] } }),
    );
    // P1: credits read the canonical ledger, not legacy monetization.
    await page.route("**/api/canon/credits/balance", (route) =>
      route.fulfill({ json: { balance: 0 } }),
    );
    await page.route("**/api/monetization/credits/balance", (route) =>
      route.fulfill({ status: 410, json: { detail: "use /api/canon/credits/balance" } }),
    );
  });

  test("shows only contextual tabs and defaults to the latest run", async ({ page }) => {
    await page.goto("/rigs/99999");
    await expect(page.getByRole("tab", { name: "Overview" })).toBeVisible();
    await expect(page.getByRole("tab", { name: "Module gallery" })).toBeVisible();
    await expect(page.getByRole("tab", { name: "Patches" })).toHaveCount(0);
    await expect(page.getByRole("tab", { name: "Exports" })).toHaveCount(0);

    await page.goto("/rigs/1");
    await expect(page.getByRole("tab", { name: "Patches" })).toBeVisible();
    await expect(page.getByRole("tab", { name: "Exports" })).toBeVisible();
    await expect(page.getByLabel("Source run (within revision)")).toHaveValue("12");
    await expect(page.getByLabel("Rig revision")).toBeVisible();
  });

  test("keeps historical social features out of active navigation", async ({ page }) => {
    await page.goto("/");
    const navigation = page.getByRole("navigation", { name: "Primary navigation" });
    await expect(navigation.getByRole("link", { name: "My Rigs" })).toBeVisible();
    await expect(navigation.getByText("Feed")).toHaveCount(0);
    await expect(navigation.getByText("Publish")).toHaveCount(0);
    await expect(navigation.getByText("Leaderboards")).toHaveCount(0);
  });

  test("export boundary explains zero-credit state", async ({ page }) => {
    // A balance is an account's, so the zero-credit state is a signed-in one.
    await signIn(page);
    await page.goto("/rigs/1");
    await page.getByRole("tab", { name: "Exports" }).click();
    await expect(page.getByRole("button", { name: "Export PDF patch book" })).toBeDisabled();
    await expect(page.getByText("Credits are required only for exports.")).toBeVisible();
    await expect(page.getByText(/Each export is a patch book of this run/)).toBeVisible();
  });

  const allowance = (exports_used: number, export_cap: number) => ({
    test_mode: true,
    credit_offer: null,
    plan_offers: [],
    subscription: null,
    allowance: { exports_used, export_cap, period_end: "2030-03-15T00:00:00Z" },
  });

  test("a period allowance pays for an export with no credits", async ({ page }) => {
    await signIn(page);
    await page.route("**/api/canon/commerce", (route) =>
      route.fulfill({ json: allowance(12, 100) }),
    );
    await page.route("**/api/canon/exports", (route) =>
      route.request().method() === "POST"
        ? route.fulfill({
            status: 201,
            json: { export_id: "export-allowance-1", status: "queued", credit_cost: 0 },
          })
        : route.fallback(),
    );
    await page.goto("/rigs/1");
    await page.getByRole("tab", { name: "Exports" }).click();

    await expect(page.getByText("Exports this period")).toBeVisible();
    await expect(page.getByText("12 of 100", { exact: true })).toBeVisible();
    await expect(page.getByText("Credits are required only for exports.")).toHaveCount(0);
    const exportButton = page.getByRole("button", { name: "Export PDF patch book" });
    await expect(exportButton).toBeEnabled();

    await exportButton.click();
    await expect(page.getByText(/counts toward this period's exports/)).toBeVisible();
  });

  test("a used-up allowance says when it resets, and the API's refusal reads in words", async ({
    page,
  }) => {
    await signIn(page);
    let allowanceRead = allowance(99, 100);
    await page.route("**/api/canon/commerce", (route) => route.fulfill({ json: allowanceRead }));
    await page.route("**/api/canon/exports", (route) =>
      route.request().method() === "POST"
        ? route.fulfill({ status: 429, json: { detail: "FAIR_USE_CAP_REACHED" } })
        : route.fallback(),
    );
    await page.goto("/rigs/1");
    await page.getByRole("tab", { name: "Exports" }).click();
    const exportButton = page.getByRole("button", { name: "Export PDF patch book" });
    await expect(exportButton).toBeEnabled();

    // The page read 99 of 100, and another tab took the last one.
    await exportButton.click();
    await expect(
      page.getByText(/used this period's exports, so nothing was charged/),
    ).toBeVisible();

    allowanceRead = allowance(100, 100);
    await page.reload();
    await page.getByRole("tab", { name: "Exports" }).click();
    await expect(exportButton).toBeDisabled();
    await expect(page.getByText(/They reset on/)).toBeVisible();
  });

  test("export boundary asks a signed-out visitor to sign in, not to buy credits", async ({
    page,
  }) => {
    await page.goto("/rigs/1");
    await page.getByRole("tab", { name: "Exports" }).click();
    await expect(page.getByRole("button", { name: "Export PDF patch book" })).toBeDisabled();
    await expect(page.getByText("Sign in to export. Only exports cost credits.")).toBeVisible();
    await expect(page.getByText("Available credits")).toHaveCount(0);
  });

  test("rack builder edit shows dual-gate panel and power completeness", async ({ page }) => {
    await page.route(RIG_7, async (route) => {
      const url = route.request().url();
      if (url.includes("/compatibility")) {
        await route.fulfill({
          json: {
            bridge_status: "ok",
            message: "Catalog compatibility evaluated",
            catalog_slug: "sim-co-sim-84",
            case_id: 10,
            module_count: 2,
            compatibility: {
              case_slug: "sim-co-sim-84",
              manufacturer: "Sim Co",
              model: "Sim 84",
              format_family: "eurorack",
              revision_key: "sim",
              overall_status: "incomplete",
              format_check: {
                status: "verified",
                code: "FORMAT_OK",
                message: "ok",
              },
              physical_fit: {
                status: "verified",
                code: "PHYSICAL_FIT_OK",
                message: "ok",
              },
              remaining_capacity: [],
              power_headroom: [
                {
                  rail: "+12V",
                  case_capacity_ma: 2000,
                  module_draw_ma: 100,
                  headroom_ma: 1900,
                  status: "verified",
                  message: "+12V: 1900mA headroom",
                },
              ],
              connector_availability: {
                status: "verified",
                code: "CONNECTORS_OK",
                message: "2/8 connectors",
              },
              pos5_compatibility: {
                status: "verified",
                code: "POS5_OK",
                message: "ok",
              },
              lid_close: {
                status: "verified",
                code: "LID_OK",
                message: "ok",
              },
              warnings: [
                {
                  status: "incomplete",
                  code: "MODULE_POWER_UNKNOWN",
                  message: "One or more modules lack power specs",
                },
              ],
              notes: [],
            },
          },
        });
        return;
      }
      if (
        route.request().method() === "GET" &&
        /\/api\/(racks|canon\/rigs)\/7\/?$/.test(new URL(url).pathname)
      ) {
        await route.fulfill({
          json: {
            id: 7,
            name: "Sim rack",
            case_id: 10,
            user_id: 1,
            generation_seed: 1,
            modules: [
              {
                module_id: 1,
                row_index: 0,
                start_hp: 0,
                module: {
                  id: 1,
                  brand: "Sim",
                  name: "Alpha",
                  hp: 10,
                  module_type: "VCO",
                  power_12v_ma: 40,
                  power_neg12v_ma: 20,
                  power_5v_ma: 0,
                },
              },
              {
                module_id: 2,
                row_index: 0,
                start_hp: 10,
                module: {
                  id: 2,
                  brand: "Sim",
                  name: "Beta",
                  hp: 8,
                  module_type: "VCF",
                  power_12v_ma: null,
                  power_neg12v_ma: null,
                },
              },
            ],
            case: {
              id: 10,
              brand: "Sim Co",
              name: "Sim 84",
              total_hp: 84,
              rows: 1,
              hp_per_row: [84],
              catalog_slug: "sim-co-sim-84",
              power_12v_ma: 2000,
              power_neg12v_ma: 1200,
              power_5v_ma: 500,
            },
            validation_warnings: [
              {
                field: "power",
                message:
                  "Any power supplied by the in-rack SYSTEM module Sim Supply isn't counted. This Rig's power budget is only what its Case supplies.",
                details: { code: "IN_RACK_SUPPLY_NOT_COUNTED" },
              },
            ],
          },
        });
        return;
      }
      await route.continue();
    });
    await page.route("**/api/modules/**", async (route) => {
      const path = new URL(route.request().url()).pathname;
      if (path.includes("materialize-batch")) {
        await route.fulfill({
          json: { status: "success", scanned: 3, created: 0, exists: 3, failed: 0 },
        });
        return;
      }
      await route.fulfill({
        json: {
          total: 2,
          modules: [
            {
              id: 1,
              brand: "Sim",
              name: "Alpha",
              hp: 10,
              module_type: "VCO",
              power_12v_ma: 40,
              power_neg12v_ma: 20,
              power_5v_ma: 0,
              source: "ModuleCatalog",
              io_ports: [],
              tags: [],
              imported_at: "2026-01-01",
              created_at: "2026-01-01",
              updated_at: "2026-01-01",
            },
            {
              id: 2,
              brand: "Sim",
              name: "Beta",
              hp: 8,
              module_type: "VCF",
              power_12v_ma: null,
              source: "ModuleCatalog",
              io_ports: [],
              tags: [],
              imported_at: "2026-01-01",
              created_at: "2026-01-01",
              updated_at: "2026-01-01",
            },
          ],
        },
      });
    });

    // Bulk materialize is shown to Admin and Ops only.
    await signIn(page, "Admin");
    await page.goto("/racks/7/edit");
    await expect(page.getByRole("heading", { name: "Module placement" })).toBeVisible({
      timeout: 15000,
    });
    await expect(page.getByText(/Sim Supply isn't counted/)).toBeVisible();
    await expect(page.getByLabel("Builder steps")).toBeVisible();
    await expect(page.getByText("Place modules").first()).toBeVisible();
    await expect(page.getByLabel("Row HP usage")).toBeVisible();
    await expect(page.getByText(/18\/84HP used/i)).toBeVisible();
    await expect(page.getByLabel(/Row 0 layout/i)).toBeVisible();
    await expect(page.getByTitle(/Alpha.*HP 0 to 9/i)).toBeVisible();
    await expect(page.getByTitle(/Beta.*power unknown/i)).toBeVisible();
    await expect(page.getByText(/Placement power/i)).toBeVisible();
    await expect(page.getByText(/Placement power: 1 of 2 modules state every rail/i)).toBeVisible();
    await expect(page.getByLabel("Power rail usage")).toBeVisible();
    await expect(page.getByLabel("+12V power usage")).toBeVisible();
    // Beta states no rail, so all three meters report 1 unknown; check the +12V row.
    const plus12Row = page
      .locator(".power-rail-meters__row")
      .filter({ has: page.getByLabel("+12V power usage") });
    await expect(plus12Row.getByText(/1 unknown/i)).toBeVisible();
    // Alpha: +12 40 / case 2000 · Beta power unknown not assumed
    await expect(page.getByText(/40\/2000mA/i).first()).toBeVisible();
    await expect(page.getByText(/Unknown draw, not assumed/i)).toBeVisible();
    await expect(page.getByRole("heading", { name: "Dual-gate compatibility" })).toBeVisible();
    await expect(page.getByLabel("Dual-gate summary")).toBeVisible();
    await expect(
      page.getByLabel("Dual-gate summary").getByText("overall: incomplete", { exact: true }),
    ).toBeVisible();
    await expect(page.getByText(/\+12V/).first()).toBeVisible();
    await expect(page.getByText(/Soft warnings/i)).toBeVisible();
    await expect(page.getByText(/MODULE_POWER_UNKNOWN/)).toBeVisible();
    await expect(page.getByRole("button", { name: "Materialize HP-known modules" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Batch place" })).toBeVisible();
    await expect(page.getByLabel("Batch module selection")).toBeVisible();
  });

  test("rack builder batch place packs selected modules in one save", async ({ page }) => {
    let putBody: { modules?: { module_id: number; row_index: number; start_hp: number }[] } | null =
      null;
    await page.route(RIG_7, async (route) => {
      const url = route.request().url();
      if (url.includes("/compatibility")) {
        await route.fulfill({
          json: {
            bridge_status: "ok",
            message: "ok",
            catalog_slug: "sim-co-sim-84",
            case_id: 10,
            module_count: 0,
            compatibility: {
              case_slug: "sim-co-sim-84",
              manufacturer: "Sim Co",
              model: "Sim 84",
              format_family: "eurorack",
              revision_key: "sim",
              overall_status: "verified",
              format_check: { status: "verified", code: "OK", message: "ok" },
              physical_fit: { status: "verified", code: "OK", message: "ok" },
              remaining_capacity: [],
              power_headroom: [],
              connector_availability: { status: "verified", code: "OK", message: "ok" },
              pos5_compatibility: { status: "verified", code: "OK", message: "ok" },
              lid_close: { status: "verified", code: "OK", message: "ok" },
              warnings: [],
              notes: [],
            },
          },
        });
        return;
      }
      if (route.request().method() === "PUT" || route.request().method() === "PATCH") {
        putBody = route.request().postDataJSON();
        await route.fulfill({
          json: {
            id: 7,
            name: "Sim rack",
            case_id: 10,
            user_id: 1,
            generation_seed: 1,
            modules: (putBody?.modules ?? []).map((m, i) => ({
              id: i + 1,
              ...m,
              module: {
                id: m.module_id,
                brand: "Sim",
                name: m.module_id === 10 ? "Gamma" : "Delta",
                hp: m.module_id === 10 ? 12 : 6,
                module_type: "UTIL",
                power_12v_ma: 20,
              },
            })),
            case: {
              id: 10,
              brand: "Sim Co",
              name: "Sim 84",
              total_hp: 84,
              rows: 1,
              hp_per_row: [84],
              catalog_slug: "sim-co-sim-84",
              power_12v_ma: 2000,
              power_neg12v_ma: 1200,
              power_5v_ma: 500,
            },
          },
        });
        return;
      }
      if (
        route.request().method() === "GET" &&
        /\/api\/(racks|canon\/rigs)\/7\/?$/.test(new URL(url).pathname)
      ) {
        await route.fulfill({
          json: {
            id: 7,
            name: "Sim rack",
            case_id: 10,
            user_id: 1,
            generation_seed: 1,
            modules: [],
            case: {
              id: 10,
              brand: "Sim Co",
              name: "Sim 84",
              total_hp: 84,
              rows: 1,
              hp_per_row: [84],
              catalog_slug: "sim-co-sim-84",
              power_12v_ma: 2000,
              power_neg12v_ma: 1200,
              power_5v_ma: 500,
            },
          },
        });
        return;
      }
      await route.continue();
    });
    await page.route("**/api/modules/**", async (route) => {
      if (new URL(route.request().url()).pathname.includes("materialize-batch")) {
        await route.fulfill({
          json: { status: "success", scanned: 0, created: 0, exists: 0, failed: 0 },
        });
        return;
      }
      await route.fulfill({
        json: {
          total: 2,
          modules: [
            {
              id: 10,
              brand: "Sim",
              name: "Gamma",
              hp: 12,
              module_type: "VCO",
              power_12v_ma: 40,
              source: "ModuleCatalog",
              io_ports: [],
              tags: [],
              imported_at: "2026-01-01",
              created_at: "2026-01-01",
              updated_at: "2026-01-01",
            },
            {
              id: 11,
              brand: "Sim",
              name: "Delta",
              hp: 6,
              module_type: "VCA",
              power_12v_ma: 15,
              source: "ModuleCatalog",
              io_ports: [],
              tags: [],
              imported_at: "2026-01-01",
              created_at: "2026-01-01",
              updated_at: "2026-01-01",
            },
          ],
        },
      });
    });

    await page.goto("/racks/7/edit");
    await expect(page.getByRole("heading", { name: "Batch place" })).toBeVisible({
      timeout: 15000,
    });
    await page.getByRole("checkbox", { name: /Select Sim Gamma for batch/i }).check();
    await page.getByRole("checkbox", { name: /Select Sim Delta for batch/i }).check();
    await expect(page.getByText(/Plan: 2 will pack/i)).toBeVisible();
    await page.getByRole("button", { name: "Place 2 selected" }).click();
    await expect(page.getByText(/Batch placed 2 modules/i)).toBeVisible({ timeout: 10000 });
    expect(putBody?.modules?.length).toBe(2);
    expect(putBody?.modules?.[0]).toEqual({ module_id: 10, row_index: 0, start_hp: 0 });
    expect(putBody?.modules?.[1]).toEqual({ module_id: 11, row_index: 0, start_hp: 12 });
  });

  /** Rig 7 on a two-row case, served from state the PUTs change, as the API would. */
  async function mockMovableRig(page: Page, { withCase = true } = {}) {
    const MODULES: Record<number, { name: string; hp: number }> = {
      10: { name: "Gamma", hp: 12 },
      11: { name: "Delta", hp: 6 },
    };
    const state = {
      modules: [
        { module_id: 10, row_index: 0, start_hp: 0 },
        { module_id: 11, row_index: 0, start_hp: 12 },
      ],
    };
    const puts: { module_id: number; row_index: number; start_hp: number }[][] = [];
    const rig = () => ({
      id: 7,
      name: "Sim rack",
      case_id: withCase ? 10 : null,
      user_id: 1,
      generation_seed: 1,
      modules: state.modules.map((m, i) => ({
        id: i + 1,
        ...m,
        module: {
          id: m.module_id,
          brand: "Sim",
          module_type: "UTIL",
          power_12v_ma: 20,
          ...MODULES[m.module_id],
        },
      })),
      case: withCase
        ? {
            id: 10,
            brand: "Sim Co",
            name: "Sim 168",
            total_hp: 168,
            rows: 2,
            hp_per_row: [84, 84],
            power_12v_ma: 2000,
            power_neg12v_ma: 1200,
            power_5v_ma: 500,
          }
        : null,
    });
    await page.route(RIG_7, async (route) => {
      const request = route.request();
      if (request.url().includes("/compatibility")) {
        await route.fulfill({ json: { bridge_status: "ok", message: "ok", compatibility: null } });
        return;
      }
      if (request.method() === "PUT" || request.method() === "PATCH") {
        state.modules = request.postDataJSON().modules;
        puts.push(state.modules);
        await route.fulfill({ json: rig() });
        return;
      }
      await route.fulfill({ json: rig() });
    });
    await page.route("**/api/modules/**", (route) =>
      route.fulfill({
        json: {
          total: 2,
          modules: Object.entries(MODULES).map(([id, m]) => ({
            id: Number(id),
            brand: "Sim",
            module_type: "UTIL",
            power_12v_ma: 20,
            ...m,
          })),
        },
      }),
    );
    return puts;
  }

  test("rack builder drops what the signed-in reader had when they sign out", async ({ page }) => {
    await signIn(page);
    await mockMovableRig(page);
    await page.route("**/api/community/auth/logout", (route) => route.fulfill({ status: 204 }));
    await page.route("**/api/modules/**", (route) => {
      const signedIn = Boolean(route.request().headers()["authorization"]);
      const row = (id: number, name: string) => ({
        id,
        brand: "Sim",
        name,
        hp: 6,
        module_type: "UTIL",
        power_12v_ma: 20,
      });
      const modules = signedIn ? [row(10, "Gamma"), row(77, "Lead only")] : [row(10, "Gamma")];
      return route.fulfill({ json: { total: modules.length, modules } });
    });
    await page.goto("/racks/7/edit");
    const picker = page.getByLabel("Select module to place");
    await expect(picker.getByRole("option", { name: /Lead only/ })).toHaveCount(1);
    await picker.selectOption("77");

    await page.getByRole("button", { name: /Sign out/ }).click();

    await expect(page.getByRole("button", { name: /Sign out/ })).toHaveCount(0);
    await expect(picker.getByRole("option", { name: /Gamma/ })).toHaveCount(1);
    await expect(picker.getByRole("option", { name: /Lead only/ })).toHaveCount(0);
    await expect(picker).toHaveValue("");
  });

  test("rack builder moves a placed module by keyboard, and Undo puts it back", async ({
    page,
  }) => {
    const puts = await mockMovableRig(page);
    await page.goto("/racks/7/edit");
    const delta = page.locator('.placement-rail [data-module="11"]');
    await expect(delta).toBeVisible({ timeout: 15000 });

    // Enter picks it up; 1 + 1 + 4 HP right, then down a row; Enter drops it.
    await delta.focus();
    await page.keyboard.press("Enter");
    await page.keyboard.press("ArrowRight");
    await page.keyboard.press("ArrowRight");
    await page.keyboard.press("Shift+ArrowRight");
    await page.keyboard.press("ArrowDown");
    await page.keyboard.press("Enter");

    await expect(page.getByRole("status").filter({ hasText: "moved" })).toHaveText(
      /Sim Delta moved to row 1 at 18 HP\./,
    );
    expect(puts.at(-1)).toMatchObject([
      { module_id: 10, row_index: 0, start_hp: 0 },
      { module_id: 11, row_index: 1, start_hp: 18 },
    ]);
    // Focus follows the module to its new row.
    await expect(page.locator('.placement-rail [data-module="11"][data-row="1"]')).toBeFocused();

    await page.getByRole("button", { name: "Undo" }).click();
    await expect(page.getByText("Sim Delta is back at row 0 at 12 HP.")).toBeVisible();
    expect(puts.at(-1)).toMatchObject([
      { module_id: 10, row_index: 0, start_hp: 0 },
      { module_id: 11, row_index: 0, start_hp: 12 },
    ]);
  });

  test("rack builder places a Rig with no Case on open rows, with no row end", async ({ page }) => {
    const puts = await mockMovableRig(page, { withCase: false });
    await page.goto("/racks/7/edit");
    await expect(page.locator('.placement-rail [data-module="11"]')).toBeVisible({
      timeout: 15000,
    });
    await expect(
      page.getByText(/no Case named, so each row is as wide as the Modules on it/),
    ).toBeVisible();
    // Its one used row, and an empty one past it to place on.
    await expect(page.getByText("18HP placed, no Case named")).toBeVisible();
    await expect(page.getByText("0HP placed, no Case named")).toBeVisible();

    await page.getByLabel("Select module to place").selectOption("11");
    await page.getByLabel("Row index").fill("1");
    await page.getByLabel("Start HP").fill("120");
    await page.getByRole("button", { name: "Add placement" }).click();

    await expect.poll(() => puts.length).toBe(1);
    expect(puts[0]).toContainEqual(
      expect.objectContaining({ module_id: 11, row_index: 1, start_hp: 120 }),
    );
  });

  test("rack builder creates a Rig with no Case, for entering one by hand", async ({ page }) => {
    await signIn(page);
    let created: unknown = null;
    await page.route(
      (url) => url.pathname.replace(/\/$/, "").endsWith("/api/racks"),
      async (route) => {
        if (route.request().method() !== "POST") return route.fallback();
        created = route.request().postDataJSON();
        await route.fulfill({ status: 201, json: { id: 7 } });
      },
    );
    await mockMovableRig(page, { withCase: false });
    await page.goto("/racks/new");

    await page.getByRole("checkbox", { name: "Go on without a Case" }).check();
    await page.getByRole("button", { name: "Create empty rig" }).click();

    await expect(page).toHaveURL(/\/racks\/7\/edit$/);
    expect(created).toMatchObject({ case_id: null, modules: [] });
  });

  test("rack builder shows a blocked slot and never saves it", async ({ page }) => {
    const puts = await mockMovableRig(page);
    await page.goto("/racks/7/edit");
    const delta = page.locator('.placement-rail [data-module="11"]');
    await expect(delta).toBeVisible({ timeout: 15000 });

    await delta.focus();
    await page.keyboard.press("Enter");
    await page.keyboard.press("ArrowLeft");
    await expect(page.getByText("Can't go there. Overlaps Sim Gamma at HP 0 to 11.")).toBeVisible();
    await expect(page.locator(".rack-row-map__block--ghost")).toHaveAttribute(
      "data-state",
      "blocked",
    );
    await page.keyboard.press("Enter");
    await page.keyboard.press("Escape");
    expect(puts).toHaveLength(0);
  });

  test("rack builder moves a placed module by dragging it to another row", async ({ page }) => {
    const puts = await mockMovableRig(page);
    await page.goto("/racks/7/edit");
    const delta = page.locator('.placement-rail [data-module="11"]');
    await expect(delta).toBeVisible({ timeout: 15000 });

    const from = (await delta.boundingBox())!;
    const row1 = (await page.locator('[data-rail-row="1"]').boundingBox())!;
    await page.mouse.move(from.x + from.width / 2, from.y + from.height / 2);
    await page.mouse.down();
    // Held at its middle (3 HP in), dropped with the pointer at HP 43 of row 1: it starts at 40.
    await page.mouse.move(row1.x + (43 / 84) * row1.width, row1.y + row1.height / 2, { steps: 8 });
    await expect(page.locator(".rack-row-map__block--ghost")).toBeVisible();
    await page.mouse.up();

    await expect(page.getByText(/Sim Delta moved to row 1 at \d+ HP\./)).toBeVisible();
    const moved = puts.at(-1)?.find((m) => m.module_id === 11);
    expect(moved?.row_index).toBe(1);
    expect(Math.abs((moved?.start_hp ?? 0) - 40)).toBeLessThanOrEqual(1);
  });

  test("rack builder keeps the gallery's module_id in the select and batch list", async ({
    page,
  }) => {
    await page.route(RIG_7, async (route) => {
      const path = new URL(route.request().url()).pathname;
      if (route.request().method() === "GET" && /\/api\/(racks|canon\/rigs)\/7\/?$/.test(path)) {
        await route.fulfill({
          json: {
            id: 7,
            name: "Sim rack",
            case_id: 10,
            user_id: 1,
            generation_seed: 1,
            modules: [],
            case: {
              id: 10,
              brand: "Sim Co",
              name: "Sim 84",
              total_hp: 84,
              rows: 1,
              hp_per_row: [84],
              catalog_slug: "sim-co-sim-84",
              power_12v_ma: 2000,
              power_neg12v_ma: 1200,
              power_5v_ma: 500,
            },
          },
        });
        return;
      }
      // Compatibility is optional for this page; a miss leaves the gate panel empty.
      await route.fulfill({ status: 404, json: { detail: "Not found" } });
    });
    await page.route("**/api/modules/**", async (route) => {
      const module = (id: number, name: string, hp: number) => ({
        id,
        brand: "Sim",
        name,
        hp,
        module_type: "VCO",
        power_12v_ma: 40,
        source: "ModuleCatalog",
        io_ports: [],
        tags: [],
        imported_at: "2026-01-01",
        created_at: "2026-01-01",
        updated_at: "2026-01-01",
      });
      await route.fulfill({
        json: { total: 2, modules: [module(10, "Gamma", 12), module(11, "Delta", 6)] },
      });
    });

    await page.goto("/racks/7/edit?module_id=11");
    await expect(page.getByText(/Preselected from gallery/i)).toBeVisible({ timeout: 15000 });
    await expect(page.getByLabel("Filter placeable modules")).toHaveValue("Sim Delta");
    const select = page.getByLabel("Select module to place");
    await expect(select).toHaveValue("11");
    await expect(select.locator("option", { hasText: "Delta" })).toHaveCount(1);
    const batchList = page.getByLabel("Batch module selection");
    await expect(
      batchList.getByRole("checkbox", { name: /Select Sim Delta for batch/i }),
    ).toBeVisible();
    await expect(batchList.getByRole("checkbox")).toHaveCount(1);
    await expect(page.getByText("No modules match the filter.")).toHaveCount(0);
  });

  test("rig overview surfaces sealed inventory receipt", async ({ page }) => {
    await page.route("**/api/**/evidence/inventory**", async (route) => {
      await route.fulfill({
        json: {
          total: 1,
          latest: {
            inventory_revision_id: "inv-rev-e2e-demo",
            system_id: "rack-1",
            rack_id: 1,
            confirmed_count: 2,
            unresolved_count: 0,
            ready_for_generation: true,
            canonical_hash: "c".repeat(64),
            created_by: "e2e",
            created_at: "2026-07-21T00:00:00Z",
          },
          revisions: [],
        },
      });
    });
    await page.goto("/rigs/1");
    await expect(page.getByLabel("Confirmed inventory receipt")).toBeVisible();
    await expect(page.getByText(/Inventory revision:/i)).toBeVisible();
    await expect(page.getByText(/ready for generation/i)).toBeVisible();
    await expect(page.getByText(/2 confirmed module/i)).toBeVisible();
  });

  test("inventory ready enables generate loop and surfaces generation receipt", async ({
    page,
  }) => {
    await page.route("**/api/**/evidence/inventory**", async (route) => {
      await route.fulfill({
        json: {
          total: 1,
          latest: {
            inventory_revision_id: "inv-rev-e2e-ready",
            system_id: "rack-1",
            rack_id: 1,
            confirmed_count: 3,
            unresolved_count: 0,
            ready_for_generation: true,
            canonical_hash: "d".repeat(64),
            created_by: "e2e",
            created_at: "2026-07-21T00:00:00Z",
          },
          revisions: [],
        },
      });
    });
    await page.route("**/api/patches/generate/1**", async (route) => {
      if (route.request().method() !== "POST") {
        await route.fallback();
        return;
      }
      await route.fulfill({
        json: {
          generated_count: 2,
          patches: [
            {
              id: 501,
              name: "Stable Current",
              category: "voice",
              connections: [],
            },
            {
              id: 502,
              name: "Soft Gate",
              category: "rhythm",
              connections: [],
            },
          ],
          run_id: 42,
          export_bridge_ready: true,
          source_run_id: "gen-run-42-" + "a".repeat(16),
          rig_revision_id: "rig-rev-" + "c".repeat(32),
          artifact_manifest_hash: "e".repeat(64),
          inventory_revision_id: "inv-rev-e2e-ready",
          inventory_gate_code: "OK",
          generation_status: "OK",
        },
      });
    });
    // After generate, reloads runs — include the new run
    await page.route("**/api/canon/runs**", async (route) => {
      const url = route.request().url();
      if (url.includes("/rigs/")) {
        return route.fallback();
      }
      await route.fulfill({
        json: {
          total: 1,
          runs: [
            {
              id: 42,
              rack_id: 1,
              status: "succeeded",
              created_at: "2026-07-21T12:00:00Z",
              rig_revision_id: "rig-rev-" + "c".repeat(32),
              source_run_id: "gen-run-42-" + "a".repeat(16),
              artifact_manifest_hash: "e".repeat(64),
              export_bridge_ready: true,
            },
          ],
        },
      });
    });
    await page.route("**/api/runs/42/patches**", async (route) => {
      await route.fulfill({
        json: {
          run_id: 42,
          total: 2,
          patches: [
            { id: 501, name: "Stable Current", category: "voice", connections: [] },
            { id: 502, name: "Soft Gate", category: "rhythm", connections: [] },
          ],
        },
      });
    });

    // Generate is disabled when signed out.
    await signIn(page);
    await page.goto("/rigs/1");
    await expect(page.getByLabel("Inventory to generation loop")).toBeVisible();
    await expect(page.getByLabel("Generate patches from inventory")).toBeVisible();
    await expect(page.getByRole("button", { name: "Generate patches" })).toBeEnabled();
    await page.getByRole("button", { name: "Generate patches" }).click();
    const receipt = page.getByLabel("Generation receipt");
    await expect(receipt).toBeVisible();
    await expect(receipt.getByText(/Generated 2 patches/i)).toBeVisible();
    await expect(receipt.getByText(/run 42/i)).toBeVisible();
    // Switches to patches tab after success
    await expect(page.getByRole("tab", { name: "Patches" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
  });

  test("generate loop without ready inventory uses soft CTA label", async ({ page }) => {
    await page.route("**/api/**/evidence/inventory**", async (route) => {
      await route.fulfill({
        json: { total: 0, latest: null, revisions: [] },
      });
    });
    await page.goto("/rigs/1");
    await expect(
      page.getByRole("button", { name: "Generate patches (may be blocked)" }),
    ).toBeVisible();
    // The way to fix the Rig before generating; spec 009 names it as the Reading screen does.
    await expect(
      page.getByRole("link", { name: "Correct the layout" }).filter({ visible: true }).first(),
    ).toHaveAttribute("href", "/racks/1/edit");
  });
});
