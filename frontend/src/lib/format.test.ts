import { describe, expect, it } from "vitest";
import { formatDate, formatDateTime, runLabel, shortHash } from "./format";

describe("formatDate", () => {
  it("shows a day, a short month and a year", () => {
    expect(formatDate("2026-11-03T01:37:45.034542", "en-GB")).toBe("3 Nov 2026");
  });

  it("says a missing or unreadable date is not stated", () => {
    expect(formatDate(null, "en-GB")).toBe("Not stated");
    expect(formatDate("", "en-GB")).toBe("Not stated");
    expect(formatDate("not a date", "en-GB")).toBe("Not stated");
  });
});

describe("formatDateTime", () => {
  it("adds the time of day", () => {
    expect(formatDateTime("2026-11-03T14:05:00", "en-GB")).toBe("3 Nov 2026, 14:05");
  });
});

describe("runLabel", () => {
  it("names a run by its number and day", () => {
    expect(runLabel({ id: 3, created_at: "2026-11-03T01:37:45Z" }, "en-GB")).toMatch(
      /^Run 3, [23] Nov 2026$/,
    );
  });

  it("names a run without a date by its number alone", () => {
    expect(runLabel({ id: 3, created_at: null }, "en-GB")).toBe("Run 3");
  });
});

describe("shortHash", () => {
  it("keeps the first eight characters", () => {
    expect(shortHash("6f81aa715e15da27fb026c6dc788573e")).toBe("6f81aa71");
    expect(shortHash("6f81aa715e15da27", 12)).toBe("6f81aa715e15");
  });

  it("keeps an id's readable prefix and shortens the hex after it", () => {
    expect(shortHash("rig-rev-6f81aa715e15da27fb026c6dc788573e")).toBe("rig-rev-6f81aa71");
    expect(shortHash("gen-run-11-aaaaaaaaaaaaaaaa")).toBe("gen-run-11-aaaaaaaa");
  });

  it("leaves a short value whole", () => {
    expect(shortHash("abc")).toBe("abc");
  });
});
