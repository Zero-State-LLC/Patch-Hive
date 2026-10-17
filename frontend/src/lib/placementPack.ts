/**
 * Contiguous HP packing for Eurorack rows (fail-closed: never invents HP).
 */
import type { RackModuleSpec } from "@/types/api";

export type ResolveHp = (moduleId: number) => number | null;

export type PackUnplaced = {
  module_id: number;
  reason: string;
};

export type PackResult = {
  /** Existing + newly packed placements */
  placements: RackModuleSpec[];
  /** Only the new specs added by this pack */
  added: RackModuleSpec[];
  unplaced: PackUnplaced[];
};

/** Occupied [start, end) intervals on a row. */
function occupiedOnRow(
  rowIndex: number,
  placements: RackModuleSpec[],
  resolveHp: ResolveHp,
): { start: number; end: number }[] {
  return placements
    .filter((p) => p.row_index === rowIndex)
    .map((p) => {
      const hp = resolveHp(p.module_id) ?? 0;
      return { start: p.start_hp, end: p.start_hp + hp };
    })
    .filter((o) => o.end > o.start)
    .sort((a, b) => a.start - b.start);
}

/** First free start HP on a row that fits moduleHp, or null if it will not fit. */
export function firstFreeStartHp(
  rowIndex: number,
  moduleHp: number,
  placements: RackModuleSpec[],
  resolveHp: ResolveHp,
  rowCapacity: number,
): number | null {
  if (moduleHp <= 0 || rowCapacity <= 0 || moduleHp > rowCapacity) return null;
  const occupied = occupiedOnRow(rowIndex, placements, resolveHp);
  let cursor = 0;
  for (const block of occupied) {
    if (block.start - cursor >= moduleHp) {
      return cursor;
    }
    cursor = Math.max(cursor, block.end);
  }
  if (rowCapacity - cursor >= moduleHp) {
    return cursor;
  }
  return null;
}

/**
 * Pack module IDs left-to-right, top-to-bottom starting at startRow.
 * Modules without known positive HP are unplaced (never invent width).
 */
export function packModulesOntoRows(
  moduleIds: number[],
  existing: RackModuleSpec[],
  resolveHp: ResolveHp,
  rowCapacities: number[],
  startRow = 0,
): PackResult {
  const working: RackModuleSpec[] = [...existing];
  const added: RackModuleSpec[] = [];
  const unplaced: PackUnplaced[] = [];

  if (!rowCapacities.length) {
    return {
      placements: working,
      added,
      unplaced: moduleIds.map((module_id) => ({
        module_id,
        reason: "No row capacity on case",
      })),
    };
  }

  const rowCount = rowCapacities.length;
  const firstRow = Math.max(0, Math.min(startRow, rowCount - 1));

  for (const moduleId of moduleIds) {
    const hp = resolveHp(moduleId);
    if (hp == null || hp <= 0) {
      unplaced.push({
        module_id: moduleId,
        reason: "HP unknown or non-positive — not placeable",
      });
      continue;
    }

    let placed = false;
    // Prefer startRow…end, then wrap to earlier rows
    const order: number[] = [];
    for (let r = firstRow; r < rowCount; r++) order.push(r);
    for (let r = 0; r < firstRow; r++) order.push(r);

    for (const row of order) {
      const capacity = rowCapacities[row] ?? 0;
      const start = firstFreeStartHp(row, hp, working, resolveHp, capacity);
      if (start == null) continue;
      const spec: RackModuleSpec = {
        module_id: moduleId,
        row_index: row,
        start_hp: start,
      };
      working.push(spec);
      added.push(spec);
      placed = true;
      break;
    }

    if (!placed) {
      unplaced.push({
        module_id: moduleId,
        reason: `No free ${hp}HP gap across ${rowCount} row(s)`,
      });
    }
  }

  return { placements: working, added, unplaced };
}
