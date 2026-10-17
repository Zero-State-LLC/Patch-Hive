import { describe, expect, it } from "vitest";
import { firstFreeStartHp, packModulesOntoRows } from "./placementPack";

const hpMap: Record<number, number> = {
  1: 10,
  2: 8,
  3: 14,
  4: 84,
  5: 0,
};

const resolveHp = (id: number) => (id in hpMap ? hpMap[id] : null);

describe("firstFreeStartHp", () => {
  it("returns 0 on empty row", () => {
    expect(firstFreeStartHp(0, 10, [], resolveHp, 84)).toBe(0);
  });

  it("snaps after occupied blocks", () => {
    const placed = [
      { module_id: 1, row_index: 0, start_hp: 0 },
      { module_id: 2, row_index: 0, start_hp: 10 },
    ];
    expect(firstFreeStartHp(0, 14, placed, resolveHp, 84)).toBe(18);
  });

  it("returns null when module cannot fit", () => {
    const placed = [{ module_id: 4, row_index: 0, start_hp: 0 }];
    expect(firstFreeStartHp(0, 10, placed, resolveHp, 84)).toBeNull();
  });
});

describe("packModulesOntoRows", () => {
  it("packs multiple modules on one row left-to-right", () => {
    const result = packModulesOntoRows([1, 2, 3], [], resolveHp, [84], 0);
    expect(result.unplaced).toEqual([]);
    expect(result.added).toEqual([
      { module_id: 1, row_index: 0, start_hp: 0 },
      { module_id: 2, row_index: 0, start_hp: 10 },
      { module_id: 3, row_index: 0, start_hp: 18 },
    ]);
  });

  it("spills to next row when current is full", () => {
    const fullish = [
      { module_id: 1, row_index: 0, start_hp: 0 }, // 10
      { module_id: 3, row_index: 0, start_hp: 10 }, // 14 → used 24
    ];
    // 84HP module fills row 0; next module spills to row 1
    const onlyFull = packModulesOntoRows([4, 2], [], resolveHp, [84, 84], 0);
    expect(onlyFull.added.find((a) => a.module_id === 4)?.row_index).toBe(0);
    expect(onlyFull.added.find((a) => a.module_id === 2)?.row_index).toBe(1);
    expect(onlyFull.added.find((a) => a.module_id === 2)?.start_hp).toBe(0);

    // Respect existing occupancy
    const withExisting = packModulesOntoRows([2], fullish, resolveHp, [84], 0);
    expect(withExisting.added).toEqual([{ module_id: 2, row_index: 0, start_hp: 24 }]);
  });

  it("marks unknown or zero HP as unplaced without inventing width", () => {
    const result = packModulesOntoRows([5, 99, 1], [], resolveHp, [84], 0);
    expect(result.added).toEqual([{ module_id: 1, row_index: 0, start_hp: 0 }]);
    expect(result.unplaced.map((u) => u.module_id).sort()).toEqual([5, 99]);
  });

  it("reports unplaced when no free gap remains", () => {
    const existing = [{ module_id: 4, row_index: 0, start_hp: 0 }];
    const result = packModulesOntoRows([1], existing, resolveHp, [84], 0);
    expect(result.added).toEqual([]);
    expect(result.unplaced[0]?.module_id).toBe(1);
    expect(result.unplaced[0]?.reason).toMatch(/No free/);
  });
});
