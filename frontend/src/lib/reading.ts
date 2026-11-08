/**
 * The Reading screen's rules (spec 009): which Sightings come first, what the owner starts
 * from, and what a confirmation sends. Nothing here calls the API.
 */
import type { ReadingConfirmRequest, Sighting } from "@/lib/api";

/** What the owner has decided for one Sighting. */
export type Decision =
  | { kind: "keep"; moduleId: number; label: string; hp: number; row: number; startHp: number }
  | { kind: "undecided"; row: number; startHp: number }
  | { kind: "leave_out" }
  | { kind: "not_a_module" };

/** A Module the owner added by hand, at a position they chose. */
export interface AddedModule {
  moduleId: number;
  label: string;
  hp: number;
  row: number;
  startHp: number;
}

/** A Sighting the owner must keep or leave out; a Blank Panel or not-Eurorack one is shown only. */
export const isDecided = (s: Sighting) => s.kind === "module" || s.kind === "unknown";

// "Couldn't tell" first, then "Check this", then "Sure", so time goes where it's needed.
const GROUP = { unresolved: 0, user_review: 1, auto_propose: 2 } as const;

const group = (s: Sighting) =>
  isDecided(s) ? (s.kind === "unknown" ? 0 : GROUP[s.disposition]) : 3;

export function orderSightings(sightings: Sighting[]): Sighting[] {
  return [...sightings].sort(
    (a, b) => group(a) - group(b) || a.row_index - b.row_index || a.start_hp - b.start_hp,
  );
}

export function dispositionWords(s: Sighting): string {
  if (s.kind === "blank_panel") return "Blank panel";
  if (s.kind === "not_eurorack") return "Not a Module";
  if (s.kind === "unknown") return "Couldn't tell";
  return { auto_propose: "Sure", user_review: "Check this", unresolved: "Couldn't tell" }[
    s.disposition
  ];
}

export type Tone = "success" | "warning" | "danger" | "neutral";

/** A Sighting's colour, from how sure the reading is; a Blank Panel or not-Eurorack one is neutral. */
export function dispositionTone(s: Sighting): Tone {
  if (!isDecided(s)) return "neutral";
  if (s.kind === "unknown") return "danger";
  return ({ auto_propose: "success", user_review: "warning", unresolved: "danger" } as const)[
    s.disposition
  ];
}

export const moduleLabel = (brand: string | null, name: string | null) =>
  [brand, name].filter(Boolean).join(" ") || "A catalog Module";

/** Where the owner starts: the closest match when the policy proposes one, else undecided. */
export function initialDecision(s: Sighting): Decision | null {
  if (!isDecided(s)) return null;
  const position = { row: s.row_index, startHp: s.start_hp };
  const top = [...s.candidates].sort((a, b) => b.score - a.score)[0];
  if (s.kind === "module" && s.disposition !== "unresolved" && top) {
    return {
      kind: "keep",
      moduleId: top.module_id,
      label: moduleLabel(top.brand, top.name),
      hp: top.hp ?? s.hp,
      ...position,
    };
  }
  return { kind: "undecided", ...position };
}

/** The confirmation the owner's decisions make, and the Sightings still to decide. */
export function confirmBody(
  decisions: Record<string, Decision>,
  added: AddedModule[],
): { body: ReadingConfirmRequest; undecided: string[] } {
  const body: ReadingConfirmRequest = { items: [], added: [], excluded: [], case_id: null };
  const undecided: string[] = [];
  for (const [sightingId, decision] of Object.entries(decisions)) {
    if (decision.kind === "keep") {
      body.items.push({
        sighting_id: sightingId,
        module_id: decision.moduleId,
        row_index: decision.row,
        start_hp: decision.startHp,
      });
    } else if (decision.kind === "undecided") {
      undecided.push(sightingId);
    } else {
      body.excluded.push(sightingId);
    }
  }
  body.added = added.map((a) => ({ module_id: a.moduleId, row_index: a.row, start_hp: a.startHp }));
  return { body, undecided };
}

/** The keys of Modules a named Case can't hold: on a row it doesn't have, or past a row's end.
 * With no Case, a row is as wide as what's on it, so nothing is past it. */
export function pastCase(
  placed: { key: string; row: number; startHp: number; hp: number }[],
  hpPerRow: number[] | null | undefined,
): Set<string> {
  if (!hpPerRow) return new Set();
  return new Set(
    placed
      .filter((p) => p.row >= hpPerRow.length || p.startHp + p.hp > hpPerRow[p.row])
      .map((p) => p.key),
  );
}

/** The keys of Modules that would share HP in a row. */
export function clashes(
  placed: { key: string; row: number; startHp: number; hp: number }[],
): Set<string> {
  const found = new Set<string>();
  placed.forEach((a, i) => {
    for (const b of placed.slice(i + 1)) {
      if (a.row === b.row && a.startHp < b.startHp + b.hp && b.startHp < a.startHp + a.hp) {
        found.add(a.key);
        found.add(b.key);
      }
    }
  });
  return found;
}

const READING_REASONS: Record<string, string> = {
  PROVIDER_DISABLED: "Photo reading is switched off on this site.",
  PROVIDER_NOT_CONFIGURED: "Photo reading isn't set up on this site yet.",
  RECORDINGS_NOT_CONFIGURED: "Photo reading isn't set up on this site yet.",
  RECORDING_MISSING: "There's no reading for this photo on this site.",
  PROVIDER_TIMED_OUT: "Reading the photo took too long.",
  PROVIDER_ERROR: "The reading service didn't answer.",
  ANSWER_MALFORMED: "The reading came back in a form PatchHive can't use.",
  TOO_MANY_SIGHTINGS: "The reading found more things than one photo can hold.",
  TOO_MANY_CANDIDATES: "The reading named too many possible Modules for one thing.",
  ROW_OUTSIDE_PHOTO: "The reading placed a Module on a row this photo doesn't cover.",
  CANDIDATE_NOT_IN_CATALOG: "The reading named a Module that isn't in the catalog.",
  CONSENT_NOT_GRANTED: "You didn't agree to let the reading service see this photo.",
  PHOTO_TOO_LARGE: "The photo is too large to send for reading.",
  PHOTO_UNREADABLE: "The photo couldn't be opened for reading.",
};

export const readingReason = (code: string | null) =>
  (code && READING_REASONS[code]) || "This photo couldn't be read.";

const REFUSALS: Record<string, string> = {
  POSITIONS_OVERLAP: "Some Modules overlap in a row. Move them apart, then confirm again.",
  ROW_PAST_CASE: "Some Modules sit past the end of a row of the Case.",
  SIGHTINGS_UNDECIDED: "Some Modules still need a decision.",
  READING_NOT_READ: "A photo is still being read, or couldn't be read. Retry or retake it first.",
  READINGS_CHANGED:
    "A photo of this Rig changed while you worked, so the reading is reloaded. Check it, then confirm again.",
  NO_CURRENT_READING: "There's nothing to confirm: every photo is already confirmed.",
  NO_MODULES: "Keep or add at least one Module.",
  PLACEMENT_INVALID: "Some Modules can't be placed where they are.",
  MODULE_NOT_FOUND: "A chosen Module is no longer in the catalog.",
  CASE_NOT_FOUND: "That Case is no longer in the catalog.",
};

export const refusalWords = (code: string | null | undefined) =>
  (code && REFUSALS[code]) || "The Rig couldn't be confirmed.";

/** The reason code an API refusal carries, as `detail` or `detail.code`. */
export function apiCode(error: unknown): string | null {
  const detail = (error as { response?: { data?: { detail?: unknown } } } | null)?.response?.data
    ?.detail;
  if (typeof detail === "string") return detail;
  if (detail && typeof detail === "object" && "code" in detail) {
    return String((detail as { code: unknown }).code);
  }
  return null;
}

/** The Modules an API refusal names, as `detail.modules`. */
export function apiModules(error: unknown): number[] {
  const detail = (error as { response?: { data?: { detail?: { modules?: unknown } } } } | null)
    ?.response?.data?.detail;
  const modules = detail && typeof detail === "object" ? detail.modules : undefined;
  return Array.isArray(modules) ? modules.filter((m): m is number => typeof m === "number") : [];
}

const PHOTO_REFUSALS: Record<string, string> = {
  PHOTO_READING_UNAVAILABLE: "Photo reading isn't open on this site.",
  ROWS_INVALID: "Say which rows the photo covers: a first row, and a last row no smaller.",
  RETAKE_NEEDS_RIG: "A retake has to name the Rig it belongs to.",
  READING_NOT_FOUND: "That photo's reading is no longer on this Rig.",
  READING_NOT_REPLACEABLE: "That reading is already confirmed or replaced.",
  PHOTO_EXPIRED: "That photo is no longer kept. Take a new one instead.",
  READING_NOT_FAILED: "That reading didn't fail, so there's nothing to retry.",
};

export const photoRefusal = (code: string | null) =>
  (code && PHOTO_REFUSALS[code]) || "This photo couldn't be used. Try another one.";
