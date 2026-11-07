import type { Rack } from "@/types/api";

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
