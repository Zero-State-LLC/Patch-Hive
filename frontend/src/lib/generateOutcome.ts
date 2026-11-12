import type { GeneratePatchesResponse } from "@/types/api";

/** The message shown when a generate call produced no patches, or null when it did. */
export function describeEmptyGeneration(body: GeneratePatchesResponse): string | null {
  const status = body.generation_status ?? "OK";
  const count = body.generated_count ?? body.patches?.length ?? 0;

  if (status === "VALIDATION_FAILED") {
    const blocking = (body.validation?.findings ?? []).filter((f) => f.severity === "block");
    const lines = blocking.map((f) => f.message);
    return lines.length
      ? `Nothing was saved: the generated patches broke these rules. ${lines.join(" ")}`
      : "Nothing was saved: the generated patches didn't pass the rig's rules.";
  }
  // The API answers NOT_COMPUTABLE for one reason only: nothing on the Rig is confirmed.
  if (status === "NOT_COMPUTABLE") {
    return "No patches yet: nothing on this Rig is confirmed. Confirm a reading of its photo, or place its Modules by hand, then generate again.";
  }
  if (count === 0) {
    return "No patch rule fits the Modules on this Rig.";
  }
  return null;
}
