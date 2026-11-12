import type { Rack, RackModuleSpec } from "@/types/api";

/**
 * HP per row of a rig. With a Case, the Case's rows as it states them. With no Case (a rig
 * started from a photo, spec 009), each row is as wide as its modules reach, and the rows run
 * to the last one that holds a module.
 */
export function rigRowWidths(rackCase: Rack["case"], modules: Rack["modules"]): number[] {
  if (rackCase) return rackCase.hp_per_row ?? [];
  const reach = new Map<number, number>();
  for (const m of modules) {
    const hp = m.module?.hp ?? 0;
    if (hp > 0) reach.set(m.row_index, Math.max(reach.get(m.row_index) ?? 0, m.start_hp + hp));
  }
  if (reach.size === 0) return [];
  return Array.from({ length: Math.max(...reach.keys()) + 1 }, (_, row) => reach.get(row) ?? 0);
}

// A Rig with no Case is placed on open rows: never drawn narrower than a common Eurorack row,
// always with room to grow past the furthest Module, and one empty row past the last used one.
const OPEN_ROW_HP = 84;
const OPEN_ROW_ROOM = 24;

/** The rows the placement editor draws for a Rig with no Case, all the same width. Nothing on
 * them is past an end: they only show where Modules sit. */
export function openRowWidths(
  placements: RackModuleSpec[],
  resolveHp: (moduleId: number) => number | null,
): number[] {
  let lastRow = -1;
  let reach = 0;
  for (const spec of placements) {
    lastRow = Math.max(lastRow, spec.row_index);
    reach = Math.max(reach, spec.start_hp + (resolveHp(spec.module_id) ?? 0));
  }
  const width = Math.max(OPEN_ROW_HP, reach + OPEN_ROW_ROOM);
  return Array.from({ length: lastRow + 2 }, () => width);
}
