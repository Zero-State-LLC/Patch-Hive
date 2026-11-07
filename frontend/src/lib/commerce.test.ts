import { describe, expect, it } from "vitest";
import {
  allowanceUsedUp,
  chargeCents,
  commerceRefusal,
  describePlan,
  describePlanStatus,
  exportRefusal,
  formatMoney,
  isHttpsUrl,
  parseCredits,
  returnNotice,
} from "./commerce";

const OFFER = { price_cents: 20, minimum_charge_cents: 500, currency: "usd", max_credits: 1000 };
const refusal = (status: number, detail: unknown) => ({ response: { status, data: { detail } } });

describe("what a checkout charges", () => {
  it("is the server's rule: the minimum, or the price per credit above it", () => {
    expect(chargeCents(1, OFFER)).toBe(500);
    expect(chargeCents(25, OFFER)).toBe(500);
    expect(chargeCents(30, OFFER)).toBe(600);
  });

  it("formats in the offer's currency", () => {
    expect(formatMoney(600, "usd", "en-US")).toBe("$6.00");
  });
});

describe("a quantity of credits", () => {
  it.each([
    ["30", 30],
    ["1", 1],
    ["1000", 1000],
    [" 7 ", 7],
  ])("reads %j as %j", (text, credits) => {
    expect(parseCredits(text, OFFER)).toBe(credits);
  });

  it.each(["", "0", "1001", "-3", "2.5", "1e3", "ten"])("refuses %j", (text) => {
    expect(parseCredits(text, OFFER)).toBeNull();
  });
});

describe("a plan, in words", () => {
  it("says what it gives", () => {
    const plan = { tier: "core", unlimited: false, fair_use_exports_per_period: null };
    expect(describePlan({ ...plan, credits_per_period: 25 })).toBe(
      "25 credits each billing period",
    );
  });

  it("says an unlimited plan has a limit", () => {
    expect(
      describePlan({
        tier: "studio",
        credits_per_period: 0,
        unlimited: true,
        fair_use_exports_per_period: 100,
      }),
    ).toBe("Exports without credits, up to 100 each billing period");
  });

  it("says a provider status plainly, and never prints an unknown one", () => {
    expect(describePlanStatus("past_due")).toBe("Payment overdue");
    expect(describePlanStatus("something_new")).toBe("Not stated");
  });
});

describe("an allowance", () => {
  const allowance = (exports_used: number) => ({
    exports_used,
    export_cap: 100,
    period_end: "2030-03-15T00:00:00Z",
  });

  it("is used up at the cap, and past it", () => {
    expect(allowanceUsedUp(allowance(99))).toBe(false);
    expect(allowanceUsedUp(allowance(100))).toBe(true);
    expect(allowanceUsedUp(allowance(101))).toBe(true);
  });
});

describe("a refusal, in words", () => {
  it("names a known checkout code and never prints it", () => {
    const text = commerceRefusal(refusal(409, "SUBSCRIPTION_EXISTS"));
    expect(text).toBe("You already have a plan. Nothing was charged.");
  });

  it("falls back to the general reason for an unknown code", () => {
    expect(commerceRefusal(refusal(500, "SOMETHING_ELSE"))).not.toMatch(/SOMETHING_ELSE/);
  });

  it("explains an export with no credits, and a used-up allowance", () => {
    expect(exportRefusal(refusal(402, "INSUFFICIENT_CREDITS"))).toMatch(/Not enough credits/);
    expect(exportRefusal(refusal(429, "FAIR_USE_CAP_REACHED"))).toMatch(
      /used this period's exports, so nothing was charged/,
    );
  });

  it("falls back for an export that failed with no reason", () => {
    expect(exportRefusal(new Error("offline"))).toBe("The export failed. Nothing was charged.");
  });
});

describe("coming back from the provider", () => {
  const notice = (query: string) => returnNotice(new URLSearchParams(query));

  it.each(["checkout=canceled", "subscription=canceled"])(
    "%s says nothing was charged",
    (query) => {
      expect(notice(query)).toEqual({
        text: "Checkout canceled. Nothing was charged.",
        good: false,
      });
    },
  );

  it("doesn't claim credits or a plan before the payment is confirmed", () => {
    expect(notice("checkout=success")?.text).toMatch(/once the payment is confirmed/);
    expect(notice("subscription=success")?.text).toMatch(/once the payment is confirmed/);
  });

  it.each(["", "checkout=other", "tab=exports"])("says nothing for %j", (query) => {
    expect(notice(query)).toBeNull();
  });
});

describe("the link to the provider", () => {
  it.each(["https://checkout.stripe.com/c/pay/cs_test"])("may be %s", (url) => {
    expect(isHttpsUrl(url)).toBe(true);
  });

  it.each([
    "http://checkout.example.test",
    "javascript:alert(1)",
    "data:text/html,x",
    "/account",
    "",
  ])("may not be %j", (url) => {
    expect(isHttpsUrl(url)).toBe(false);
  });
});
