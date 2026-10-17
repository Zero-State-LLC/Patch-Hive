/**
 * Hash helpers. Prefer server-authored Run.artifact_manifest_hash for exports.
 * legacyRunManifestHash remains for tests / parity with backend.runs.bridge.
 */
export async function sha256Hex(input: string): Promise<string> {
  const data = new TextEncoder().encode(input);
  const digest = await crypto.subtle.digest("SHA-256", data);
  return Array.from(new Uint8Array(digest))
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("");
}

/**
 * @deprecated Prefer `run.artifact_manifest_hash` from GET /api/runs.
 * Kept for parity with backend `legacy_artifact_manifest_hash`.
 */
export async function legacyRunManifestHash(
  runId: number | string,
  rigId: number | string,
): Promise<string> {
  return sha256Hex(`patchhive:legacy-run:${runId}:rig:${rigId}`);
}
