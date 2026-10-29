import type { GeneratePatchesResponse } from "@/types/api";

/** The message shown when a generate call produced no patches, or null when it did. */
export function describeEmptyGeneration(body: GeneratePatchesResponse): string | null {
  const status = body.generation_status ?? "OK";
  const count = body.generated_count ?? body.patches?.length ?? 0;

  if (status === "VALIDATION_FAILED") {
    const blocking = (body.validation?.findings ?? []).filter((f) => f.severity === "block");
    const lines = blocking.map((f) => f.message);
    return (
      "Generation VALIDATION_FAILED: nothing was saved." +
      (lines.length ? ` Blocking findings: ${lines.join(" ")}` : "")
    );
  }
  if (status === "NOT_COMPUTABLE") {
    return (
      `Generation ${status}: no patches produced` +
      (body.inventory_gate_code ? ` (${body.inventory_gate_code})` : "") +
      ". Confirm inventory modules, then retry."
    );
  }
  if (count === 0) {
    return "No patch rule fits this rack.";
  }
  return null;
}
