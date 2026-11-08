/**
 * The words and sums behind buying credits and holding a plan (spec 004). The API decides what's
 * on offer and what things cost; this only says it plainly. Copy here follows COPY_COMPLIANCE.md,
 * so a plan is named by what it gives.
 */
import { failureReason } from "@/lib/loadError";
import { formatDate } from "@/lib/format";
import type { CommerceAllowance, CommerceCreditOffer, CommercePlan } from "@/types/api";

/** What the server charges: `max(minimum, credits * price)` (FR-006). */
export function chargeCents(credits: number, offer: CommerceCreditOffer): number {
  return Math.max(offer.minimum_charge_cents, credits * offer.price_cents);
}

export function formatMoney(cents: number, currency: string, locale?: string): string {
  return new Intl.NumberFormat(locale, { style: "currency", currency }).format(cents / 100);
}

/** A whole number of credits this checkout can sell, or null. */
export function parseCredits(text: string, offer: CommerceCreditOffer): number | null {
  if (!/^\d+$/.test(text.trim())) return null;
  const credits = Number(text);
  return credits >= 1 && credits <= offer.max_credits ? credits : null;
}

export function describePlan(plan: CommercePlan): string {
  if (plan.unlimited) {
    return `Exports without credits, up to ${plan.fair_use_exports_per_period ?? 0} each billing period`;
  }
  return `${plan.credits_per_period} credits each billing period`;
}

const PLAN_STATUS: Record<string, string> = {
  active: "Active",
  trialing: "Trial",
  past_due: "Payment overdue",
  unpaid: "Unpaid",
  paused: "Paused",
  incomplete: "Waiting for payment",
};

export function describePlanStatus(status: string): string {
  return PLAN_STATUS[status] ?? "Not stated";
}

/** The short form, for a readout labelled "Exports this period". */
export function allowanceCount(allowance: CommerceAllowance): string {
  return `${allowance.exports_used} of ${allowance.export_cap}`;
}

export function allowanceUsage(allowance: CommerceAllowance): string {
  return `${allowanceCount(allowance)} exports used`;
}

export function allowanceUsedUp(allowance: CommerceAllowance): boolean {
  return allowance.exports_used >= allowance.export_cap;
}

export function allowanceReset(allowance: CommerceAllowance): string {
  return `You've used this period's exports. They reset on ${formatDate(allowance.period_end)}.`;
}

const creditWords = (n: number) => `${n} credit${n === 1 ? "" : "s"}`;

/** An export's price, shown before the owner commits (spec 009 story 29), and whether it can be
 * asked for. A plan's allowance pays instead of credits while the period has exports left. The
 * server sets the price; with no price or no balance to show, nothing is asked for. */
export function exportOffer({
  allowance,
  credits,
  cost,
}: {
  allowance: CommerceAllowance | null;
  credits: number | null;
  cost: number | null;
}): { canExport: boolean; button: string; price: string } {
  const plain = "Export the Patch Book";
  if (allowance) {
    return allowanceUsedUp(allowance)
      ? { canExport: false, button: plain, price: allowanceReset(allowance) }
      : {
          canExport: true,
          button: plain,
          price: `Your plan covers this export (${allowanceCount(allowance)} used this period).`,
        };
  }
  if (cost == null)
    return { canExport: false, button: plain, price: "The export's price didn't load." };
  if (cost === 0) return { canExport: true, button: plain, price: "This export is free." };
  const button = `Export for ${creditWords(cost)}`;
  if (credits == null) {
    return {
      canExport: false,
      button,
      price: `This export costs ${creditWords(cost)}. Your balance didn't load.`,
    };
  }
  return credits >= cost
    ? {
        canExport: true,
        button,
        price: `This export costs ${creditWords(cost)}. You have ${credits}, so ${credits - cost} will be left.`,
      }
    : {
        canExport: false,
        button,
        price: `This export costs ${creditWords(cost)}, and you have ${credits}.`,
      };
}

const REFUSALS: Record<string, string> = {
  PAYMENTS_DISABLED: "Buying isn't open right now. Nothing was charged.",
  PRODUCTION_PAYMENTS_DISABLED: "Buying isn't open right now. Nothing was charged.",
  STRIPE_SECRET_KEY_MISSING: "Checkout isn't available right now. Nothing was charged.",
  LIVE_KEY_REFUSED: "Checkout isn't available right now. Nothing was charged.",
  PAYMENT_PROVIDER_ERROR:
    "The payment provider didn't answer. Nothing was charged. Try again in a moment.",
  SUBSCRIPTION_EXISTS: "You already have a plan. Nothing was charged.",
  SUBSCRIPTION_CHECKOUT_OPEN:
    "You have a checkout open for another plan. Finish it, or try again after it expires.",
  SUBSCRIPTION_PRICE_MISSING: "This plan isn't available right now. Nothing was charged.",
  SUBSCRIPTION_NOT_FOUND: "You don't have a plan to cancel.",
  SUBSCRIPTION_NOT_ACTIVE: "This plan can't be cancelled while it's in this state.",
};

/** Why a checkout or a cancel was refused, in words. */
export function commerceRefusal(error: unknown): string {
  const detail = (error as { response?: { data?: { detail?: unknown } } } | null)?.response?.data
    ?.detail;
  if (typeof detail === "string" && REFUSALS[detail]) return REFUSALS[detail];
  return failureReason(error);
}

/** Why an export was refused, in words. */
export function exportRefusal(error: unknown): string {
  const response = (error as { response?: { data?: { detail?: unknown }; status?: number } } | null)
    ?.response;
  if (response?.status === 402) return "Not enough credits for this export. Nothing was charged.";
  const detail = response?.data?.detail;
  if (detail === "FAIR_USE_CAP_REACHED") {
    return "You've used this period's exports, so nothing was charged. They reset when your next period starts.";
  }
  return typeof detail === "string" && detail ? detail : "The export failed. Nothing was charged.";
}

/** What the provider's return link means, or null for any other visit to the page. */
export function returnNotice(params: URLSearchParams): { text: string; good: boolean } | null {
  const canceled = { text: "Checkout canceled. Nothing was charged.", good: false };
  const credits = params.get("checkout");
  if (credits === "success") {
    return {
      text: "Thanks. Your credits appear here once the payment is confirmed. Reload this page to check.",
      good: true,
    };
  }
  if (credits === "canceled") return canceled;
  const plan = params.get("subscription");
  if (plan === "success") {
    return {
      text: "Thanks. Your plan appears here once the payment is confirmed. Reload this page to check.",
      good: true,
    };
  }
  return plan === "canceled" ? canceled : null;
}

/** Only a provider's own https page may take the visitor away from PatchHive. */
export function isHttpsUrl(value: string): boolean {
  try {
    return new URL(value).protocol === "https:";
  } catch {
    return false;
  }
}

/** Leaves for the provider's checkout page. Separate so tests can watch it. */
export function leaveForCheckout(url: string): void {
  window.location.assign(url);
}
