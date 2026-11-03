import { describe, expect, it } from "vitest";
import { titleFor } from "./routeTitles";

describe("titleFor", () => {
  it("keeps the brand title for the home screen", () => {
    expect(titleFor("/")).toBe("PatchHive, by Zero State");
  });

  it.each([
    ["/racks", "Rigs, PatchHive"],
    ["/racks/new", "New rig, PatchHive"],
    ["/racks/7/edit", "Place modules, PatchHive"],
    ["/rigs/7", "Rig workspace, PatchHive"],
    ["/rigs/7/patchbook-studio", "Patch book style, PatchHive"],
    ["/cases/sim-co-sim-84", "Case, PatchHive"],
    ["/admin", "Ops, PatchHive"],
    ["/admin/exports", "Ops exports, PatchHive"],
  ])("names %s", (path, title) => {
    expect(titleFor(path)).toBe(title);
  });

  it("names an unknown path as not found", () => {
    expect(titleFor("/no-such-route")).toBe("Not found, PatchHive");
  });
});
