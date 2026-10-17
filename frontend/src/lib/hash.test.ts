import { describe, expect, it } from "vitest";
import { legacyRunManifestHash, sha256Hex } from "@/lib/hash";

describe("hash helpers", () => {
  it("produces stable 64-char hex digests", async () => {
    const a = await sha256Hex("patchhive");
    const b = await sha256Hex("patchhive");
    expect(a).toHaveLength(64);
    expect(a).toBe(b);
    expect(a).toMatch(/^[0-9a-f]{64}$/);
  });

  it("bridges legacy run ids into canon manifest hashes", async () => {
    const hash = await legacyRunManifestHash(12, 1);
    expect(hash).toHaveLength(64);
    expect(hash).not.toBe(await legacyRunManifestHash(11, 1));
  });
});
