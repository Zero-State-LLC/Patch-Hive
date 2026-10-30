import { describe, expect, it } from "vitest";
import { placementPower, railMeter, summarizePower } from "./powerBudget";

describe("placementPower", () => {
  const qcd = {
    power_12v_ma: null,
    power_neg12v_ma: 40,
    power_5v_ma: null,
    power_configs: [
      { id: 7, power_12v_ma: 48, power_neg12v_ma: 40, power_5v_ma: 41 },
      { id: 8, power_12v_ma: 88, power_neg12v_ma: 40, power_5v_ma: 0 },
    ],
  };

  it("uses the chosen setting's draws", () => {
    const s = summarizePower([placementPower(qcd, 8)]);
    expect([s.p12, s.n12, s.p5]).toEqual([
      { known: 88, unknown: 0 },
      { known: 40, unknown: 0 },
      { known: 0, unknown: 0 },
    ]);
  });

  it("leaves the jumper rails unknown when no setting is chosen", () => {
    const s = summarizePower([placementPower(qcd, null)]);
    expect([s.p12.unknown, s.n12.unknown, s.p5.unknown]).toEqual([1, 0, 1]);
  });

  it("falls back to the module when the setting is not its own", () => {
    expect(placementPower(qcd, 99)).toBe(qcd);
    expect(placementPower(undefined, 7)).toBeUndefined();
  });
});

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
