import type { Patch } from "@/types/api";

export type PatchDifficulty = "Beginner" | "Intermediate" | "Advanced";
export type WeirdnessFilter = "Any" | "Low" | "Medium" | "High";

export interface RackPatchFilters {
  category: string;
  difficulty: string;
  weirdness: WeirdnessFilter | string;
}

const WEIRDNESS_BUCKETS: Record<Exclude<WeirdnessFilter, "Any">, { min: number; max: number }> = {
  Low: { min: 0, max: 25 },
  Medium: { min: 25, max: 60 },
  High: { min: 60, max: Number.POSITIVE_INFINITY },
};

export function difficultyFromConnections(patch: Patch): PatchDifficulty {
  const count = patch.connections?.length || 0;
  if (count <= 4) return "Beginner";
  if (count <= 8) return "Intermediate";
  return "Advanced";
}

export function weirdnessFromConnections(patch: Patch): number {
  const modulationEdges = patch.connections.filter((connection) =>
    ["cv", "gate", "clock"].includes(connection.cable_type),
  ).length;
  return Math.min(100, modulationEdges * 8);
}

function patchMatchesWeirdness(patch: Patch, weirdnessFilter: string): boolean {
  if (weirdnessFilter === "Any") return true;
  const bucket = WEIRDNESS_BUCKETS[weirdnessFilter as Exclude<WeirdnessFilter, "Any">];
  if (!bucket) return true;

  const weirdness = weirdnessFromConnections(patch);
  return weirdness >= bucket.min && weirdness <= bucket.max;
}

export function patchMatchesFilters(patch: Patch, filters: RackPatchFilters): boolean {
  const categoryMatches = filters.category === "All" || patch.category === filters.category;
  const difficultyMatches =
    filters.difficulty === "All" || difficultyFromConnections(patch) === filters.difficulty;

  return categoryMatches && difficultyMatches && patchMatchesWeirdness(patch, filters.weirdness);
}

export function filterPatches(patches: Patch[], filters: RackPatchFilters): Patch[] {
  return patches.filter((patch) => patchMatchesFilters(patch, filters));
}

export function patchCategories(patches: Patch[]): string[] {
  return [...new Set(patches.map((patch) => patch.category))];
}
