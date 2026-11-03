import type { GeneratePatchesResponse } from "@/types/api";

/** Why the inventory gate stopped a run, in words. Unknown codes fall back to the general hint. */
const GATE_REASONS: Record<string, string> = {
  NO_CONFIRMED_MODULES: "this rig has no confirmed modules yet",
};

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
  if (status === "NOT_COMPUTABLE") {
    const reason = body.inventory_gate_code ? GATE_REASONS[body.inventory_gate_code] : undefined;
    return `No patches could be generated${reason ? `: ${reason}` : ""}. Confirm inventory modules, then retry.`;
  }
  if (count === 0) {
    return "No patch rule fits this rack.";
  }
  return null;
}
