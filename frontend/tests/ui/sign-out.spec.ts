/**
 * Signing out stays on the current page, so a page holding an account's data has to let go of it.
 * Every API call is mocked and answers by the token the request carries, as the API would.
 */
import { expect, test, type Page, type Route } from "@playwright/test";

const STAMP = "2026-01-01T00:00:00Z";
const USER = {
  id: 1,
  username: "e2e-user",
  email: "e2e-user@example.com",
  role: "User",
  display_name: "Private Name",
  created_at: STAMP,
  updated_at: STAMP,
};

const summary = (id: number, name: string, isPublic: boolean) => ({
  rig_id: id,
  rack_id: id,
  user_id: 1,
  case_id: 2,
  name,
  name_suggested: null,
  description: null,
  tags: [],
  is_public: isPublic,
  module_count: 0,
  created_at: STAMP,
  updated_at: STAMP,
});
const PRIVATE_RIG = summary(7, "Private rig", false);
const PUBLIC_RIG = summary(9, "Public rig", true);
const detail = (rig: typeof PRIVATE_RIG) => ({
  ...rig,
  generation_seed: 1,
  vote_count: 0,
  case: null,
  modules: [],
});
const patchRow = (id: number, name: string) => ({
  id,
  rack_id: 7,
  name,
  category: "Voice",
  connections: [],
  generation_seed: 42,
  generation_version: "v1",
  is_public: false,
  vote_count: 0,
  created_at: STAMP,
  updated_at: STAMP,
});

const signedIn = (route: Route) => Boolean(route.request().headers()["authorization"]);
const NOT_FOUND = { status: 404, json: { detail: "not found" } };
const REFUSED = { status: 401, json: { detail: "SESSION_EXPIRED" } };

/** A session restored from the refresh cookie, which sign-out revokes. */
async function mockSession(page: Page) {
  const session = { cookie: true };
  const tokens = () => ({ access_token: "e2e-token", token_type: "bearer", user: USER });
  await page.route("**/api/**", (route) => route.fulfill(NOT_FOUND));
  await page.route("**/api/community/auth/refresh", (route) =>
    route.fulfill(session.cookie ? { json: tokens() } : REFUSED),
  );
  await page.route("**/api/community/auth/logout", (route) => {
    session.cookie = false;
    return route.fulfill({ status: 204 });
  });
  await page.route("**/api/community/auth/login", (route) => {
    session.cookie = true;
    return route.fulfill({ json: tokens() });
  });
  return session;
}

const signOutButton = (page: Page) => page.getByRole("button", { name: /Sign out/ });

test.describe("a change of reader", () => {
  test("the rigs page lets go of the reader's rig when they sign out", async ({ page }) => {
    await mockSession(page);
    await page.route("**/api/canon/rigs**", (route) => {
      const { pathname } = new URL(route.request().url());
      if (pathname.endsWith("/canon/rigs")) {
        const rigs = signedIn(route) ? [PRIVATE_RIG] : [PUBLIC_RIG];
        return route.fulfill({ json: { total: rigs.length, rigs } });
      }
      if (pathname.endsWith("/rigs/7") && signedIn(route)) {
        return route.fulfill({ json: detail(PRIVATE_RIG) });
      }
      return route.fallback();
    });
    await page.route("**/api/canon/runs**", (route) =>
      signedIn(route) ? route.fulfill({ json: { total: 0, runs: [] } }) : route.fallback(),
    );

    await page.goto("/racks/7");
    await expect(page.getByRole("heading", { level: 2, name: "Private rig" })).toBeVisible();

    await signOutButton(page).click();

    await expect(signOutButton(page)).toHaveCount(0);
    await expect(page.getByText("Public rig")).toBeVisible();
    await expect(page.getByText("Private rig")).toHaveCount(0);
    await expect(page).toHaveURL(/\/racks\/7$/);
  });

  test("the account page goes to sign-in, and signing in comes back to it", async ({ page }) => {
    await mockSession(page);
    await page.route("**/api/community/users/me", (route) =>
      signedIn(route) ? route.fulfill({ json: USER }) : route.fulfill(REFUSED),
    );
    await page.route("**/api/canon/credits/summary", (route) =>
      signedIn(route)
        ? route.fulfill({ json: { balance: 41, entries: [] } })
        : route.fulfill(REFUSED),
    );

    await page.goto("/account");
    await expect(page.getByRole("heading", { level: 1, name: "Credits & profile" })).toBeVisible();
    await expect(page.getByLabel("Display name")).toHaveValue("Private Name");

    await signOutButton(page).click();

    await expect(page).toHaveURL(/\/login$/);
    await expect(page.getByLabel("Display name")).toHaveCount(0);
    await expect(page.getByText("41", { exact: true })).toHaveCount(0);

    await page.getByLabel("Username").fill("e2e-user");
    await page.locator('input[name="password"]').fill("demo-pass");
    await page.getByRole("button", { name: "Sign in to PatchHive" }).click();

    await expect(page).toHaveURL(/\/account$/);
    await expect(page.getByLabel("Display name")).toHaveValue("Private Name");
    await expect(page.getByText("41", { exact: true })).toBeVisible();
  });

  test("a token renewal leaves the page as it is", async ({ page }) => {
    await mockSession(page);
    let expired = false;
    await page.route("**/api/patches**", (route) => {
      if (expired) {
        expired = false;
        return route.fulfill(REFUSED);
      }
      return route.fulfill({ json: { total: 1, patches: [patchRow(1, "Private patch")] } });
    });

    await page.goto("/patches");
    await expect(page.getByText("Private patch")).toBeVisible();
    await page.getByLabel("Category").selectOption("Voice");
    await expect(page.getByLabel("Category")).toHaveValue("Voice");

    expired = true;
    const renewal = page.waitForResponse("**/api/community/auth/refresh");
    await page.getByRole("button", { name: "Refresh" }).click();
    await renewal;

    await expect(page.getByText("Private patch")).toBeVisible();
    await expect(page.getByLabel("Category")).toHaveValue("Voice");
    await expect(signOutButton(page)).toBeVisible();
  });

  test("a refused renewal lets go of the reader's data too", async ({ page }) => {
    const session = await mockSession(page);
    let expired = false;
    await page.route("**/api/patches**", (route) => {
      if (expired) return route.fulfill(REFUSED);
      const patches = signedIn(route)
        ? [patchRow(1, "Private patch"), patchRow(2, "Public patch")]
        : [patchRow(2, "Public patch")];
      return route.fulfill({ json: { total: patches.length, patches } });
    });

    await page.goto("/patches");
    await expect(page.getByText("Private patch")).toBeVisible();

    expired = true;
    session.cookie = false;
    const renewal = page.waitForResponse("**/api/community/auth/refresh");
    await page.getByRole("button", { name: "Refresh" }).click();
    await renewal;
    expired = false;

    await expect(signOutButton(page)).toHaveCount(0);
    await expect(page.getByText("Public patch")).toBeVisible();
    await expect(page.getByText("Private patch")).toHaveCount(0);
  });
});
