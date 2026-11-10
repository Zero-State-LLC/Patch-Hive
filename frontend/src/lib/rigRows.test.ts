import { describe, expect, it } from "vitest";
import type { Rack, RackModule, RackModuleSpec } from "@/types/api";
import { openRowWidths, rigRowWidths } from "./rigRows";

const at = (row: number, startHp: number, hp: number): RackModule =>
  ({
    id: row * 100 + startHp,
    module_id: row * 100 + startHp,
    row_index: row,
    start_hp: startHp,
    module: { id: 1, brand: "Test", name: "M", hp, module_type: "VCO" },
  }) as RackModule;

const withCase = (hpPerRow: number[]): Rack["case"] => ({
  id: 1,
  brand: "Test",
  name: "Case",
  total_hp: hpPerRow.reduce((a, b) => a + b, 0),
  rows: hpPerRow.length,
  hp_per_row: hpPerRow,
});

describe("rigRowWidths", () => {
  it("takes a Case's rows as it states them", () => {
    expect(rigRowWidths(withCase([104, 84]), [at(0, 0, 10)])).toEqual([104, 84]);
  });

  it("makes each row of a rig with no Case as wide as its modules reach", () => {
    expect(rigRowWidths(undefined, [at(0, 0, 10), at(0, 18, 6), at(2, 4, 8)])).toEqual([24, 0, 12]);
  });

  it("draws no rows for a rig with no Case and nothing placed", () => {
    expect(rigRowWidths(undefined, [])).toEqual([]);
  });
});

describe("openRowWidths", () => {
  const HP: Record<number, number> = { 1: 10, 2: 8 };
  const resolveHp = (id: number) => HP[id] ?? null;
  const spec = (moduleId: number, row: number, startHp: number): RackModuleSpec => ({
    module_id: moduleId,
    row_index: row,
    start_hp: startHp,
  });

  it("gives an empty Rig with no Case one row to place on", () => {
    expect(openRowWidths([], resolveHp)).toEqual([84]);
  });

  it("keeps one empty row past the last used one, and room to grow past the furthest Module", () => {
    // The furthest Module ends at HP 98, so every row is drawn 24 HP past it.
    expect(openRowWidths([spec(1, 0, 0), spec(2, 1, 90)], resolveHp)).toEqual([122, 122, 122]);
  });

  it("never draws a row narrower than a common Eurorack row", () => {
    expect(openRowWidths([spec(1, 0, 0)], resolveHp)).toEqual([84, 84]);
  });
});
