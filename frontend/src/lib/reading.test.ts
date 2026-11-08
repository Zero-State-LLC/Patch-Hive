import { describe, expect, it } from "vitest";
import type { Sighting } from "@/lib/api";
import {
  clashes,
  confirmBody,
  dispositionTone,
  dispositionWords,
  initialDecision,
  namePlaced,
  orderSightings,
  pastCase,
  readingReason,
  refusalWords,
} from "./reading";

const sighting = (id: string, over: Partial<Sighting> = {}): Sighting => ({
  sighting_id: id,
  box: { x: 0, y: 0, w: 0.1, h: 0.5 },
  kind: "module",
  row_index: 0,
  start_hp: 0,
  hp: 10,
  candidates: [],
  disposition: "unresolved",
  ...over,
});

const candidate = (moduleId: number, score: number, name = `M${moduleId}`, hp = 10) => ({
  module_id: moduleId,
  score,
  brand: "Sim Co",
  name,
  hp,
});

describe("the reading list", () => {
  it("puts Couldn't tell first, then Check this, then Sure, each by row and HP", () => {
    const list = [
      sighting("sure-r0", { disposition: "auto_propose", row_index: 0, start_hp: 20 }),
      sighting("check-r1", { disposition: "user_review", row_index: 1, start_hp: 0 }),
      sighting("unknown-r0", { kind: "unknown", row_index: 0, start_hp: 30 }),
      sighting("tell-r0", { row_index: 0, start_hp: 10 }),
      sighting("check-r0", { disposition: "user_review", row_index: 0, start_hp: 40 }),
      sighting("panel", { kind: "blank_panel", row_index: 0, start_hp: 50 }),
    ];

    expect(orderSightings(list).map((s) => s.sighting_id)).toEqual([
      "tell-r0",
      "unknown-r0",
      "check-r0",
      "check-r1",
      "sure-r0",
      // A Blank Panel is empty HP, not a Module to decide, so it comes after them.
      "panel",
    ]);
  });

  it("says how sure it is in words, never numbers", () => {
    expect(dispositionWords(sighting("a", { disposition: "auto_propose" }))).toBe("Sure");
    expect(dispositionWords(sighting("b", { disposition: "user_review" }))).toBe("Check this");
    expect(dispositionWords(sighting("c"))).toBe("Couldn't tell");
    expect(dispositionWords(sighting("d", { kind: "blank_panel" }))).toBe("Blank panel");
    expect(dispositionWords(sighting("e", { kind: "not_eurorack" }))).toBe("Not a Module");
  });
});

describe("tones", () => {
  it("colour a Sighting by how sure the reading is, never by its wording", () => {
    expect(dispositionTone(sighting("a", { disposition: "auto_propose" }))).toBe("success");
    expect(dispositionTone(sighting("b", { disposition: "user_review" }))).toBe("warning");
    expect(dispositionTone(sighting("c"))).toBe("danger");
    expect(dispositionTone(sighting("d", { kind: "unknown", disposition: "auto_propose" }))).toBe(
      "danger",
    );
    expect(dispositionTone(sighting("e", { kind: "blank_panel" }))).toBe("neutral");
  });
});

describe("what the owner starts from", () => {
  it("keeps the closest match when the policy proposes one", () => {
    const s = sighting("a", {
      disposition: "user_review",
      row_index: 1,
      start_hp: 8,
      candidates: [candidate(2, 0.3), candidate(1, 0.6, "Maths", 20)],
    });

    expect(initialDecision(s)).toEqual({
      kind: "keep",
      moduleId: 1,
      label: "Sim Co Maths",
      hp: 20,
      row: 1,
      startHp: 8,
    });
  });

  it("leaves a Module it couldn't tell, or an unknown thing, for the owner to decide", () => {
    const unsure = sighting("a", { candidates: [candidate(1, 0.2)], start_hp: 4 });

    expect(initialDecision(unsure)).toEqual({ kind: "undecided", row: 0, startHp: 4 });
    expect(initialDecision(sighting("b", { kind: "unknown" }))).toEqual({
      kind: "undecided",
      row: 0,
      startHp: 0,
    });
  });

  it("has nothing to decide for a Blank Panel or something that isn't Eurorack", () => {
    expect(initialDecision(sighting("a", { kind: "blank_panel" }))).toBeNull();
    expect(initialDecision(sighting("b", { kind: "not_eurorack" }))).toBeNull();
  });
});

describe("confirming", () => {
  const kept = {
    kind: "keep",
    moduleId: 7,
    label: "Sim Co VCO",
    hp: 10,
    row: 0,
    startHp: 0,
  } as const;

  it("sends what is kept, what is left out and what was added, and nothing else", () => {
    const body = confirmBody(
      {
        a: kept,
        b: { kind: "leave_out" },
        c: { kind: "not_a_module" },
      },
      [{ moduleId: 9, label: "Sim Co LFO", hp: 4, row: 1, startHp: 2 }],
    );

    expect(body).toEqual({
      undecided: [],
      body: {
        items: [{ sighting_id: "a", module_id: 7, row_index: 0, start_hp: 0 }],
        added: [{ module_id: 9, row_index: 1, start_hp: 2 }],
        excluded: ["b", "c"],
        case_id: null,
      },
    });
  });

  it("names every Sighting still to decide", () => {
    const { undecided } = confirmBody(
      {
        a: kept,
        b: { kind: "undecided", row: 0, startHp: 10 },
        c: { kind: "undecided", row: 1, startHp: 0 },
      },
      [],
    );

    expect(undecided).toEqual(["b", "c"]);
  });

  it("finds Modules that would share HP in a row", () => {
    expect(
      clashes([
        { key: "a", row: 0, startHp: 0, hp: 10 },
        { key: "b", row: 0, startHp: 8, hp: 4 },
        { key: "c", row: 0, startHp: 12, hp: 4 },
        { key: "d", row: 1, startHp: 0, hp: 10 },
      ]),
    ).toEqual(new Set(["a", "b"]));
  });
});

describe("a named Case", () => {
  it("finds Modules on a row it doesn't have, or past the end of a row", () => {
    const placed = [
      { key: "fits", row: 0, startHp: 0, hp: 84 },
      { key: "past-end", row: 1, startHp: 60, hp: 8 },
      { key: "no-such-row", row: 2, startHp: 0, hp: 4 },
    ];

    expect(pastCase(placed, [84, 64])).toEqual(new Set(["past-end", "no-such-row"]));
    // With no Case, a row is as wide as what's on it.
    expect(pastCase(placed, null)).toEqual(new Set());
  });
});

describe("naming what's in the way", () => {
  it("names each Module with its row and HP, in the order shown", () => {
    const placed = [
      { key: "a", row: 0, startHp: 0, hp: 12, label: "Mutable Instruments Plaits" },
      { key: "b", row: 0, startHp: 10, hp: 20, label: "Make Noise Maths" },
      { key: "c", row: 1, startHp: 0, hp: 14, label: "Mutable Instruments Rings" },
    ];

    expect(namePlaced(placed, new Set(["b", "a"]))).toBe(
      "Mutable Instruments Plaits (row 0, HP 0 to 12) and Make Noise Maths (row 0, HP 10 to 30)",
    );
    expect(namePlaced(placed, new Set(["a", "b", "c"]))).toBe(
      "Mutable Instruments Plaits (row 0, HP 0 to 12), Make Noise Maths (row 0, HP 10 to 30) and Mutable Instruments Rings (row 1, HP 0 to 14)",
    );
  });
});

describe("reasons in words", () => {
  it("explains why a Reading failed, and has words for a code it doesn't know", () => {
    expect(readingReason("PROVIDER_TIMED_OUT")).toMatch(/took too long/i);
    expect(readingReason("CONSENT_NOT_GRANTED")).toMatch(/agree/i);
    expect(readingReason("SOMETHING_NEW")).toMatch(/couldn't be read/i);
  });

  it("explains why a confirmation was refused", () => {
    expect(refusalWords("POSITIONS_OVERLAP")).toMatch(/overlap/i);
    expect(refusalWords("READINGS_CHANGED")).toMatch(/changed/i);
    expect(refusalWords("SOMETHING_NEW")).toMatch(/couldn't be confirmed/i);
  });
});
