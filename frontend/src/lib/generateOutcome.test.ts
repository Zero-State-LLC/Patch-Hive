import { describe, expect, it } from "vitest";
import { describeEmptyGeneration } from "./generateOutcome";
import type { GeneratePatchesResponse } from "@/types/api";

const base: GeneratePatchesResponse = { generated_count: 0, patches: [] };

describe("describeEmptyGeneration", () => {
  it("lists the blocking findings when validation fails, not the inventory hint", () => {
    const message = describeEmptyGeneration({
      ...base,
      generation_status: "VALIDATION_FAILED",
      validation: {
        blocking: true,
        findings: [
          {
            severity: "block",
            code: "PORT_DIRECTION_MISMATCH",
            message: "VCF: 'LP Out' is not a declared input.",
          },
          {
            severity: "unresolved",
            code: "PORT_NOT_ON_FILE",
            message: "Bare: jack names are not on file.",
          },
        ],
      },
    });
    expect(message).toContain("Nothing was saved");
    expect(message).toContain("VCF: 'LP Out' is not a declared input.");
    expect(message).not.toContain("not on file");
    expect(message).not.toContain("nothing on this Rig is confirmed");
  });

  it("says in words that nothing is confirmed when the run can't be computed", () => {
    // What the API answers today: the inventory gate's code is NOT_COMPUTABLE itself, with a
    // message meant for logs.
    const message = describeEmptyGeneration({
      ...base,
      generation_status: "NOT_COMPUTABLE",
      inventory_gate_code: "NOT_COMPUTABLE",
      inventory_gate_messages: [
        "No USER_CONFIRMED modules in rack inventory; hardware-constrained generation is not computable.",
      ],
    });
    expect(message).toBe(
      "No patches yet: nothing on this Rig is confirmed. Confirm a reading of its photo, or place its Modules by hand, then generate again.",
    );
  });

  it("says no rule fits for zero patches on a computed run", () => {
    expect(describeEmptyGeneration({ ...base, generation_status: "OK" })).toBe(
      "No patch rule fits the Modules on this Rig.",
    );
  });

  it("returns null when patches were produced", () => {
    expect(
      describeEmptyGeneration({ ...base, generated_count: 2, generation_status: "OK" }),
    ).toBeNull();
  });
});
