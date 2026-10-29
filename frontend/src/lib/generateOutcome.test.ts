import { describe, expect, it } from "vitest";
import { describeEmptyGeneration } from "./generateOutcome";
import type { GeneratePatchesResponse } from "@/types/api";

const base: GeneratePatchesResponse = { generated_count: 0, patches: [] };

describe("describeEmptyGeneration", () => {
  it("lists the blocking findings for VALIDATION_FAILED, not the inventory hint", () => {
    const message = describeEmptyGeneration({
      ...base,
      generation_status: "VALIDATION_FAILED",
      validation: {
        blocking: true,
        findings: [
          { severity: "block", code: "PORT_DIRECTION_MISMATCH", message: "VCF: 'LP Out' is not a declared input." },
          { severity: "unresolved", code: "PORT_NOT_ON_FILE", message: "Bare: jack names are not on file." },
        ],
      },
    });
    expect(message).toContain("VALIDATION_FAILED");
    expect(message).toContain("VCF: 'LP Out' is not a declared input.");
    expect(message).not.toContain("not on file");
    expect(message).not.toContain("Confirm inventory");
  });

  it("keeps the inventory hint for NOT_COMPUTABLE", () => {
    const message = describeEmptyGeneration({
      ...base,
      generation_status: "NOT_COMPUTABLE",
      inventory_gate_code: "NO_CONFIRMED_MODULES",
    });
    expect(message).toContain("Confirm inventory modules");
    expect(message).toContain("NO_CONFIRMED_MODULES");
  });

  it("says no rule fits for zero patches on a computed run", () => {
    expect(describeEmptyGeneration({ ...base, generation_status: "OK" })).toBe(
      "No patch rule fits this rack.",
    );
  });

  it("returns null when patches were produced", () => {
    expect(describeEmptyGeneration({ ...base, generated_count: 2, generation_status: "OK" })).toBeNull();
  });
});
