import { describe, expect, it } from "vitest";
import { patchName } from "./patchName";

describe("patchName", () => {
  it("prefers the user's own name, then the suggested name, then the generated one", () => {
    expect(patchName({ name: "gen", suggested_name: "sug", name_override: "mine" })).toBe("mine");
    expect(patchName({ name: "gen", suggested_name: "sug", name_override: null })).toBe("sug");
    expect(patchName({ name: "gen", suggested_name: null })).toBe("gen");
  });
});
