/**
 * Spec 009 T051: the navigation holds only the journey (My Rigs, Patches, Account, plus Admin
 * for an Admin), and the catalog pages it no longer has send old links to the home page
 * (decision 58). The API is mocked; anything not mocked answers 404.
 */
import { expect, test, type Page } from "@playwright/test";

const STAMP = "2026-01-01T00:00:00Z";

async function signIn(page: Page, role: "User" | "Admin") {
  const user = {
    id: 1,
    username: "nav-user",
    email: "nav-user@example.com",
    role,
    created_at: STAMP,
    updated_at: STAMP,
  };
  await page.route("**/api/community/auth/refresh", (route) =>
    route.fulfill({ json: { access_token: "nav-token", token_type: "bearer", user } }),
  );
  await page.route("**/api/community/users/me", (route) => route.fulfill({ json: user }));
}

async function navLinks(page: Page): Promise<string[]> {
  const nav = page.getByRole("navigation", { name: "Primary navigation" });
  await expect(nav.getByRole("link").first()).toBeVisible();
  return nav.getByRole("link").allTextContents();
}

test.beforeEach(async ({ page }) => {
  await page.route("**/api/**", (route) =>
    route.fulfill({ status: 404, json: { detail: "Not Found" } }),
  );
});

test.describe("the primary navigation", () => {
  test("holds My Rigs and Patches for a visitor", async ({ page }) => {
    await page.goto("/");

    expect(await navLinks(page)).toEqual(["My Rigs", "Patches"]);
  });

  test("adds Account for a signed-in owner", async ({ page }) => {
    await signIn(page, "User");
    await page.goto("/");

    await expect.poll(() => navLinks(page)).toEqual(["My Rigs", "Patches", "Account"]);
  });

  test("adds Admin for an Admin", async ({ page }) => {
    await signIn(page, "Admin");
    await page.goto("/");

    await expect.poll(() => navLinks(page)).toEqual(["My Rigs", "Patches", "Account", "Admin"]);
    const nav = page.getByRole("navigation", { name: "Primary navigation" });
    await expect(nav.getByRole("link", { name: "Admin" })).toHaveAttribute("href", "/admin");
  });
});

test.describe("the catalog pages it no longer has", () => {
  for (const path of [
    "/modules",
    "/modules?hp=known",
    "/products",
    "/products?query=make-noise",
    "/cases",
    "/cases/eurorack-104",
  ]) {
    test(`${path} lands on the home page`, async ({ page }) => {
      await page.goto(path);

      await expect(page).toHaveURL(/\/$/);
      await expect(page.getByRole("link", { name: "Photograph your Rig" })).toBeVisible();
    });
  }

  test("an Admin still has the catalog tools", async ({ page }) => {
    await signIn(page, "Admin");
    await page.goto("/");
    await page
      .getByRole("navigation", { name: "Primary navigation" })
      .getByRole("link", { name: "Admin" })
      .click();

    await expect(page).toHaveURL(/\/admin$/);
    await expect(page.locator('a[href="/admin/modules"]').first()).toBeVisible();
  });
});
