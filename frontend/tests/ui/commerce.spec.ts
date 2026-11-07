/**
 * Buying credits, holding a plan and cancelling it, on the Account page in a browser. Every API
 * call is mocked, and the provider's page is a stub, so nothing here reaches a payment provider.
 */
import { expect, test, type Page } from "@playwright/test";

const USER = {
  id: 1,
  username: "e2e-user",
  email: "e2e-user@example.com",
  role: "User",
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};
const NOTHING = {
  test_mode: true,
  credit_offer: null,
  plan_offers: [],
  subscription: null,
  allowance: null,
};
const CREDIT_OFFER = {
  price_cents: 20,
  minimum_charge_cents: 500,
  currency: "usd",
  max_credits: 1000,
};
const CHECKOUT_URL = "https://checkout.example.test/cs_e2e";

async function mockAccount(page: Page, commerce: unknown) {
  await page.route("**/api/**", (route) =>
    route.fulfill({ status: 404, json: { detail: "not mocked" } }),
  );
  await page.route("**/api/community/auth/refresh", (route) =>
    route.fulfill({ json: { access_token: "e2e-token", token_type: "bearer", user: USER } }),
  );
  await page.route("**/api/community/users/me", (route) => route.fulfill({ json: USER }));
  await page.route("**/api/canon/credits/summary", (route) =>
    route.fulfill({ json: { balance: 3, entries: [] } }),
  );
  await page.route("**/api/canon/exports", (route) => route.fulfill({ json: [] }));
  await page.route("**/api/canon/commerce", (route) => route.fulfill({ json: commerce }));
  await page.route(`${CHECKOUT_URL}**`, (route) =>
    route.fulfill({ contentType: "text/html", body: "<h1>Provider checkout stub</h1>" }),
  );
}

async function openAccount(page: Page, path = "/account") {
  await page.goto(path);
  await expect(page.getByRole("heading", { level: 1, name: "Credits & profile" })).toBeVisible();
}

test("with payments off the page offers nothing to buy", async ({ page }) => {
  await mockAccount(page, NOTHING);
  await openAccount(page);
  await expect(page.getByRole("heading", { name: "Exports" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Buy credits" })).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "Plans" })).toHaveCount(0);
});

test("buying credits states the charge and goes to the provider's page", async ({ page }) => {
  await mockAccount(page, { ...NOTHING, credit_offer: CREDIT_OFFER });
  let body: unknown = null;
  await page.route("**/api/canon/checkout/credits", (route) => {
    body = route.request().postDataJSON();
    return route.fulfill({ status: 201, json: { checkout_url: CHECKOUT_URL } });
  });
  await openAccount(page);

  await expect(page.getByText("You'll pay $6.00 on the next page.")).toBeVisible();
  await page.getByRole("spinbutton", { name: "Credits" }).fill("50");
  await expect(page.getByText("You'll pay $10.00 on the next page.")).toBeVisible();
  await page.getByRole("button", { name: "Continue to checkout" }).click();

  await expect(page.getByRole("heading", { name: "Provider checkout stub" })).toBeVisible();
  expect(body).toEqual({ credits: 50 });
});

test("coming back after cancelling at the provider says nothing was charged", async ({ page }) => {
  await mockAccount(page, { ...NOTHING, credit_offer: CREDIT_OFFER });
  await openAccount(page, "/account?checkout=canceled");
  await expect(page.getByText("Checkout canceled. Nothing was charged.")).toBeVisible();
});

test("cancelling a plan asks first and shows when it ends", async ({ page }) => {
  const held = {
    plan: {
      tier: "core",
      credits_per_period: 25,
      unlimited: false,
      fair_use_exports_per_period: null,
    },
    status: "active",
    cancel_at_period_end: false,
    current_period_end: "2030-03-15T12:00:00Z",
    can_cancel: true,
  };
  let commerce: unknown = { ...NOTHING, subscription: held };
  await mockAccount(page, commerce);
  await page.route("**/api/canon/commerce", (route) => route.fulfill({ json: commerce }));
  await page.route("**/api/canon/subscription/cancel", (route) => {
    commerce = {
      ...NOTHING,
      subscription: { ...held, cancel_at_period_end: true, can_cancel: false },
    };
    return route.fulfill({
      json: { cancel_at_period_end: true, current_period_end: held.current_period_end },
    });
  });
  await openAccount(page);

  await expect(page.getByText("25 credits each billing period")).toBeVisible();
  await page.getByRole("button", { name: "Cancel plan…" }).click();
  await expect(page.getByText(/won't be billed again/)).toBeVisible();
  await page.getByRole("button", { name: "Cancel at period end" }).click();

  await expect(page.getByRole("status")).toContainText("end at the end of this period");
  await expect(page.getByText(/You keep your credits/)).toBeVisible();
  await expect(page.getByRole("button", { name: /Cancel/ })).toHaveCount(0);
});

test("the offers fit a phone with no sideways scroll", async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 720 });
  await mockAccount(page, {
    ...NOTHING,
    credit_offer: CREDIT_OFFER,
    plan_offers: [
      {
        tier: "studio",
        credits_per_period: 0,
        unlimited: true,
        fair_use_exports_per_period: 100,
      },
    ],
  });
  await openAccount(page);
  await expect(page.getByRole("heading", { name: "Plans" })).toBeVisible();
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
  expect(overflow).toBeLessThanOrEqual(0);
});
