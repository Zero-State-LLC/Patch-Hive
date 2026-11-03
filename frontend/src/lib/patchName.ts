import type { Patch } from "@/types/api";

/** The name a patch goes by: the user's own name for it, then the suggested name, then the generated one. */
export function patchName(patch: Pick<Patch, "name" | "name_override" | "suggested_name">): string {
  return patch.name_override || patch.suggested_name || patch.name;
}
