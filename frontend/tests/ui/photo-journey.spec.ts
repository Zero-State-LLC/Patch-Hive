/**
 * Spec 009 T050: the photo journey in a browser, with the API mocked. A photo of the Rig goes
 * in, the owner corrects its Reading, and confirming it leads to the Rig screen. Where photo
 * reading isn't open, the Photo screen says so and offers manual entry.
 */
import { readFileSync } from "node:fs";
import { expect, test, type Page, type Request } from "@playwright/test";

const STAMP = "2026-01-01T00:00:00Z";
const RIG = 7;
// A small photo of a Rig, for the Reading screen to draw its boxes over.
const PHOTO = readFileSync(new URL("./fixtures/rig-photo.jpg", import.meta.url));

const candidate = (id: number, name: string, score: number, hp: number) => ({
  module_id: id,
  score,
  brand: "Sim Co",
  name,
  hp,
});

const sighting = (id: string, over: Record<string, unknown>) => ({
  sighting_id: id,
  box: { x: 0.1, y: 0.1, w: 0.1, h: 0.8 },
  kind: "module",
  row_index: 0,
  start_hp: 0,
  hp: 10,
  candidates: [],
  disposition: "unresolved",
  ...over,
});

const reading = (status: string, sightings: unknown[], reason: string | null = null) => ({
  reading_id: "read-1",
  photo_id: "img-1",
  status,
  reason_code: reason,
  provider: "recorded",
  provider_version: "recorded-1",
  first_row: 0,
  last_row: 0,
  created_at: STAMP,
  completed_at: STAMP,
  sightings,
});

const SIGHTINGS = [
  sighting("s-sure", {
    disposition: "auto_propose",
    box: { x: 0.0, y: 0.1, w: 0.12, h: 0.8 },
    candidates: [candidate(11, "Oscillator", 0.95, 10)],
  }),
  sighting("s-check", {
    disposition: "user_review",
    start_hp: 10,
    hp: 8,
    box: { x: 0.12, y: 0.1, w: 0.1, h: 0.8 },
    candidates: [candidate(12, "Filter A", 0.6, 8), candidate(13, "Filter B", 0.3, 8)],
  }),
  sighting("s-unknown", {
    kind: "unknown",
    start_hp: 18,
    hp: 6,
    box: { x: 0.22, y: 0.1, w: 0.07, h: 0.8 },
  }),
  sighting("s-panel", {
    kind: "blank_panel",
    start_hp: 24,
    hp: 4,
    box: { x: 0.29, y: 0.1, w: 0.05, h: 0.8 },
  }),
];

const catalogModule = (id: number, name: string, hp: number) => ({
  id,
  brand: "Sim Co",
  name,
  hp,
  module_type: "ENV",
  power_12v_ma: 20,
  power_neg12v_ma: 10,
  power_5v_ma: 0,
  io_ports: [],
  tags: [],
  source: "test",
  created_at: STAMP,
  updated_at: STAMP,
});

const SEARCH: Record<string, unknown[]> = {
  env: [catalogModule(30, "Envelope", 6)],
  lfo: [catalogModule(31, "LFO", 4)],
};

async function signIn(page: Page) {
  await page.route("**/api/community/auth/refresh", (route) =>
    route.fulfill({
      json: {
        access_token: "e2e-token",
        token_type: "bearer",
        user: {
          id: 1,
          username: "e2e-user",
          email: "e2e-user@example.com",
          role: "User",
          created_at: STAMP,
          updated_at: STAMP,
        },
      },
    }),
  );
}

const placedModule = (
  id: number,
  moduleId: number,
  name: string,
  row: number,
  startHp: number,
  hp: number,
) => ({
  id,
  module_id: moduleId,
  row_index: row,
  start_hp: startHp,
  module: { id: moduleId, brand: "Sim Co", name, hp, module_type: "VCO" },
});

/** The Rig as the canon API reads it: no Case, and `modules` already placed. */
const rigDetail = (modules: unknown[] = []) => ({
  rig_id: RIG,
  rack_id: RIG,
  user_id: 1,
  case_id: null,
  name: "From a photo",
  name_suggested: "From a photo",
  description: null,
  tags: [],
  is_public: false,
  module_count: modules.length,
  created_at: STAMP,
  updated_at: STAMP,
  generation_seed: 1,
  vote_count: 0,
  modules,
  case: null,
});

/** The API for a Rig whose photo reads as `readings()` says at the time it is asked. */
async function mockReading(page: Page, readings: () => unknown[], placed: unknown[] = []) {
  await page.route(`**/api/racks/${RIG}/evidence/readings`, (route) =>
    route.fulfill({ json: { readings: readings() } }),
  );
  await page.route(`**/api/canon/rigs/${RIG}`, (route) =>
    route.fulfill({ json: rigDetail(placed) }),
  );
  await page.route(`**/api/racks/${RIG}/evidence/images/img-1/content`, (route) =>
    route.fulfill({ body: PHOTO, contentType: "image/jpeg" }),
  );
  await page.route("**/api/modules/?**", (route) => {
    const q = new URL(route.request().url()).searchParams.get("q") ?? "";
    const modules = SEARCH[q.toLowerCase()] ?? [];
    return route.fulfill({ json: { total: modules.length, modules } });
  });
}

const capability = (page: Page, available: boolean, reason: string | null = null) =>
  page.route("**/api/evidence/photo-reading", (route) =>
    route.fulfill({ json: { available, reason } }),
  );

/** The text fields a multipart request sent, by name. */
function formFields(request: Request): Record<string, string> {
  const body = request.postDataBuffer()?.toString("latin1") ?? "";
  const fields: Record<string, string> = {};
  for (const match of body.matchAll(/name="([^"]+)"\r\n\r\n([^\r]*)\r\n/g)) {
    fields[match[1]] = match[2];
  }
  return fields;
}

test.describe("the photo journey", () => {
  test("the home page's example reading is listed as the Reading screen lists it", async ({
    page,
  }) => {
    await page.goto("/");

    const items = page.getByRole("list", { name: "An example reading" }).getByRole("listitem");
    await expect(items).toHaveCount(3);
    await expect(items.nth(0)).toContainText("Check this");
    await expect(items.nth(1)).toContainText("Sure");
    await expect(items.nth(2)).toContainText("Sure");
  });

  test("a visitor is asked to sign in before photographing their Rig", async ({ page }) => {
    await page.goto("/");

    await page.getByRole("link", { name: "Photograph your Rig" }).click();

    await expect(page).toHaveURL(/\/login$/);
  });

  test("a photo becomes a confirmed Rig, with every correction made on the Reading", async ({
    page,
  }) => {
    await signIn(page);
    await capability(page, true);
    await mockReading(page, () => [reading("read", SIGHTINGS)]);
    let started: Record<string, string> = {};
    await page.route("**/api/evidence/rig-photos", (route) => {
      started = formFields(route.request());
      return route.fulfill({
        status: 201,
        json: { rig_id: RIG, photo_id: "img-1", reading_id: "read-1" },
      });
    });
    let confirmed: unknown = null;
    await page.route(`**/api/racks/${RIG}/evidence/readings/confirm`, (route) => {
      confirmed = route.request().postDataJSON();
      return route.fulfill({
        status: 201,
        json: {
          rig_revision_id: "rig-rev-1",
          inventory_revision_id: "inv-rev-1",
          ready_for_generation: true,
          placements: [],
          modules_to_place: [],
          warnings: [],
        },
      });
    });

    await page.goto("/");
    await page.getByRole("link", { name: "Photograph your Rig" }).click();

    // The Photo screen: guidance, the camera on a phone, the rows, and the owner's consent.
    await expect(page).toHaveURL(/\/rigs\/new\/photo$/);
    await expect(page.getByText(/whole Rig, straight on/i)).toBeVisible();
    const file = page.getByLabel("Photo of your Rig");
    await expect(file).toHaveAttribute("capture", "environment");
    await file.setInputFiles({ name: "rig.jpg", mimeType: "image/jpeg", buffer: PHOTO });
    const read = page.getByRole("button", { name: "Read this photo" });
    await expect(read).toBeDisabled();
    await page.getByRole("checkbox", { name: /let the reading service see this photo/i }).check();
    await read.click();

    await expect(page).toHaveURL(new RegExp(`/rigs/${RIG}/reading$`));
    expect(started).toMatchObject({ rows: "0", consent_provider_processing: "true" });

    // The Reading screen: numbered boxes on the photo, and the same list in text, the
    // Modules PatchHive is unsure of first.
    await expect(page.locator(".reading-photo__box")).toHaveCount(4);
    const items = page.getByRole("listitem").filter({ has: page.locator(".sighting__number") });
    await expect(items).toHaveCount(4);
    await expect(items.nth(0)).toContainText("Couldn't tell");
    await expect(items.nth(1)).toContainText("Check this");
    await expect(items.nth(2)).toContainText("Sure");
    await expect(items.nth(3)).toContainText("Blank panel");
    await expect(items.nth(2)).toContainText("Row 0, HP 0 to 10");

    // Confirming waits until every Module is decided.
    const confirm = page.getByRole("button", { name: "Confirm the Rig" });
    await expect(page.getByText(/1 still to decide/)).toBeVisible();

    // Couldn't tell: the owner finds it in the catalog.
    await items.nth(0).getByLabel("Search the catalog").fill("env");
    await items.nth(0).getByRole("button", { name: "Use Sim Co Envelope" }).click();
    await expect(items.nth(0)).toContainText("Sim Co Envelope");

    // Check this: one tap on the other close match.
    await items.nth(1).getByRole("radio", { name: "Sim Co Filter B" }).check();

    // Sure, but the owner leaves it out of the Rig.
    await items.nth(2).getByRole("button", { name: "Leave out" }).click();

    // A Module PatchHive missed, added at the position the owner chooses.
    const add = page.getByRole("region", { name: "Add a Module" });
    await add.getByLabel("Search the catalog").fill("lfo");
    await add.getByRole("button", { name: "Use Sim Co LFO" }).click();
    await add.getByLabel("Row").fill("1");
    await add.getByLabel("Start HP").fill("0");
    await add.getByRole("button", { name: "Add to the Rig" }).click();

    await expect(page.getByText(/still to decide/)).toHaveCount(0);
    await confirm.click();

    await expect(page).toHaveURL(new RegExp(`/rigs/${RIG}$`));
    expect(confirmed).toEqual({
      items: [
        { sighting_id: "s-unknown", module_id: 30, row_index: 0, start_hp: 18 },
        { sighting_id: "s-check", module_id: 13, row_index: 0, start_hp: 10 },
      ],
      added: [{ module_id: 31, row_index: 1, start_hp: 0 }],
      excluded: ["s-sure"],
      case_id: null,
    });
  });

  test("the layout can be corrected, and an overlap is named before confirming", async ({
    page,
  }) => {
    await signIn(page);
    await mockReading(page, () => [reading("read", SIGHTINGS.slice(0, 2))]);
    await page.goto(`/rigs/${RIG}/reading`);

    const items = page.getByRole("listitem").filter({ has: page.locator(".sighting__number") });
    await page.getByRole("button", { name: "Correct the layout" }).click();
    // Move the Filter onto the Oscillator's HP.
    await items.nth(0).getByLabel("Start HP").fill("4");

    // The warning names both Modules and where they sit, not only a red border.
    const warning = page.getByRole("alert");
    await expect(warning).toContainText(/overlap/i);
    await expect(warning).toContainText("Sim Co Oscillator (row 0, HP 0 to 10)");
    await expect(warning).toContainText("Sim Co Filter A (row 0, HP 4 to 12)");
    await expect(page.getByRole("button", { name: "Confirm the Rig" })).toBeDisabled();
  });

  test("the Rig screen leads back to an open Reading and deletes a photo when asked twice", async ({
    page,
  }) => {
    await signIn(page);
    await mockReading(page, () => [reading("read", SIGHTINGS)]);
    let photos = [{ id: "img-1", created_at: STAMP, retention_expires_at: "2026-01-31T00:00:00Z" }];
    const deleted: string[] = [];
    await page.route(`**/api/racks/${RIG}/evidence/images`, (route) =>
      route.fulfill({ json: { total: photos.length, assets: photos } }),
    );
    await page.route(`**/api/racks/${RIG}/evidence/images/img-1`, (route) => {
      if (route.request().method() !== "DELETE") return route.fallback();
      deleted.push("img-1");
      photos = [];
      return route.fulfill({ json: { status: "deleted" } });
    });
    await page.goto(`/rigs/${RIG}`);

    const panel = page.getByRole("region", { name: "Photos" });
    await expect(panel.getByRole("link", { name: "Check the reading" })).toHaveAttribute(
      "href",
      `/rigs/${RIG}/reading`,
    );
    await expect(panel.getByRole("link", { name: "Take a new photo" })).toHaveAttribute(
      "href",
      `/rigs/${RIG}/photo`,
    );
    await expect(panel).toContainText("kept until");

    // Each step's button replaces the one pressed, and focus moves with it.
    const ask = panel.getByRole("button", { name: /^Delete the photo taken/ });
    await ask.click();
    expect(deleted).toEqual([]);
    await expect(panel.getByRole("button", { name: "Delete it now" })).toBeFocused();
    await panel.getByRole("button", { name: "Keep it" }).click();
    await expect(ask).toBeFocused();
    await ask.click();
    await panel.getByRole("button", { name: "Delete it now" }).click();

    await expect(panel).toContainText("No photo of this Rig is kept.");
    await expect(panel.getByRole("heading", { name: "Photos" })).toBeFocused();
    expect(deleted).toEqual(["img-1"]);
  });

  test("a confirmed Rig has no Reading to go back to", async ({ page }) => {
    await signIn(page);
    await mockReading(page, () => [reading("confirmed", SIGHTINGS)]);
    await page.route(`**/api/racks/${RIG}/evidence/images`, (route) =>
      route.fulfill({ json: { total: 0, assets: [] } }),
    );
    await page.goto(`/rigs/${RIG}`);

    const panel = page.getByRole("region", { name: "Photos" });
    await expect(panel.getByRole("link", { name: "Take a new photo" })).toBeVisible();
    await expect(panel.getByRole("link", { name: "Check the reading" })).toHaveCount(0);
  });

  test("the Rig's other rows stay, and a Module added over one of them is named", async ({
    page,
  }) => {
    await signIn(page);
    // Row 1 was confirmed from an earlier photo; this photo covers row 0 only.
    await mockReading(page, () => [reading("read", SIGHTINGS.slice(0, 1))], [
      placedModule(901, 21, "Sequencer", 1, 0, 16),
    ]);
    await page.goto(`/rigs/${RIG}/reading`);

    await expect(page.getByText(/Sim Co Sequencer stays on row 1/)).toBeVisible();
    const add = page.getByRole("region", { name: "Add a Module" });
    await add.getByLabel("Search the catalog").fill("lfo");
    await add.getByRole("button", { name: "Use Sim Co LFO" }).click();
    await add.getByLabel("Row").fill("1");
    await add.getByLabel("Start HP").fill("4");
    await add.getByRole("button", { name: "Add to the Rig" }).click();

    await expect(page.getByRole("alert")).toContainText(/overlap/i);
    await expect(page.getByRole("alert")).toContainText("Sim Co Sequencer (row 1, HP 0 to 16)");
    await expect(page.getByRole("button", { name: "Confirm the Rig" })).toBeDisabled();
  });

  test("leaving a Module out and keeping it again brings back the owner's choice", async ({
    page,
  }) => {
    await signIn(page);
    await mockReading(page, () => [reading("read", SIGHTINGS.slice(1, 2))]);
    await page.goto(`/rigs/${RIG}/reading`);

    const item = page.getByRole("listitem").filter({ has: page.locator(".sighting__number") });
    await item.getByRole("radio", { name: "Sim Co Filter B" }).check();
    await item.getByRole("button", { name: "Leave out" }).click();
    await expect(item).toContainText("Left out of the Rig");
    await item.getByRole("button", { name: "Keep it" }).click();

    await expect(item.getByRole("radio", { name: "Sim Co Filter B" })).toBeChecked();
  });

  test("a Retake replaces the Reading it names", async ({ page }) => {
    await signIn(page);
    await capability(page, true);
    await mockReading(page, () => [reading("read", SIGHTINGS)]);
    let started: Record<string, string> = {};
    await page.route("**/api/evidence/rig-photos", (route) => {
      started = formFields(route.request());
      return route.fulfill({
        status: 201,
        json: { rig_id: RIG, photo_id: "img-1", reading_id: "read-2" },
      });
    });
    await page.goto(`/rigs/${RIG}/photo?replaces=read-1`);

    await expect(page.getByRole("heading", { name: "Retake the photo" })).toBeVisible();
    await page
      .getByLabel("Photo of your Rig")
      .setInputFiles({ name: "rig.jpg", mimeType: "image/jpeg", buffer: PHOTO });
    await page.getByRole("checkbox", { name: /let the reading service see this photo/i }).check();
    await page.getByRole("button", { name: "Read this photo" }).click();

    await expect(page).toHaveURL(new RegExp(`/rigs/${RIG}/reading$`));
    expect(started).toMatchObject({ rig_id: String(RIG), replaces_reading_id: "read-1" });
  });

  test("a failed Reading says why in words and can be retried", async ({ page }) => {
    await signIn(page);
    let retried = false;
    // The retry supersedes the failed Reading with one that reads.
    await mockReading(page, () =>
      retried
        ? [
            reading("superseded", [], "PROVIDER_TIMED_OUT"),
            { ...reading("read", SIGHTINGS.slice(0, 1)), reading_id: "read-2" },
          ]
        : [reading("failed", [], "PROVIDER_TIMED_OUT")],
    );
    await page.route(`**/api/racks/${RIG}/evidence/readings/read-1/retry`, (route) => {
      retried = true;
      return route.fulfill({
        status: 201,
        json: { rig_id: RIG, photo_id: "img-1", reading_id: "read-1" },
      });
    });
    await page.goto(`/rigs/${RIG}/reading`);

    await expect(page.getByText("Reading the photo took too long.")).toBeVisible();
    await expect(page.getByRole("link", { name: "Retake" })).toHaveAttribute(
      "href",
      `/rigs/${RIG}/photo?replaces=read-1`,
    );
    await page.getByRole("button", { name: "Retry" }).click();

    expect(retried).toBe(true);
    await expect(page.getByText("Sure")).toBeVisible();
  });

  test("where photo reading is closed, the Photo screen says so and offers manual entry", async ({
    page,
  }) => {
    await signIn(page);
    await capability(page, false, "PROVIDER_DISABLED");
    await page.goto("/rigs/new/photo");

    await expect(page.getByText(/photo reading isn't open on this site/i)).toBeVisible();
    await expect(page.getByRole("link", { name: "Enter your Rig by hand" })).toHaveAttribute(
      "href",
      "/racks/new",
    );
    await expect(page.getByLabel("Photo of your Rig")).toHaveCount(0);
  });
});
