/**
 * PowerMeters — placement draw per rail against the case's capacity. A rail a module does not
 * state is counted as unknown, never 0, so a total with unknowns is a lower bound.
 */
import type { CSSProperties } from "react";
import { railMeter, type PowerSummary, type RailKey, type RailMeter } from "@/lib/powerBudget";

/** The case's stated capacity per rail; a missing number leaves that meter unscaled. */
export interface CaseRails {
  power_12v_ma?: number | null;
  power_neg12v_ma?: number | null;
  power_5v_ma?: number | null;
}

const RAILS: { rail: string; key: RailKey; capacity: keyof CaseRails }[] = [
  { rail: "+12V", key: "p12", capacity: "power_12v_ma" },
  { rail: "−12V", key: "n12", capacity: "power_neg12v_ma" },
  { rail: "+5V", key: "p5", capacity: "power_5v_ma" },
];

const RAIL_LABEL: Record<RailKey, string> = { p12: "+12", n12: "−12", p5: "+5" };

/** Under the figure: what is left, and when unknowns make the figure a lower bound. */
function meterNote(m: RailMeter): string {
  const unknown = m.unknown ? `${m.unknown} unknown, so a lower bound` : "";
  if (m.capacity == null || m.headroom == null) {
    return sentence([unknown, "case capacity unspecified"]);
  }
  const left =
    m.headroom < 0
      ? `${-m.headroom}mA over budget`
      : `${m.unknown ? "at most " : ""}${m.headroom}mA headroom`;
  return sentence([unknown, left]);
}

function sentence(parts: string[]): string {
  const s = parts.filter(Boolean).join("; ");
  return s.charAt(0).toUpperCase() + s.slice(1);
}

export default function PowerMeters({
  summary,
  caseRails,
}: {
  summary: PowerSummary;
  /** Omitted until the rig's case has loaded; the meters need its capacity. */
  caseRails?: CaseRails | null;
}) {
  const meters = caseRails
    ? RAILS.map((r) => ({ ...r, ...railMeter(summary[r.key], caseRails[r.capacity]) }))
    : [];
  const unknownRails = RAILS.map((r) => ({ key: r.key, n: summary[r.key].unknown })).filter(
    (r) => r.n > 0,
  );

  return (
    <div className="power-rail-panel" role="group" aria-label="Power rail usage" aria-live="polite">
      <p className="muted">
        Placement power: <strong>{summary.fullyKnown}</strong> of {summary.total} modules state
        every rail
        {summary.total
          ? `. Known draw: +12 ${summary.p12.known}mA, −12 ${summary.n12.known}mA, +5 ${summary.p5.known}mA`
          : ""}
      </p>
      {meters.length > 0 ? (
        <div className="power-rail-meters">
          {meters.map((rail) => (
            <div key={rail.rail} className="power-rail-meters__row">
              <div className="power-meter__head">
                <span className={`status-chip status-chip--${rail.tone}`}>{rail.rail}</span>
                <span className="power-meter__figure">
                  {rail.capacity == null ? `${rail.draw}mA` : `${rail.draw}/${rail.capacity}mA`}
                </span>
              </div>
              <div
                className="usage-bar power-meter__bar"
                role="meter"
                aria-valuemin={0}
                aria-valuemax={rail.capacity ?? 0}
                aria-valuenow={rail.draw}
                aria-valuetext={rail.label}
                aria-label={`${rail.rail} power usage`}
              >
                <div
                  className={`usage-bar__fill usage-bar__fill--${rail.tone}`}
                  style={
                    {
                      // No capacity to scale against: a sliver says "some draw", not how much.
                      "--fill": rail.capacity == null ? (rail.draw > 0 ? 0.08 : 0) : rail.pct / 100,
                    } as CSSProperties
                  }
                />
              </div>
              <span className="power-meter__note">{meterNote(rail)}</span>
            </div>
          ))}
        </div>
      ) : null}
      {unknownRails.length > 0 ? (
        <p className="status status-warning">
          Unknown draw, not assumed:{" "}
          {unknownRails.map((r) => `${RAIL_LABEL[r.key]} ${r.n}`).join(", ")}. Totals on those rails
          are lower bounds.
        </p>
      ) : null}
    </div>
  );
}
