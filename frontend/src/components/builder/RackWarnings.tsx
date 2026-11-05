import type { RackValidationWarning } from "@/types/api";

/** A retired module has its own banner in PlacementStep, with the alternatives. */
const SHOWN_ELSEWHERE = new Set(["MODULE_TOMBSTONED"]);

/** The advisories the rig's own read carries, such as an in-rack supply that isn't counted. */
export default function RackWarnings({ warnings }: { warnings?: RackValidationWarning[] }) {
  const shown = (warnings ?? []).filter((w) => !SHOWN_ELSEWHERE.has(w.details?.code ?? ""));
  if (shown.length === 0) return null;
  return (
    <div className="status status-warning builder-warnings" role="status">
      <ul>
        {shown.map((w) => (
          <li key={w.details?.code ?? w.message}>{w.message}</li>
        ))}
      </ul>
    </div>
  );
}
