/**
 * LoadFailure — what a page shows when its data didn't arrive: what is missing, why in one
 * sentence, and Retry. It is an alert, so it is announced, and it never reads as an empty result.
 */
import { failureReason } from "@/lib/loadError";

export default function LoadFailure({
  what,
  error,
  onRetry,
}: {
  /** What didn't load, as the start of a sentence: "Your credits", "This rig's runs". */
  what: string;
  error: unknown;
  onRetry?: () => void;
}) {
  return (
    <div className="screen-state" role="alert">
      <p className="status status-danger">
        {what} didn&apos;t load. {failureReason(error)}
      </p>
      {onRetry ? (
        <button className="button button-secondary" type="button" onClick={onRetry}>
          Retry
        </button>
      ) : null}
    </div>
  );
}
