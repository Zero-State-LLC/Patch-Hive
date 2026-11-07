import { describe, expect, it } from "vitest";
import type { Rack, RackModule } from "@/types/api";
import { rigRowWidths } from "./rigRows";

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
