/**
 * Buying credits, holding a plan and cancelling it: what shows comes from the API, and with
 * payments off nothing does. Leaving for the provider is mocked, since jsdom can't navigate.
 */
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { CommerceStatus } from "@/types/api";

const api = vi.hoisted(() => ({
  canonApi: {
    getCommerce: vi.fn(),
    startCreditCheckout: vi.fn(),
    startPlanCheckout: vi.fn(),
    cancelPlan: vi.fn(),
  },
}));
const leaveForCheckout = vi.hoisted(() => vi.fn());

vi.mock("@/lib/api", () => api);
vi.mock("@/lib/commerce", async (original) => ({
  ...(await original<typeof import("@/lib/commerce")>()),
  leaveForCheckout,
}));

import AccountCommerce, { CheckoutReturnNotice } from "./AccountCommerce";

const NOTHING: CommerceStatus = {
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
const CREDITS_PLAN = {
  tier: "core",
  credits_per_period: 25,
  unlimited: false,
  fair_use_exports_per_period: null,
};
const HELD = {
  plan: CREDITS_PLAN,
  status: "active",
  cancel_at_period_end: false,
  current_period_end: "2030-03-15T12:00:00Z",
  can_cancel: true,
};
const CHECKOUT = { data: { checkout_url: "https://checkout.example.test/cs_1" } };

function renderAt(status: CommerceStatus, path = "/account") {
  api.canonApi.getCommerce.mockResolvedValue({ data: status });
  return render(
    <MemoryRouter initialEntries={[path]}>
      <AccountCommerce />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  leaveForCheckout.mockReset();
});

afterEach(() => {
  vi.restoreAllMocks();
  Object.values(api.canonApi).forEach((mock) => mock.mockReset());
});

describe("with payments off", () => {
  it("shows nothing at all", async () => {
    const { container } = renderAt(NOTHING);
    await waitFor(() => expect(api.canonApi.getCommerce).toHaveBeenCalled());
    await waitFor(() => expect(container.textContent).toBe(""));
  });

  it("still shows a plan the person holds, and doesn't offer a cancel the API would refuse", async () => {
    renderAt({ ...NOTHING, subscription: { ...HELD, can_cancel: false } });
    expect(await screen.findByRole("heading", { name: "Your plan" })).toBeTruthy();
    expect(screen.getByText(/gives you: 25 credits each billing period/)).toBeTruthy();
    expect(screen.getByText(/Cancelling isn.t available right now/)).toBeTruthy();
    expect(screen.queryByRole("button", { name: /Cancel plan/ })).toBeNull();
  });
});

describe("buying credits", () => {
  it("states the charge and the test mode, then leaves for the provider's page", async () => {
    const user = userEvent.setup();
    api.canonApi.startCreditCheckout.mockResolvedValue(CHECKOUT);
    renderAt({ ...NOTHING, credit_offer: CREDIT_OFFER });

    expect(await screen.findByText(/You.ll pay \$6\.00 on the next page/)).toBeTruthy();
    expect(screen.getByText(/Test mode: no real charge/)).toBeTruthy();

    const field = screen.getByLabelText("Credits");
    await user.clear(field);
    await user.type(field, "50");
    expect(screen.getByText(/You.ll pay \$10\.00 on the next page/)).toBeTruthy();

    await user.click(screen.getByRole("button", { name: "Continue to checkout" }));

    await waitFor(() =>
      expect(leaveForCheckout).toHaveBeenCalledWith("https://checkout.example.test/cs_1"),
    );
    expect(api.canonApi.startCreditCheckout).toHaveBeenCalledWith(50);
  });

  it("won't send a quantity the checkout can't sell", async () => {
    const user = userEvent.setup();
    renderAt({ ...NOTHING, credit_offer: CREDIT_OFFER });

    const field = await screen.findByLabelText("Credits");
    await user.clear(field);
    await user.type(field, "1001");

    expect(screen.getByText("Enter a whole number from 1 to 1000.")).toBeTruthy();
    const submit = screen.getByRole("button", { name: "Continue to checkout" });
    expect((submit as HTMLButtonElement).disabled).toBe(true);
  });

  it("says why a checkout was refused, in words, and stays on the page", async () => {
    const user = userEvent.setup();
    api.canonApi.startCreditCheckout.mockRejectedValue({
      response: { status: 502, data: { detail: "PAYMENT_PROVIDER_ERROR" } },
    });
    renderAt({ ...NOTHING, credit_offer: CREDIT_OFFER });

    await user.click(await screen.findByRole("button", { name: "Continue to checkout" }));

    expect((await screen.findByRole("alert")).textContent).toMatch(
      /payment provider didn.t answer. Nothing was charged/,
    );
    expect(leaveForCheckout).not.toHaveBeenCalled();
  });

  it("won't follow a link that isn't https", async () => {
    const user = userEvent.setup();
    api.canonApi.startCreditCheckout.mockResolvedValue({
      data: { checkout_url: "javascript:alert(1)" },
    });
    renderAt({ ...NOTHING, credit_offer: CREDIT_OFFER });

    await user.click(await screen.findByRole("button", { name: "Continue to checkout" }));

    expect((await screen.findByRole("alert")).textContent).toMatch(/can.t open/);
    expect(leaveForCheckout).not.toHaveBeenCalled();
  });
});

describe("starting a plan", () => {
  it("lists what each plan gives, and leaves for the provider's page", async () => {
    const user = userEvent.setup();
    api.canonApi.startPlanCheckout.mockResolvedValue(CHECKOUT);
    renderAt({
      ...NOTHING,
      plan_offers: [
        CREDITS_PLAN,
        {
          tier: "studio",
          credits_per_period: 0,
          unlimited: true,
          fair_use_exports_per_period: 100,
        },
      ],
    });

    expect(await screen.findByRole("heading", { name: "Plans" })).toBeTruthy();
    expect(screen.getByText(/The next page shows the price/)).toBeTruthy();

    await user.click(
      screen.getByRole("button", {
        name: "Start the plan: Exports without credits, up to 100 each billing period",
      }),
    );

    await waitFor(() => expect(api.canonApi.startPlanCheckout).toHaveBeenCalledWith("studio"));
    await waitFor(() => expect(leaveForCheckout).toHaveBeenCalled());
  });
});

describe("cancelling a plan", () => {
  it("asks first, keeps the plan on no, and shows the end date on yes", async () => {
    const user = userEvent.setup();
    renderAt({ ...NOTHING, subscription: HELD });

    await user.click(await screen.findByRole("button", { name: "Cancel plan…" }));
    expect(screen.getByText(/You keep your credits/)).toBeTruthy();
    await user.click(screen.getByRole("button", { name: "Keep my plan" }));
    expect(api.canonApi.cancelPlan).not.toHaveBeenCalled();

    api.canonApi.cancelPlan.mockResolvedValue({ data: {} });
    api.canonApi.getCommerce.mockResolvedValue({
      data: {
        ...NOTHING,
        subscription: { ...HELD, cancel_at_period_end: true, can_cancel: false },
      },
    });
    await user.click(screen.getByRole("button", { name: "Cancel plan…" }));
    await user.click(screen.getByRole("button", { name: "Cancel at period end" }));

    await waitFor(() => expect(api.canonApi.cancelPlan).toHaveBeenCalledTimes(1));
    expect(await screen.findByText("Ends")).toBeTruthy();
    expect(screen.getByRole("status").textContent).toMatch(/end at the end of this period/);
    expect(screen.queryByRole("button", { name: /Cancel/ })).toBeNull();
  });

  it("moves focus to the safe choice, and back, since each step removes the pressed button", async () => {
    const user = userEvent.setup();
    renderAt({ ...NOTHING, subscription: HELD });

    await user.click(await screen.findByRole("button", { name: "Cancel plan…" }));
    expect(document.activeElement).toBe(screen.getByRole("button", { name: "Keep my plan" }));

    await user.click(screen.getByRole("button", { name: "Keep my plan" }));
    expect(document.activeElement).toBe(screen.getByRole("button", { name: "Cancel plan…" }));
  });

  it("says why a cancel was refused and keeps the plan showing", async () => {
    const user = userEvent.setup();
    api.canonApi.cancelPlan.mockRejectedValue({
      response: { status: 409, data: { detail: "SUBSCRIPTION_NOT_ACTIVE" } },
    });
    renderAt({ ...NOTHING, subscription: HELD });

    await user.click(await screen.findByRole("button", { name: "Cancel plan…" }));
    await user.click(screen.getByRole("button", { name: "Cancel at period end" }));

    expect((await screen.findByRole("alert")).textContent).toMatch(/can.t be cancelled/);
    expect(screen.getByRole("heading", { name: "Your plan" })).toBeTruthy();
  });

  it("shows the allowance beside the plan", async () => {
    renderAt({
      ...NOTHING,
      subscription: HELD,
      allowance: { exports_used: 12, export_cap: 100, period_end: "2030-03-15T12:00:00Z" },
    });
    expect(await screen.findByText("Exports this period")).toBeTruthy();
    expect(screen.getByText("12 of 100")).toBeTruthy();
  });
});

describe("the return from the provider", () => {
  it("shows the notice with payments off too", async () => {
    render(
      <MemoryRouter initialEntries={["/account?checkout=canceled"]}>
        <CheckoutReturnNotice />
      </MemoryRouter>,
    );
    expect((await screen.findByRole("status")).textContent).toBe(
      "Checkout canceled. Nothing was charged.",
    );
  });
});

describe("a load that fails", () => {
  it("says so and retries, so it never reads as nothing on offer", async () => {
    const user = userEvent.setup();
    api.canonApi.getCommerce.mockRejectedValueOnce({ response: { status: 500 } });
    api.canonApi.getCommerce.mockResolvedValue({
      data: { ...NOTHING, credit_offer: CREDIT_OFFER },
    });
    render(
      <MemoryRouter>
        <AccountCommerce />
      </MemoryRouter>,
    );

    await user.click(await screen.findByRole("button", { name: "Retry" }));

    expect(await screen.findByRole("heading", { name: "Buy credits" })).toBeTruthy();
    expect(screen.queryByText(/didn.t load/)).toBeNull();
  });
});
