import { expect, test } from "@playwright/test";

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
    await expect(navigation.getByRole("link", { name: "Rigs" })).toBeVisible();
    await expect(navigation.getByText("Feed")).toHaveCount(0);
    await expect(navigation.getByText("Publish")).toHaveCount(0);
    await expect(navigation.getByText("Leaderboards")).toHaveCount(0);
  });

  test("photo evidence is keyboard reachable and requires explicit resolution", async ({
    page,
  }) => {
    await page.goto("/racks/new");
    await page.getByRole("button", { name: "Rig photo" }).setInputFiles({
      name: "rig.jpg",
      mimeType: "image/jpeg",
      buffer: Buffer.from([0xff, 0xd8, 0xff, 0xd9]),
    });
    await page.getByRole("button", { name: "Detect modules" }).click();
    await expect(page.getByRole("list", { name: "Ranked module candidates" })).toBeVisible();
    const createRevision = page.getByRole("button", { name: "Create immutable rig revision" });
    await expect(createRevision).toBeDisabled();
    // Resolve every ranked candidate (confirm + reject) so inventory is ready.
    await page.getByRole("button", { name: "Confirm match" }).first().click();
    await page.getByRole("button", { name: "Reject" }).last().click();
    await expect(createRevision).toBeEnabled();
    await createRevision.click();
    await expect(page.getByText(/Inventory revision ready/i)).toBeVisible();
  });

  test("export boundary explains zero-credit state", async ({ page }) => {
    await page.goto("/rigs/1");
    await page.getByRole("tab", { name: "Exports" }).click();
    await expect(page.getByRole("button", { name: "Export PDF patch book" })).toBeDisabled();
    await expect(page.getByText("Credits are required only for exports.")).toBeVisible();
    await expect(page.getByText("/api/canon/exports")).toBeVisible();
  });

  test("multi-photo fusion panel confirms representative and blocks conflict", async ({ page }) => {
    await page.route("**/api/**/evidence/images**", async (route) => {
      if (route.request().method() === "POST") {
        await route.fulfill({
          status: 201,
          json: {
            uploaded: [
              { id: "img-a", rack_id: 1, content_sha256: "a".repeat(64) },
              { id: "img-b", rack_id: 1, content_sha256: "b".repeat(64) },
            ],
            rejected: [],
          },
        });
        return;
      }
      await route.fallback();
    });
    await page.route("**/api/**/evidence/candidates**", async (route) => {
      await route.fulfill({
        json: {
          total: 2,
          candidates: [
            {
              candidate_id: "cand-osc",
              entity_type: "module",
              manufacturer: "MockAudio",
              model: "Oscillator A",
              confidence: 0.91,
              confidence_method: "mock",
              alternative_candidates: [],
              classification_status: "INFERRED",
              evidence_id: "ev-1",
              gallery_revision_id: "catalog-module-osc-a",
            },
            {
              candidate_id: "cand-vca",
              entity_type: "module",
              manufacturer: "MockAudio",
              model: "VCA B",
              confidence: 0.55,
              confidence_method: "mock",
              alternative_candidates: [],
              classification_status: "INFERRED",
              evidence_id: "ev-2",
              gallery_revision_id: "catalog-module-vca-b",
            },
          ],
        },
      });
    });
    await page.route("**/api/**/evidence/reconcile**", async (route) => {
      await route.fulfill({
        json: {
          image_asset_ids: ["img-a", "img-b"],
          image_count: 2,
          fused_entities: [
            {
              fuse_id: "fuse-osc",
              entity_key: "mockaudio|oscillator a",
              manufacturer: "MockAudio",
              model: "Oscillator A",
              entity_type: "module",
              observation_count: 2,
              supporting_image_ids: ["img-a", "img-b"],
              mean_confidence: 0.88,
              max_confidence: 0.91,
              conflict: false,
              conflict_notes: [],
              classification_status: "INFERRED",
              representative_candidate_id: "cand-osc",
            },
            {
              fuse_id: "fuse-conflict",
              entity_key: "mockaudio|mystery",
              manufacturer: "MockAudio",
              model: "Mystery",
              entity_type: "module",
              observation_count: 2,
              supporting_image_ids: ["img-a", "img-b"],
              mean_confidence: 0.4,
              max_confidence: 0.5,
              conflict: true,
              conflict_notes: ["label disagreement across images"],
              classification_status: "INFERRED",
              representative_candidate_id: "cand-vca",
            },
          ],
          unmatched_candidate_ids: [],
          conflict_count: 1,
          status: "RECONCILED_WITH_CONFLICTS",
          note: "Mock multi-photo fusion for e2e.",
        },
      });
    });

    await page.goto("/racks/1/edit");
    await page.getByRole("button", { name: "Rig photo" }).setInputFiles([
      {
        name: "rig-a.jpg",
        mimeType: "image/jpeg",
        buffer: Buffer.from([0xff, 0xd8, 0xff, 0xd9]),
      },
      {
        name: "rig-b.jpg",
        mimeType: "image/jpeg",
        buffer: Buffer.from([0xff, 0xd8, 0xff, 0xd9]),
      },
    ]);
    await page.getByRole("button", { name: "Detect modules" }).click();
    await expect(page.getByLabel("Multi-photo reconciliation")).toBeVisible();
    await expect(page.getByLabel("Fused module entities")).toBeVisible();

    const conflictRow = page.getByLabel("Resolve fused Mystery");
    await expect(conflictRow.getByRole("button", { name: "Confirm fused match" })).toBeDisabled();

    await page.getByRole("button", { name: "Confirm fused match" }).first().click();
    await expect(page.getByText(/Applied confirmed to fused/i)).toBeVisible();
    await expect(page.getByText("Status: confirmed").first()).toBeVisible();
  });

  test("module gallery supports search filter and placement entry", async ({ page }) => {
    const allModules = [
      {
        id: 1,
        slug: "mockaudio-oscillator-a",
        brand: "MockAudio",
        name: "Oscillator A",
        hp: 12,
        category: "VCO",
        is_available: "available",
      },
      {
        id: 2,
        slug: "otherbrand-filter-z",
        brand: "OtherBrand",
        name: "Filter Z",
        hp: 8,
        category: "VCF",
        is_available: "available",
      },
    ];

    // Single dispatcher — avoids route-order races between /catalog and /catalog/stats etc.
    await page.route("**/api/modules/catalog**", async (route) => {
      const url = new URL(route.request().url());
      const path = url.pathname.replace(/\/+$/, "");
      if (path.endsWith("/catalog/stats")) {
        await route.fulfill({
          json: {
            total_modules: 2,
            total_brands: 2,
            total_categories: 2,
            hp_stats: {
              average: 10,
              min: 8,
              max: 12,
              known: 2,
              unknown: 0,
              coverage_pct: 100,
            },
            availability: { available: 2, discontinued: 0 },
          },
        });
        return;
      }
      if (path.endsWith("/catalog/brands")) {
        await route.fulfill({
          json: {
            total: 2,
            brands: [
              { name: "MockAudio", module_count: 1 },
              { name: "OtherBrand", module_count: 1 },
            ],
          },
        });
        return;
      }
      if (path.endsWith("/catalog/categories")) {
        await route.fulfill({
          json: {
            total: 2,
            categories: [
              { name: "VCO", module_count: 1 },
              { name: "VCF", module_count: 1 },
            ],
          },
        });
        return;
      }
      if (path.endsWith("/materialize") || path.includes("/materialize")) {
        await route.fulfill({
          json: {
            status: "created",
            catalog_slug: "otherbrand-filter-z",
            module_id: 99,
            module: {
              id: 99,
              brand: "OtherBrand",
              name: "Filter Z",
              hp: 8,
              module_type: "VCF",
              source: "ModuleCatalog",
            },
          },
        });
        return;
      }
      const search = (url.searchParams.get("search") || "").toLowerCase();
      const modules = search
        ? allModules.filter(
            (m) => m.brand.toLowerCase().includes(search) || m.name.toLowerCase().includes(search),
          )
        : allModules;
      await route.fulfill({
        json: {
          total: modules.length,
          skip: 0,
          limit: 48,
          modules,
        },
      });
    });
    await page.goto("/modules");
    await expect(page.getByRole("heading", { name: "Module gallery" })).toBeVisible();
    await expect(page.getByLabel("Module filters")).toBeVisible({ timeout: 15000 });
    await expect(page.getByLabel("Module catalog results")).toBeVisible();
    await expect(page.getByText(/Showing 2 of 2 catalog modules/)).toBeVisible();
    await page.getByRole("searchbox", { name: "Search modules" }).fill("Filter");
    await expect(page.getByText(/Showing 1 of 1 catalog modules \(filtered\)/)).toBeVisible();
    // Catalog cards use separate brand/name mockup faces (not a single "Brand — Name" string).
    const filteredCard = page.getByLabel("Module: OtherBrand Filter Z, 8 HP, VCF");
    await expect(filteredCard).toBeVisible();
    await expect(filteredCard.getByText("OtherBrand", { exact: true })).toBeVisible();
    await expect(filteredCard.getByText("Filter Z", { exact: true })).toBeVisible();
    await expect(page.getByText("Oscillator A")).toHaveCount(0);
    await expect(page.getByRole("link", { name: "Place on new rig" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Prepare for rig" }).first()).toBeVisible();

    // Prepare for rig → materialize + navigate to rack create with module_id
    await page.getByRole("button", { name: "Prepare for rig" }).first().click();
    await page.waitForURL(/\/racks\/new\?module_id=99/);
    await expect(page).toHaveURL(/module_id=99/);
  });

  test("rack builder edit shows dual-gate panel and power completeness", async ({ page }) => {
    await page.route("**/api/racks/7**", async (route) => {
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
      if (route.request().method() === "GET" && /\/api\/racks\/7\/?$/.test(new URL(url).pathname)) {
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

    await page.goto("/racks/7/edit");
    await expect(page.getByRole("heading", { name: "Module placement" })).toBeVisible({
      timeout: 15000,
    });
    await expect(page.getByLabel("Builder steps")).toBeVisible();
    await expect(page.getByText("Place modules").first()).toBeVisible();
    await expect(page.getByLabel("Row HP usage")).toBeVisible();
    await expect(page.getByText(/18\/84HP used/i)).toBeVisible();
    await expect(page.getByLabel(/Row 0 layout/i)).toBeVisible();
    await expect(page.getByTitle(/Alpha.*HP 0–9/i)).toBeVisible();
    await expect(page.getByTitle(/Beta.*power unknown/i)).toBeVisible();
    await expect(page.getByText(/Placement power/i)).toBeVisible();
    await expect(page.getByText(/1 modules with \+12 known/i)).toBeVisible();
    await expect(page.getByText(/1 unknown/i)).toBeVisible();
    await expect(page.getByLabel("Power rail usage")).toBeVisible();
    await expect(page.getByLabel("+12V power usage")).toBeVisible();
    // Alpha: +12 40 / case 2000 · Beta power unknown not assumed
    await expect(page.getByText(/40\/2000mA/i).first()).toBeVisible();
    await expect(page.getByText(/Soft gap: 1 module without \+12 specs/i)).toBeVisible();
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
    await page.route("**/api/racks/7**", async (route) => {
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
      if (route.request().method() === "GET" && /\/api\/racks\/7\/?$/.test(new URL(url).pathname)) {
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

  test("module gallery URL filters and status chips", async ({ page }) => {
    const allModules = [
      {
        id: 1,
        slug: "mockaudio-oscillator-a",
        brand: "MockAudio",
        name: "Oscillator A",
        hp: 12,
        category: "VCO",
        source: "SynthCatalogResearch",
        is_available: "available",
      },
      {
        id: 2,
        slug: "otherbrand-filter-z",
        brand: "OtherBrand",
        name: "Filter Z",
        hp: 8,
        category: "VCF",
        source: "ModuleCatalog",
        is_available: "available",
      },
    ];
    await page.route("**/api/modules/**", async (route) => {
      const url = new URL(route.request().url());
      const path = url.pathname;
      if (path.endsWith("/catalog/stats")) {
        await route.fulfill({
          json: {
            total_modules: 2,
            total_brands: 2,
            total_categories: 2,
            hp_stats: { average: 10, min: 8, max: 12, known: 2, unknown: 0, coverage_pct: 100 },
            availability: { available: 2 },
            by_source: { SynthCatalogResearch: 1, ModuleCatalog: 1 },
          },
        });
        return;
      }
      if (path.endsWith("/catalog/brands")) {
        await route.fulfill({
          json: {
            total: 2,
            brands: [
              { name: "MockAudio", module_count: 1 },
              { name: "OtherBrand", module_count: 1 },
            ],
          },
        });
        return;
      }
      if (path.endsWith("/catalog/categories")) {
        await route.fulfill({
          json: {
            total: 2,
            categories: [
              { name: "VCO", module_count: 1 },
              { name: "VCF", module_count: 1 },
            ],
          },
        });
        return;
      }
      if (path.includes("/catalog")) {
        await route.fulfill({
          json: { total: allModules.length, skip: 0, limit: 48, modules: allModules },
        });
        return;
      }
      await route.continue();
    });

    await page.goto("/modules?hp=known");
    await expect(page.getByRole("heading", { name: "Module gallery" })).toBeVisible();
    await expect(page.getByLabel("Active filters")).toBeVisible();
    await expect(page.getByText("HP known").first()).toBeVisible();
    await expect(page.getByText("placeable").first()).toBeVisible();
    await expect(page).toHaveURL(/hp=known/);
    await expect(page.getByRole("button", { name: "Add to existing" }).first()).toBeVisible();
  });

  test("module add-to-existing opens rig picker after materialize", async ({ page }) => {
    await page.route("**/api/modules/**", async (route) => {
      const path = new URL(route.request().url()).pathname;
      if (path.endsWith("/catalog/stats")) {
        await route.fulfill({
          json: {
            total_modules: 1,
            total_brands: 1,
            total_categories: 1,
            hp_stats: { average: 8, min: 8, max: 8, known: 1, unknown: 0, coverage_pct: 100 },
            availability: { available: 1 },
            by_source: { ModuleCatalog: 1 },
          },
        });
        return;
      }
      if (path.endsWith("/catalog/brands")) {
        await route.fulfill({
          json: { total: 1, brands: [{ name: "OtherBrand", module_count: 1 }] },
        });
        return;
      }
      if (path.endsWith("/catalog/categories")) {
        await route.fulfill({ json: { total: 1, categories: [{ name: "VCF", module_count: 1 }] } });
        return;
      }
      if (path.includes("/materialize")) {
        await route.fulfill({
          json: {
            status: "exists",
            catalog_slug: "otherbrand-filter-z",
            module_id: 42,
            module: { id: 42, brand: "OtherBrand", name: "Filter Z", hp: 8, module_type: "VCF" },
          },
        });
        return;
      }
      if (path.includes("/catalog")) {
        await route.fulfill({
          json: {
            total: 1,
            skip: 0,
            limit: 48,
            modules: [
              {
                id: 2,
                slug: "otherbrand-filter-z",
                brand: "OtherBrand",
                name: "Filter Z",
                hp: 8,
                category: "VCF",
                source: "ModuleCatalog",
                is_available: "available",
              },
            ],
          },
        });
        return;
      }
      await route.continue();
    });
    await page.route("**/api/racks/**", async (route) => {
      if (route.request().method() === "GET") {
        await route.fulfill({
          json: {
            total: 1,
            racks: [{ id: 7, name: "Sim rack", case_id: 10, user_id: 1, modules: [] }],
          },
        });
        return;
      }
      await route.continue();
    });

    await page.goto("/modules?hp=known");
    await page.getByRole("button", { name: "Add to existing" }).first().click();
    await expect(page.getByLabel("Select existing rig")).toBeVisible({ timeout: 10000 });
    await expect(page.getByRole("button", { name: "Open placement" })).toBeEnabled();
    await page.getByRole("button", { name: "Open placement" }).click();
    await page.waitForURL(/\/racks\/7\/edit\?module_id=42/);
  });

  test("cases catalog shows placeable chips and URL format filter", async ({ page }) => {
    await page.route("**/api/cases/**", async (route) => {
      const url = new URL(route.request().url());
      const path = url.pathname;
      if (path.includes("/stats") || path.endsWith("/catalog/stats")) {
        await route.fulfill({
          json: {
            case_count: 1,
            manufacturer_count: 1,
            with_power_rails: 1,
            with_depth: 1,
            source_packet_count: 1,
          },
        });
        return;
      }
      // case catalog list
      await route.fulfill({
        json: {
          total: 1,
          skip: 0,
          limit: 200,
          cases: [
            {
              slug: "sim-co-sim-84",
              manufacturer: "Sim Co",
              model: "Sim 84",
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
        },
      });
    });

    await page.goto("/cases?format=eurorack");
    await expect(page.getByRole("heading", { name: "Cases" })).toBeVisible();
    await expect(page.getByLabel("Case filters")).toBeVisible({ timeout: 15000 });
    await expect(page.getByText("placeable").first()).toBeVisible();
    await expect(page.getByText("powered").first()).toBeVisible();
    await expect(page).toHaveURL(/format=eurorack/);
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
    await expect(page.getByRole("link", { name: /Confirm inventory/i })).toBeVisible();
  });
});
