import { describe, expect, it } from "vitest";
import { rigDetailToRack, rigSummaryToRack } from "./canonRigAdapter";
import type { CanonRigDetailDto, CanonRigSummaryDto } from "./canonRigAdapter";

const summary: CanonRigSummaryDto = {
  rig_id: 7,
  rack_id: 7,
  user_id: 3,
  case_id: 2,
  name: "Golden Rig",
  name_suggested: null,
  description: null,
  tags: ["demo"],
  is_public: false,
  module_count: 2,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-02T00:00:00Z",
};

describe("canonRigAdapter", () => {
  it("maps rig_id onto Rack.id and keeps list rows placement-free", () => {
    const rack = rigSummaryToRack(summary);
    expect(rack.id).toBe(7);
    expect(rack.case_id).toBe(2);
    expect(rack.name).toBe("Golden Rig");
    expect(rack.name_suggested).toBeUndefined();
    expect(rack.description).toBeUndefined();
    expect(rack.modules).toEqual([]);
    expect(rack.case).toBeUndefined();
  });

  it("falls back to an empty name when the canon row has none", () => {
    expect(rigSummaryToRack({ ...summary, name: null }).name).toBe("");
  });

  it("carries detail placements and case through unchanged", () => {
    const detail: CanonRigDetailDto = {
      ...summary,
      generation_seed: 42,
      modules: [{ id: 1, module_id: 9, row_index: 0, start_hp: 0 }],
      case: { id: 2, brand: "Intellijel", name: "7U", total_hp: 104, rows: 2, hp_per_row: [104, 104] },
      vote_count: 5,
    };
    const rack = rigDetailToRack(detail);
    expect(rack.id).toBe(7);
    expect(rack.generation_seed).toBe(42);
    expect(rack.modules).toHaveLength(1);
    expect(rack.modules[0].module_id).toBe(9);
    expect(rack.case?.brand).toBe("Intellijel");
    expect(rack.vote_count).toBe(5);
  });

  it("treats a null case as absent", () => {
    const rack = rigDetailToRack({ ...summary, generation_seed: null, modules: [], case: null, vote_count: 0 });
    expect(rack.case).toBeUndefined();
    expect(rack.generation_seed).toBeUndefined();
  });
});
