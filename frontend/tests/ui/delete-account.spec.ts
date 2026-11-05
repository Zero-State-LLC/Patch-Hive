/**
 * Deleting an account from the Account page, in a browser. Every API call is mocked: the catch-all
 * answers anything not named here, and `DELETE /api/me` never leaves the page.
 */
import { expect, test, type Page, type Request } from "@playwright/test";

const LONG_NAME = "a-rather-long-username-that-has-to-wrap-on-a-phone";
const PASSWORD = "correct horse battery";

const user = (username: string) => ({
  id: 1,
  username,
  email: "e2e-user@example.com",
  role: "User",
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
});

interface Recorded {
  deletes: Request[];
  refreshes: number;
  logouts: number;
}

/** Sign in by the refresh cookie, and answer `DELETE /api/me` from `answer`. */
async function mockApi(
  page: Page,
  answer: { status: number; json?: unknown },
  username = "e2e-user",
): Promise<Recorded> {
  const recorded: Recorded = { deletes: [], refreshes: 0, logouts: 0 };
  let signedIn = true;
  await page.route("**/api/**", (route) =>
    route.fulfill({ status: 404, json: { detail: "not mocked" } }),
  );
  await page.route("**/api/community/auth/refresh", (route) => {
    recorded.refreshes += 1;
    return signedIn
      ? route.fulfill({
          json: { access_token: "e2e-token", token_type: "bearer", user: user(username) },
        })
      : route.fulfill({ status: 401, json: { detail: "SESSION_EXPIRED" } });
  });
  await page.route("**/api/community/auth/logout", (route) => {
    recorded.logouts += 1;
    return route.fulfill({ status: 204 });
  });
  await page.route("**/api/community/users/me", (route) => route.fulfill({ json: user(username) }));
  await page.route("**/api/canon/credits/summary", (route) =>
    route.fulfill({ json: { balance: 3, entries: [] } }),
  );
  await page.route("**/api/canon/exports", (route) => route.fulfill({ json: [] }));
  await page.route("**/api/me", (route) => {
    const request = route.request();
    if (request.method() !== "DELETE") return route.fallback();
    recorded.deletes.push(request);
    if (answer.status < 300 || answer.status === 401) signedIn = false;
    return route.fulfill(answer);
  });
  return recorded;
}

async function openAccount(page: Page) {
  await page.goto("/account");
  await expect(page.getByRole("heading", { level: 1, name: "Credits & profile" })).toBeVisible();
}

const panel = (page: Page) => page.locator(".account-delete");
const trigger = (page: Page) => panel(page).getByRole("button", { name: "Delete account…" });
const usernameField = (page: Page) => panel(page).getByLabel(/Type your username/);
const passwordField = (page: Page) => panel(page).getByLabel("Current password");
const confirm = (page: Page) => panel(page).getByRole("button", { name: "Delete my account" });

async function fill(page: Page, username = "e2e-user") {
  await trigger(page).click();
  await usernameField(page).fill(username);
  await passwordField(page).fill(PASSWORD);
}

test.describe("deleting an account", () => {
  test("states the terms, sends the password, then signs out", async ({ page }) => {
    const recorded = await mockApi(page, { status: 204 });
    await openAccount(page);

    await trigger(page).click();
    await expect(panel(page).getByRole("heading", { name: "Confirm deletion" })).toBeFocused();
    await expect(panel(page).getByText(/This can't be undone/)).toBeVisible();
    await expect(panel(page).getByRole("heading", { name: "What's removed" })).toBeVisible();
    await expect(
      panel(page).getByRole("heading", { name: "What's kept, anonymised" }),
    ).toBeVisible();
    await expect(confirm(page)).toBeDisabled();

    await usernameField(page).fill("not-my-name");
    await passwordField(page).fill(PASSWORD);
    await expect(confirm(page)).toBeDisabled();
    await usernameField(page).fill("e2e-user");
    await expect(confirm(page)).toBeEnabled();
    await confirm(page).click();

    const heading = page.getByRole("heading", { level: 1, name: "Account deleted" });
    await expect(heading).toBeVisible();
    await expect(heading).toBeFocused();
    await expect(page.getByRole("link", { name: "Sign in" })).toBeVisible();
    await expect(page.getByRole("button", { name: /Sign out/ })).toHaveCount(0);

    expect(recorded.deletes).toHaveLength(1);
    const sent = recorded.deletes[0];
    expect(sent.method()).toBe("DELETE");
    expect(new URL(sent.url()).pathname).toBe("/api/me");
    expect(sent.postDataJSON()).toEqual({ password: PASSWORD });
    expect(sent.headers()["authorization"]).toBe("Bearer e2e-token");
    expect(recorded.logouts).toBe(0);

    // A reload stays signed out, without even asking the API.
    const refreshesBefore = recorded.refreshes;
    await page.reload();
    await expect(page).toHaveURL(/\/login$/);
    expect(recorded.refreshes).toBe(refreshesBefore);
  });

  test("a wrong password says so in place and stays signed in", async ({ page }) => {
    const recorded = await mockApi(page, {
      status: 403,
      json: { detail: "PASSWORD_INCORRECT" },
    });
    await openAccount(page);
    await fill(page);
    await confirm(page).click();

    await expect(panel(page).getByRole("alert")).toContainText(
      "That password didn't work, so nothing was deleted.",
    );
    await expect(passwordField(page)).toHaveValue("");
    await expect(passwordField(page)).toBeFocused();
    await expect(page.getByRole("button", { name: /Sign out/ })).toBeVisible();
    expect(recorded.deletes).toHaveLength(1);
  });

  for (const { name, answer, message } of [
    {
      name: "too many attempts",
      answer: { status: 429, json: { detail: "Too many attempts; try again shortly" } },
      message: "Too many attempts, so nothing was deleted.",
    },
    {
      name: "a server failure",
      answer: { status: 500, json: { detail: "Internal Server Error" } },
      message: "PatchHive couldn't confirm the deletion.",
    },
  ]) {
    test(`${name} is shown, and the form stays ready`, async ({ page }) => {
      await mockApi(page, answer);
      await openAccount(page);
      await fill(page);
      await confirm(page).click();

      await expect(panel(page).getByRole("alert")).toContainText(message);
      await expect(passwordField(page)).toHaveValue(PASSWORD);
      await expect(confirm(page)).toBeEnabled();
      await expect(confirm(page)).toBeFocused();
      await expect(page.getByRole("button", { name: /Sign out/ })).toBeVisible();
    });
  }

  test("a session that has ended says so, and the control stays in view", async ({ page }) => {
    await mockApi(page, { status: 401, json: { detail: "Not authenticated" } });
    await openAccount(page);
    await fill(page);
    await confirm(page).click();

    await expect(panel(page).getByRole("alert")).toContainText("Your session has ended.");
    await expect(page.getByRole("link", { name: "Sign in" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Account deleted" })).toHaveCount(0);
  });

  test("a lost connection never reads as success", async ({ page }) => {
    await mockApi(page, { status: 204 });
    await page.route("**/api/me", (route) =>
      route.request().method() === "DELETE" ? route.abort("connectionfailed") : route.fallback(),
    );
    await openAccount(page);
    await fill(page);
    await confirm(page).click();

    await expect(panel(page).getByRole("alert")).toContainText(
      "PatchHive couldn't confirm the deletion. PatchHive can't be reached.",
    );
    await expect(page.getByRole("heading", { name: "Account deleted" })).toHaveCount(0);
    await expect(page.getByRole("button", { name: /Sign out/ })).toBeVisible();
  });

  test("works from the keyboard, and backing out sends nothing", async ({ page }) => {
    const recorded = await mockApi(page, { status: 204 });
    await openAccount(page);

    await trigger(page).focus();
    await page.keyboard.press("Enter");
    await expect(panel(page).getByRole("heading", { name: "Confirm deletion" })).toBeFocused();

    await page.keyboard.press("Tab");
    await expect(usernameField(page)).toBeFocused();
    await page.keyboard.type("e2e-user");
    await page.keyboard.press("Tab");
    await expect(passwordField(page)).toBeFocused();
    await page.keyboard.type(PASSWORD);
    await page.keyboard.press("Tab");
    await expect(confirm(page)).toBeFocused();
    await page.keyboard.press("Tab");
    const keep = panel(page).getByRole("button", { name: "Keep my account" });
    await expect(keep).toBeFocused();

    await page.keyboard.press("Enter");
    await expect(trigger(page)).toBeFocused();
    expect(recorded.deletes).toHaveLength(0);
  });

  test("reflows at 320 px with a long username", async ({ page }) => {
    await page.setViewportSize({ width: 320, height: 640 });
    await mockApi(page, { status: 204 }, LONG_NAME);
    await openAccount(page);
    await fill(page, LONG_NAME);
    await expect(confirm(page)).toBeEnabled();

    const sideways = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    );
    expect(sideways, "horizontal page scroll").toBeLessThanOrEqual(1);
  });
});
