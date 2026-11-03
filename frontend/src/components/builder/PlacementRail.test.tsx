import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import axe from "axe-core";
import { describe, expect, it, vi } from "vitest";
import PlacementRail, { type RailModule } from "./PlacementRail";
import type { RackModuleSpec } from "@/types/api";

const MODULES: Record<number, RailModule> = {
  1: { brand: "Sim", name: "Alpha", hp: 10, power_12v_ma: 40 },
  2: { brand: "Sim", name: "Beta", hp: 8, power_12v_ma: null },
  3: { brand: "Sim", name: "Gamma", hp: 12, power_12v_ma: 20 },
};

const placements: RackModuleSpec[] = [
  { module_id: 1, row_index: 0, start_hp: 0 },
  { module_id: 2, row_index: 0, start_hp: 10 },
];

function renderRail(overrides: Partial<Parameters<typeof PlacementRail>[0]> = {}) {
  const onPickSlot = vi.fn();
  const utils = render(
    <PlacementRail
      rows={[{ row: 0, capacity: 84, used: 18, free: 66 }]}
      placements={placements}
      moduleFor={(spec) => MODULES[spec.module_id]}
      resolveHp={(id) => MODULES[id]?.hp ?? null}
      preview={null}
      batchPlan={[]}
      onPickSlot={onPickSlot}
      {...overrides}
    />,
  );
  return { ...utils, onPickSlot };
}

describe("PlacementRail", () => {
  it("positions each placed block from --start and --hp, not from inline lengths", () => {
    renderRail();
    const alpha = screen.getByTitle("Sim Alpha, HP 0 to 9");
    expect(alpha.style.getPropertyValue("--start")).toBe("0");
    expect(alpha.style.getPropertyValue("--hp")).toBe("10");
    expect(alpha.style.left).toBe("");
    expect(alpha.style.width).toBe("");
    const beta = screen.getByTitle("Sim Beta, HP 10 to 17, power unknown");
    expect(beta.style.getPropertyValue("--start")).toBe("10");
    expect(beta).toHaveClass("rack-row-map__block--unknown-power");
  });

  it("reports the row's HP usage as a meter that fills to its share", () => {
    const { container } = renderRail();
    expect(screen.getByRole("meter", { name: "Row 0 HP usage" })).toHaveAttribute(
      "aria-valuenow",
      "18",
    );
    const fill = container.querySelector<HTMLElement>(".usage-bar__fill");
    expect(fill?.style.getPropertyValue("--fill")).toBe(String(Math.round((18 / 84) * 100) / 100));
    expect(screen.getByText("18/84HP used, 66 free")).toBeInTheDocument();
  });

  it("picks a placed module's row and start HP when its block is clicked", async () => {
    const { onPickSlot } = renderRail();
    await userEvent.click(screen.getByRole("button", { name: /Beta/ }));
    expect(onPickSlot).toHaveBeenCalledWith(0, 10);
  });

  it("picks the HP under the pointer when the empty rail is clicked", () => {
    const { container, onPickSlot } = renderRail();
    const track = container.querySelector<HTMLElement>(".rack-row-map__track")!;
    track.getBoundingClientRect = () =>
      ({ left: 0, width: 840, top: 0, height: 120, right: 840, bottom: 120 }) as DOMRect;
    fireEvent.click(track, { clientX: 420 });
    expect(onPickSlot).toHaveBeenCalledWith(0, 42);
  });

  it("draws the next placement and a batch plan without making them clickable", () => {
    renderRail({
      preview: { module: MODULES[3], row: 0, startHp: 18 },
      batchPlan: [{ module_id: 3, row_index: 0, start_hp: 30 }],
    });
    const preview = screen.getByTitle("Preview: Sim Gamma at HP 18");
    expect(preview).toHaveAttribute("aria-hidden", "true");
    expect(preview.style.getPropertyValue("--start")).toBe("18");
    expect(screen.getByTitle("Batch plan: Sim Gamma at HP 30")).toHaveClass(
      "rack-row-map__block--batch",
    );
  });

  it("leaves a module of unknown HP off the rail rather than guessing its width", () => {
    renderRail({
      placements: [...placements, { module_id: 99, row_index: 0, start_hp: 40 }],
    });
    expect(screen.getAllByRole("button")).toHaveLength(2);
  });

  it("has no axe violations", async () => {
    const { container } = renderRail();
    // jsdom has no layout or canvas, so contrast is checked in the browser suite instead.
    const results = await axe.run(container, {
      rules: { "color-contrast": { enabled: false } },
    });
    expect(results.violations).toEqual([]);
  });
});
