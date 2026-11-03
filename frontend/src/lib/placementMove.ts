/**
 * placementMove — where a module may sit on a case's rows, checked before anything is saved.
 * A slot is a row and a start HP for a module of known width; it is free when it stays on the
 * row and overlaps no other placement. Moves snap to whole HP.
 */
import type { RackModuleSpec } from "@/types/api";
import type { ResolveHp } from "./placementPack";

export interface Slot {
  row: number;
  start: number;
  hp: number;
}

export type SlotCheck = { ok: true } | { ok: false; reason: string };

export type NudgeKey = "ArrowLeft" | "ArrowRight" | "ArrowUp" | "ArrowDown";

/** A big nudge (Shift + arrow) moves this many HP. */
export const BIG_NUDGE_HP = 4;

/** The start HP that keeps a module of `hp` whole on a row of `capacity`. */
export function clampStart(start: number, hp: number, capacity: number): number {
  return Math.max(0, Math.min(Math.round(start), Math.max(0, capacity - hp)));
}

/**
 * Whether a module may sit in `slot`. `ignoreIndex` is the placement being moved, which never
 * collides with itself. `nameFor` names the placement in the way, for the reason given.
 */
export function checkSlot(
  slot: Slot,
  placements: RackModuleSpec[],
  rowCapacities: number[],
  resolveHp: ResolveHp,
  nameFor: (spec: RackModuleSpec) => string,
  ignoreIndex = -1,
): SlotCheck {
  const capacity = rowCapacities[slot.row];
  if (capacity == null || capacity <= 0) {
    return { ok: false, reason: `Row ${slot.row} isn't on this case.` };
  }
  if (slot.hp <= 0) {
    return { ok: false, reason: "Its width isn't known, so it can't be placed." };
  }
  if (slot.start < 0 || slot.start + slot.hp > capacity) {
    return {
      ok: false,
      reason: `Runs past the end of row ${slot.row}, which is ${capacity} HP.`,
    };
  }
  const end = slot.start + slot.hp;
  for (const [index, spec] of placements.entries()) {
    if (index === ignoreIndex || spec.row_index !== slot.row) continue;
    const hp = resolveHp(spec.module_id) ?? 0;
    if (hp <= 0) continue;
    if (spec.start_hp < end && slot.start < spec.start_hp + hp) {
      return {
        ok: false,
        reason: `Overlaps ${nameFor(spec)} at HP ${spec.start_hp} to ${spec.start_hp + hp - 1}.`,
      };
    }
  }
  return { ok: true };
}

/** The slot one arrow press away: 1 HP (or BIG_NUDGE_HP) along the row, or one row up or down. */
export function nudgeSlot(slot: Slot, key: NudgeKey, big: boolean, rowCapacities: number[]): Slot {
  const step = big ? BIG_NUDGE_HP : 1;
  const lastRow = Math.max(0, rowCapacities.length - 1);
  if (key === "ArrowLeft" || key === "ArrowRight") {
    const capacity = rowCapacities[slot.row] ?? 0;
    const start = slot.start + (key === "ArrowRight" ? step : -step);
    return { ...slot, start: clampStart(start, slot.hp, capacity) };
  }
  const row = Math.max(0, Math.min(lastRow, slot.row + (key === "ArrowDown" ? 1 : -1)));
  return { ...slot, row, start: clampStart(slot.start, slot.hp, rowCapacities[row] ?? 0) };
}

/** The start HP under a pointer, snapped to whole HP, keeping the module's grab point. */
export function startUnderPointer(
  clientX: number,
  track: { left: number; width: number },
  capacity: number,
  hp: number,
  grabHp: number,
): number {
  if (track.width <= 0) return 0;
  const atHp = ((clientX - track.left) / track.width) * capacity;
  return clampStart(atHp - grabHp, hp, capacity);
}

/** The same placements with one moved to a new row and start HP. */
export function moveTo(
  placements: RackModuleSpec[],
  index: number,
  row: number,
  start: number,
): RackModuleSpec[] {
  return placements.map((spec, i) =>
    i === index ? { ...spec, row_index: row, start_hp: start } : spec,
  );
}

/** Where a module sits, as a phrase: "row 1 at 12 HP". */
export function slotPhrase(row: number, start: number): string {
  return `row ${row} at ${start} HP`;
}
