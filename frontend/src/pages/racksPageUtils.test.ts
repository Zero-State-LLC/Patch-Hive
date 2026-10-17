import { describe, expect, it } from "vitest";
import type { Patch } from "@/types/api";
import {
  difficultyFromConnections,
  filterPatches,
  patchCategories,
  weirdnessFromConnections,
} from "./racksPageUtils";

const basePatch: Patch = {
  id: 1,
  rack_id: 1,
  run_id: 1,
  name: "Patch",
  category: "Drone",
  connections: [],
  generation_seed: 1,
  generation_version: "test",
  is_public: false,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
  vote_count: 0,
};

function patchWithConnections(id: number, category: string, cableTypes: string[]): Patch {
  return {
    ...basePatch,
    id,
    name: `Patch ${id}`,
    category,
    connections: cableTypes.map((cable_type, index) => ({
      from_module_id: index,
      from_port: `out-${index}`,
      to_module_id: index + 1,
      to_port: `in-${index}`,
      cable_type,
    })),
  };
}

describe("racksPageUtils", () => {
  it("keeps difficulty thresholds aligned with connection counts", () => {
    expect(difficultyFromConnections(patchWithConnections(1, "Drone", ["audio"]))).toBe("Beginner");
    expect(
      difficultyFromConnections(patchWithConnections(2, "Drone", Array(6).fill("audio"))),
    ).toBe("Intermediate");
    expect(
      difficultyFromConnections(patchWithConnections(3, "Drone", Array(9).fill("audio"))),
    ).toBe("Advanced");
  });

  it("scores weirdness from modulation cable types only", () => {
    expect(
      weirdnessFromConnections(patchWithConnections(1, "Drone", ["audio", "cv", "gate"])),
    ).toBe(16);
  });

  it("filters patches by category, difficulty, and weirdness buckets", () => {
    const beginnerLow = patchWithConnections(1, "Drone", ["audio", "cv"]);
    const intermediateMedium = patchWithConnections(2, "Percussion", [
      "cv",
      "gate",
      "clock",
      "cv",
      "audio",
    ]);
    const advancedHigh = patchWithConnections(3, "Drone", Array(9).fill("cv"));

    expect(
      filterPatches([beginnerLow, intermediateMedium, advancedHigh], {
        category: "Drone",
        difficulty: "Advanced",
        weirdness: "High",
      }),
    ).toEqual([advancedHigh]);

    expect(
      filterPatches([beginnerLow, intermediateMedium, advancedHigh], {
        category: "All",
        difficulty: "All",
        weirdness: "Medium",
      }),
    ).toEqual([intermediateMedium]);
  });

  it("returns unique patch categories in source order", () => {
    expect(
      patchCategories([
        patchWithConnections(1, "Drone", []),
        patchWithConnections(2, "Percussion", []),
        patchWithConnections(3, "Drone", []),
      ]),
    ).toEqual(["Drone", "Percussion"]);
  });
});
