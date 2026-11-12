/**
 * Buying credits, holding a plan and cancelling it, on the Account page (spec 004 P1, P2, P5). The
 * API decides what shows. With payments off, the default, this renders nothing unless the person
 * already holds a plan or has just come back from checkout.
 */
import { useEffect, useId, useRef, useState } from "react";
import type { FormEvent } from "react";
import { useSearchParams } from "react-router-dom";
import LoadFailure from "@/components/LoadFailure";
import { ListSkeleton } from "@/components/Skeletons";
import { canonApi } from "@/lib/api";
import {
  allowanceCount,
  chargeCents,
  commerceRefusal,
  describePlan,
  describePlanStatus,
  formatMoney,
  isHttpsUrl,
  leaveForCheckout,
  parseCredits,
  returnNotice,
} from "@/lib/commerce";
import { formatDate } from "@/lib/format";
import type { CommerceCreditOffer, CommerceStatus, CommerceSubscription } from "@/types/api";

const NO_LINK = "The payment provider sent a link PatchHive can't open. Nothing was charged.";

function Failure({ text }: { text: string }) {
  return (
    <p role="alert" className="status status-warning">
      {text}
    </p>
  );
}

function BuyCredits({ offer, testMode }: { offer: CommerceCreditOffer; testMode: boolean }) {
  const id = useId();
  const [text, setText] = useState("30");
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState("");
  const credits = parseCredits(text, offer);

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    if (credits == null || busy) return;
    setBusy(true);
    setFailure("");
    try {
      const { data } = await canonApi.startCreditCheckout(credits);
      if (!isHttpsUrl(data.checkout_url)) {
        setFailure(NO_LINK);
        setBusy(false);
        return;
      }
      leaveForCheckout(data.checkout_url);
    } catch (error: unknown) {
      setFailure(commerceRefusal(error));
      setBusy(false);
    }
  };

  return (
    <section className="ops-section" aria-labelledby={`${id}-heading`}>
      <h2 id={`${id}-heading`}>Buy credits</h2>
      <p className="muted">
        Credits don&apos;t expire. Each costs {formatMoney(offer.price_cents, offer.currency)}, with
        a {formatMoney(offer.minimum_charge_cents, offer.currency)} minimum.
        {testMode ? " Test mode: no real charge." : ""}
      </p>
      <form className="ops-form" onSubmit={(event) => void handleSubmit(event)}>
        <label className="field">
          Credits
          <input
            type="number"
            inputMode="numeric"
            min={1}
            max={offer.max_credits}
            step={1}
            value={text}
            onChange={(event) => setText(event.target.value)}
            aria-describedby={`${id}-charge`}
          />
        </label>
        <p id={`${id}-charge`} className="muted">
          {credits == null
            ? `Enter a whole number from 1 to ${offer.max_credits}.`
            : `You'll pay ${formatMoney(chargeCents(credits, offer), offer.currency)} on the next page.`}
        </p>
        <button className="button button-primary" type="submit" disabled={credits == null || busy}>
          {busy ? "Opening checkout…" : "Continue to checkout"}
        </button>
      </form>
      {failure ? <Failure text={failure} /> : null}
    </section>
  );
}

function CurrentPlan({
  subscription,
  status,
  onChanged,
}: {
  subscription: CommerceSubscription;
  status: CommerceStatus;
  onChanged: () => void;
}) {
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState("");
  const endDate = formatDate(subscription.current_period_end);
  const keepButton = useRef<HTMLButtonElement>(null);
  const cancelButton = useRef<HTMLButtonElement>(null);
  const opened = useRef(false);

  // Each step removes the button just pressed, so focus goes to the safe choice in the next one.
  useEffect(() => {
    if (confirming) {
      opened.current = true;
      keepButton.current?.focus();
    } else if (opened.current) {
      cancelButton.current?.focus();
    }
  }, [confirming]);

  const handleCancel = async () => {
    setBusy(true);
    setFailure("");
    try {
      await canonApi.cancelPlan();
      setConfirming(false);
      onChanged();
    } catch (error: unknown) {
      setFailure(commerceRefusal(error));
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      {subscription.plan ? <p>Your plan gives you: {describePlan(subscription.plan)}.</p> : null}
      <dl className="readout">
        <div>
          <dt>Status</dt>
          <dd>{describePlanStatus(subscription.status)}</dd>
        </div>
        <div>
          <dt>{subscription.cancel_at_period_end ? "Ends" : "Next billing date"}</dt>
          <dd>{endDate}</dd>
        </div>
        {status.allowance ? (
          <div>
            <dt>Exports this period</dt>
            <dd>{allowanceCount(status.allowance)}</dd>
          </div>
        ) : null}
      </dl>
      {subscription.cancel_at_period_end ? (
        <p className="muted">Your plan ends on {endDate}. You keep your credits.</p>
      ) : subscription.can_cancel ? (
        confirming ? (
          <>
            <p>
              Your plan stays until {endDate}, and you won&apos;t be billed again. You keep your
              credits.
            </p>
            <div className="toolbar">
              <button
                className="button button-primary"
                type="button"
                onClick={() => void handleCancel()}
                disabled={busy}
              >
                {busy ? "Cancelling…" : "Cancel at period end"}
              </button>
              <button
                ref={keepButton}
                className="button button-secondary"
                type="button"
                onClick={() => setConfirming(false)}
                disabled={busy}
              >
                Keep my plan
              </button>
            </div>
          </>
        ) : (
          <div className="toolbar">
            <button
              ref={cancelButton}
              className="button button-secondary"
              type="button"
              onClick={() => setConfirming(true)}
            >
              Cancel plan…
            </button>
          </div>
        )
      ) : (
        <p className="muted">Cancelling isn&apos;t available right now.</p>
      )}
      {failure ? <Failure text={failure} /> : null}
    </>
  );
}

function PlanOffers({ status }: { status: CommerceStatus }) {
  const [busyTier, setBusyTier] = useState<string | null>(null);
  const [failure, setFailure] = useState("");

  const handleStart = async (tier: string) => {
    setBusyTier(tier);
    setFailure("");
    try {
      const { data } = await canonApi.startPlanCheckout(tier);
      if (!isHttpsUrl(data.checkout_url)) {
        setFailure(NO_LINK);
        setBusyTier(null);
        return;
      }
      leaveForCheckout(data.checkout_url);
    } catch (error: unknown) {
      setFailure(commerceRefusal(error));
      setBusyTier(null);
    }
  };

  return (
    <>
      <p className="muted">
        A plan bills each period until you cancel. The next page shows the price.
        {status.test_mode ? " Test mode: no real charge." : ""}
      </p>
      <div className="ops-table-wrap">
        <table className="data-table">
          <thead>
            <tr>
              <th>Gives you</th>
              <th>Start</th>
            </tr>
          </thead>
          <tbody>
            {status.plan_offers.map((plan) => (
              <tr key={plan.tier}>
                <td>{describePlan(plan)}</td>
                <td>
                  <button
                    className="button button-secondary"
                    type="button"
                    onClick={() => void handleStart(plan.tier)}
                    disabled={busyTier != null}
                    aria-label={`Start the plan: ${describePlan(plan)}`}
                  >
                    {busyTier === plan.tier ? "Opening checkout…" : "Start this plan"}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {failure ? <Failure text={failure} /> : null}
    </>
  );
}

/** What the provider's return link means, first on the page. Shows with payments off too. */
export function CheckoutReturnNotice() {
  const [params] = useSearchParams();
  const notice = returnNotice(params);
  if (!notice) return null;
  return (
    <p role="status" className={`status account-notice${notice.good ? " status-success" : ""}`}>
      {notice.text}
    </p>
  );
}

export default function AccountCommerce() {
  const headingId = useId();
  const [status, setStatus] = useState<CommerceStatus | null>(null);
  const [loadError, setLoadError] = useState<unknown>(null);
  const [attempt, setAttempt] = useState(0);
  const [cancelled, setCancelled] = useState(false);

  useEffect(() => {
    let current = true;
    setLoadError(null);
    canonApi
      .getCommerce()
      .then((response) => {
        if (current) setStatus(response.data);
      })
      .catch((error: unknown) => {
        if (current) setLoadError(error);
      });
    return () => {
      current = false;
    };
  }, [attempt]);

  const hasPlanSection = Boolean(status?.subscription || status?.plan_offers.length);

  return (
    <>
      {loadError ? (
        <section className="ops-section" aria-labelledby={`${headingId}-load`}>
          <h2 id={`${headingId}-load`}>Your plan</h2>
          <LoadFailure
            what="Your plan and credit options"
            error={loadError}
            onRetry={() => setAttempt((n) => n + 1)}
          />
        </section>
      ) : !status && attempt > 0 ? (
        <ListSkeleton label="Loading your plan…" rows={1} />
      ) : null}
      {status?.credit_offer ? (
        <BuyCredits offer={status.credit_offer} testMode={status.test_mode} />
      ) : null}
      {status && hasPlanSection ? (
        <section className="ops-section" aria-labelledby={`${headingId}-plan`}>
          <h2 id={`${headingId}-plan`}>{status.subscription ? "Your plan" : "Plans"}</h2>
          {cancelled ? (
            <p role="status" className="status status-success">
              Done. Your plan will end at the end of this period.
            </p>
          ) : null}
          {status.subscription ? (
            <CurrentPlan
              subscription={status.subscription}
              status={status}
              onChanged={() => {
                setCancelled(true);
                setAttempt((n) => n + 1);
              }}
            />
          ) : (
            <PlanOffers status={status} />
          )}
        </section>
      ) : null}
    </>
  );
}
