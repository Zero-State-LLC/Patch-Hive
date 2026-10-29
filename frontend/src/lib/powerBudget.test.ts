import { describe, expect, it } from "vitest";
import { railMeter, summarizePower } from "./powerBudget";

describe("summarizePower", () => {
  it("keeps a module's known rails when another rail is missing", () => {
    const s = summarizePower([
      { power_12v_ma: 60, power_neg12v_ma: 20, power_5v_ma: 0 },
      { power_12v_ma: null, power_neg12v_ma: 30, power_5v_ma: null },
    ]);
    expect(s.p12).toEqual({ known: 60, unknown: 1 });
    expect(s.n12).toEqual({ known: 50, unknown: 0 });
    expect(s.p5).toEqual({ known: 0, unknown: 1 });
    expect(s.fullyKnown).toBe(1);
    expect(s.total).toBe(2);
  });

  it("counts a module that is not loaded as unknown on every rail", () => {
    const s = summarizePower([undefined]);
    expect([s.p12.unknown, s.n12.unknown, s.p5.unknown]).toEqual([1, 1, 1]);
  });
});

describe("railMeter", () => {
  it("warns when unknown draws make the budget a lower bound", () => {
    const m = railMeter({ known: 300, unknown: 2 }, 1000);
    expect(m.tone).toBe("warning");
    expect(m.label).toBe("at least 300/1000mA + 2 unknown · at most 700mA headroom");
  });

  it("is danger when known draws alone exceed capacity", () => {
    expect(railMeter({ known: 1200, unknown: 1 }, 1000).tone).toBe("danger");
  });

  it("is success when every draw is known and fits", () => {
    const m = railMeter({ known: 200, unknown: 0 }, 1000);
    expect(m.tone).toBe("success");
    expect(m.label).toBe("200/1000mA · headroom 800mA");
  });

  it("is neutral when the case capacity is unspecified", () => {
    expect(railMeter({ known: 50, unknown: 1 }, null).label).toBe(
      "draw 50mA + 1 unknown · case capacity unspecified",
    );
  });
});
