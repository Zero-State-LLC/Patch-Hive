import { describe, expect, it } from "vitest";
import type { RackModuleSpec } from "@/types/api";
import {
  checkSlot,
  clampStart,
  moveTo,
  nudgeSlot,
  slotPhrase,
  startUnderPointer,
} from "./placementMove";

const HP: Record<number, number> = { 1: 10, 2: 8, 3: 12 };
const NAMES: Record<number, string> = { 1: "Alpha", 2: "Beta", 3: "Gamma" };
const resolveHp = (id: number) => HP[id] ?? null;
const nameFor = (spec: RackModuleSpec) => NAMES[spec.module_id];

// Two rows of 84 HP: Alpha at 0 to 9 and Beta at 10 to 17 on row 0.
const placements: RackModuleSpec[] = [
  { module_id: 1, row_index: 0, start_hp: 0 },
  { module_id: 2, row_index: 0, start_hp: 10 },
];
const rows = [84, 84];
const check = (row: number, start: number, hp: number, ignore = -1) =>
  checkSlot({ row, start, hp }, placements, rows, resolveHp, nameFor, ignore);

describe("checkSlot", () => {
  it("accepts a free slot, including one that touches its neighbours", () => {
    expect(check(0, 18, 12)).toEqual({ ok: true });
    expect(check(1, 0, 84)).toEqual({ ok: true });
  });

  it("names the module in the way and where it sits", () => {
    expect(check(0, 14, 12)).toEqual({ ok: false, reason: "Overlaps Beta at HP 10 to 17." });
  });

  it("refuses a slot that runs off the end of its row", () => {
    expect(check(0, 80, 12)).toEqual({
      ok: false,
      reason: "Runs past the end of row 0, which is 84 HP.",
    });
  });

  it("refuses a row the case doesn't have, and a width nobody knows", () => {
    expect(check(2, 0, 4)).toEqual({ ok: false, reason: "Row 2 isn't on this case." });
    expect(check(1, 0, 0).ok).toBe(false);
  });

  it("never lets a moving module collide with itself", () => {
    expect(check(0, 12, 8, 1)).toEqual({ ok: true });
    expect(check(0, 12, 8)).toEqual({ ok: false, reason: "Overlaps Beta at HP 10 to 17." });
  });
});

describe("nudgeSlot", () => {
  const beta = { row: 0, start: 10, hp: 8 };

  it("moves 1 HP, or 4 with Shift, along the row", () => {
    expect(nudgeSlot(beta, "ArrowRight", false, rows)).toEqual({ ...beta, start: 11 });
    expect(nudgeSlot(beta, "ArrowLeft", true, rows)).toEqual({ ...beta, start: 6 });
  });

  it("stops at either end of the row", () => {
    expect(nudgeSlot({ ...beta, start: 1 }, "ArrowLeft", true, rows).start).toBe(0);
    expect(nudgeSlot({ ...beta, start: 75 }, "ArrowRight", true, rows).start).toBe(76);
  });

  it("changes rows with Up and Down, keeping the module on the row it lands on", () => {
    expect(nudgeSlot(beta, "ArrowDown", false, rows)).toEqual({ ...beta, row: 1 });
    expect(nudgeSlot(beta, "ArrowUp", false, rows)).toEqual(beta);
    expect(nudgeSlot({ row: 0, start: 80, hp: 8 }, "ArrowDown", false, [84, 42])).toEqual({
      row: 1,
      start: 34,
      hp: 8,
    });
  });
});

describe("startUnderPointer", () => {
  const track = { left: 100, width: 840 };

  it("snaps to whole HP and keeps where the module was taken hold of", () => {
    // 10 px per HP: the pointer at HP 42.6, holding the module 2 HP in.
    expect(startUnderPointer(526, track, 84, 8, 2)).toBe(41);
  });

  it("keeps the module whole on the row", () => {
    expect(startUnderPointer(0, track, 84, 8, 0)).toBe(0);
    expect(startUnderPointer(2000, track, 84, 8, 0)).toBe(76);
  });
});

describe("moving", () => {
  it("moves one placement and leaves the rest", () => {
    expect(moveTo(placements, 1, 1, 20)).toEqual([
      placements[0],
      { module_id: 2, row_index: 1, start_hp: 20 },
    ]);
  });

  it("says where a module sits", () => {
    expect(slotPhrase(1, 12)).toBe("row 1 at 12 HP");
    expect(clampStart(-3, 8, 84)).toBe(0);
  });
});
