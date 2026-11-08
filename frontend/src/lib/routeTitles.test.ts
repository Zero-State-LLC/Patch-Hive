import { describe, expect, it } from "vitest";
import { metaFor, titleFor } from "./routeTitles";

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
    ["/rigs/7/reading", "Check the reading, PatchHive"],
    ["/privacy", "Privacy notice, PatchHive"],
    ["/admin", "Admin, PatchHive"],
    ["/admin/exports", "Admin exports, PatchHive"],
  ])("names %s", (path, title) => {
    expect(titleFor(path)).toBe(title);
  });

  it("names an unknown path as not found", () => {
    expect(titleFor("/no-such-route")).toBe("Not found, PatchHive");
  });

  it("describes every screen, and names a canonical URL only for a public page", () => {
    expect(metaFor("/")).toEqual({
      title: "PatchHive, by Zero State",
      description: "Confirm a Eurorack rig and export its Patch Book, without invented inventory.",
      canonical: "https://patch-hive.com/",
    });
    expect(metaFor("/patches").canonical).toBe("https://patch-hive.com/patches");
    expect(metaFor("/privacy/").canonical).toBe("https://patch-hive.com/privacy");
    for (const path of ["/racks", "/rigs/7/reading", "/account", "/admin/runs", "/nope"]) {
      expect(metaFor(path).description).not.toBe("");
      expect(metaFor(path).canonical).toBeNull();
    }
    expect(metaFor("/rigs/7/reading").description).toMatch(/^Fix anything PatchHive got wrong/);
  });

  it("gives distinct screens distinct titles", () => {
    const paths = ["/", "/patches", "/privacy", "/login", "/account", "/racks", "/racks/new"]
      .concat(["/racks/7/edit", "/rigs/new/photo", "/rigs/7/photo", "/rigs/7/reading", "/rigs/7"])
      .concat(["/rigs/7/patchbook-studio", "/rigs/7/patches/3", "/admin", "/admin/users"])
      .concat(["/admin/modules", "/admin/gallery", "/admin/runs", "/admin/exports"])
      .concat(["/admin/leaderboards", "/nope"]);
    const titles = paths.map(titleFor);
    expect(new Set(titles).size).toBe(paths.length);
  });
});
