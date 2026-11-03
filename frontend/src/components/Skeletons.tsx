/**
 * Skeletons — placeholders in the shape of what is loading, so a screen never reads as empty
 * before its data arrives. The shapes are aria-hidden; each carries one visually hidden status
 * line naming what is coming.
 */
import { useEffect, useState } from "react";
import type { CSSProperties } from "react";

const ANNOUNCE_DELAY_MS = 150;

/** Title bar widths, in characters, so rows do not read as a ruled grid. */
const TITLE_WIDTHS = [18, 26, 14, 22, 30, 16];

/** Faceplate widths in HP for each skeleton row of an 84HP rail. */
const PLATE_ROWS = [
  [12, 8, 16, 4, 10, 14, 6],
  [20, 6, 10, 8, 14, 12],
  [8, 14, 4, 18, 10, 12],
];

/**
 * A live region that mounts empty and fills a beat later: screen readers often skip a region
 * that arrives already filled. A load that ends sooner than that is never announced.
 */
function LoadingStatus({ label }: { label: string }) {
  const [text, setText] = useState("");
  useEffect(() => {
    const timer = window.setTimeout(() => setText(label), ANNOUNCE_DELAY_MS);
    return () => window.clearTimeout(timer);
  }, [label]);
  return (
    <span className="visually-hidden" role="status">
      {text}
    </span>
  );
}

/** List rows: a title over a shorter meta line, as side lists and patch rows draw them. */
export function ListSkeleton({ label, rows = 4 }: { label: string; rows?: number }) {
  return (
    <div className="list-skeleton">
      <LoadingStatus label={label} />
      <ul aria-hidden="true">
        {Array.from({ length: rows }, (_, i) => (
          <li key={i}>
            <span
              className="skeleton"
              style={{ "--w": TITLE_WIDTHS[i % TITLE_WIDTHS.length] } as CSSProperties}
            />
            <span className="skeleton" />
          </li>
        ))}
      </ul>
    </div>
  );
}

/** A rig's rail: rows of faceplates at plausible widths. */
export function RailSkeleton({ label, rows = 2 }: { label: string; rows?: number }) {
  return (
    <div className="rail-skeleton">
      <LoadingStatus label={label} />
      <div aria-hidden="true">
        {Array.from({ length: rows }, (_, r) => (
          <div key={r} className="rail-skeleton__row">
            {PLATE_ROWS[r % PLATE_ROWS.length].map((hp, i) => (
              <span key={i} className="skeleton" style={{ "--hp": hp } as CSSProperties} />
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}

/** The rig's patch path: three jacks on one cable, each over a stage name. */
export function ChainSkeleton({ label }: { label: string }) {
  return (
    <div className="chain-skeleton">
      <LoadingStatus label={label} />
      <ol aria-hidden="true">
        {[0, 1, 2].map((i) => (
          <li key={i}>
            <span className="skeleton chain-skeleton__jack" />
            <span className="skeleton chain-skeleton__name" />
          </li>
        ))}
      </ol>
    </div>
  );
}

/** A readout figure while its number loads. Pass a label on one figure per region, not each. */
export function ReadoutSkeleton({ label }: { label?: string }) {
  return (
    <span className="readout-skeleton">
      {label ? <LoadingStatus label={label} /> : null}
      <span className="skeleton" aria-hidden="true" />
    </span>
  );
}
