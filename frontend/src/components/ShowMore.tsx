/**
 * ShowMore — the next page of a list the API pages, under the rows already shown. A page that
 * didn't load says so beside the button, which then asks again.
 */
import { failureReason } from "@/lib/loadError";

export default function ShowMore({
  shown,
  total,
  noun,
  loading,
  error,
  onMore,
}: {
  shown: number;
  total: number;
  /** The rows, plural: "patches", "rigs". */
  noun: string;
  loading: boolean;
  error: unknown;
  onMore: () => void;
}) {
  if (shown >= total) return null;
  return (
    <div className="show-more">
      <button className="button button-secondary" type="button" disabled={loading} onClick={onMore}>
        {loading ? `Loading more ${noun}…` : `Show more ${noun}`}
      </button>
      {error ? (
        <p className="status status-danger" role="alert">
          More {noun} didn&apos;t load. {failureReason(error)}
        </p>
      ) : null}
    </div>
  );
}
