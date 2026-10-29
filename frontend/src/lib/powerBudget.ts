/**
 * Per-rail power totals for placed modules. A rail a module does not state is unknown,
 * never 0 (spec 003 FR-022), and unknowns are counted per rail: a module with +12V
 * known but -12V missing still adds its +12V draw.
 */

export type RailKey = "p12" | "n12" | "p5";

export interface PowerSpec {
  power_12v_ma?: number | null;
  power_neg12v_ma?: number | null;
  power_5v_ma?: number | null;
}

export interface RailTotal {
  /** Sum of the known draws: a lower bound when `unknown` > 0. */
  known: number;
  /** Modules on this rail with no stated draw (or not loaded). */
  unknown: number;
}

export type PowerSummary = Record<RailKey, RailTotal> & { total: number; fullyKnown: number };

const FIELDS: Record<RailKey, keyof PowerSpec> = {
  p12: "power_12v_ma",
  n12: "power_neg12v_ma",
  p5: "power_5v_ma",
};

export function summarizePower(modules: (PowerSpec | undefined)[]): PowerSummary {
  const summary: PowerSummary = {
    p12: { known: 0, unknown: 0 },
    n12: { known: 0, unknown: 0 },
    p5: { known: 0, unknown: 0 },
    total: modules.length,
    fullyKnown: 0,
  };
  for (const mod of modules) {
    let complete = true;
    for (const rail of Object.keys(FIELDS) as RailKey[]) {
      const value = mod?.[FIELDS[rail]];
      if (value == null) {
        summary[rail].unknown += 1;
        complete = false;
      } else {
        summary[rail].known += value;
      }
    }
    if (complete) summary.fullyKnown += 1;
  }
  return summary;
}

export type RailTone = "success" | "warning" | "danger" | "neutral";

export interface RailMeter {
  draw: number;
  unknown: number;
  capacity: number | null;
  /** capacity minus known draw: an upper bound when `unknown` > 0. */
  headroom: number | null;
  pct: number;
  tone: RailTone;
  label: string;
}

/** One rail against the case: over capacity is danger whatever is unknown; unknowns warn. */
export function railMeter(total: RailTotal, capacity: number | null | undefined): RailMeter {
  const { known: draw, unknown } = total;
  const plus = unknown ? ` + ${unknown} unknown` : "";
  if (capacity == null) {
    return {
      draw,
      unknown,
      capacity: null,
      headroom: null,
      pct: 0,
      tone: "neutral",
      label: `draw ${draw}mA${plus} · case capacity unspecified`,
    };
  }
  const headroom = capacity - draw;
  const pct = capacity > 0 ? Math.min(100, Math.round((draw / capacity) * 100)) : draw > 0 ? 100 : 0;
  const tone: RailTone =
    headroom < 0 ? "danger" : unknown > 0 || pct >= 85 ? "warning" : "success";
  const label = unknown
    ? `at least ${draw}/${capacity}mA${plus} · at most ${headroom}mA headroom`
    : `${draw}/${capacity}mA · headroom ${headroom}mA`;
  return { draw, unknown, capacity, headroom, pct, tone, label };
}
