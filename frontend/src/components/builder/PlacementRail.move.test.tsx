/**
 * Moving placed modules by keyboard: Enter picks one up, arrows move it, Enter drops it, Escape
 * puts it back, Delete removes it. A slot it can't take is shown and never offered.
 */
import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { checkSlot } from "@/lib/placementMove";
import type { RackModuleSpec } from "@/types/api";
import PlacementRail, { type RailModule } from "./PlacementRail";

const MODULES: Record<number, RailModule> = {
  1: { brand: "Sim", name: "Alpha", hp: 10, power_12v_ma: 40 },
  2: { brand: "Sim", name: "Beta", hp: 8, power_12v_ma: 20 },
};

// Alpha at 0 to 9 and Beta at 10 to 17 on row 0; row 1 is empty.
const placements: RackModuleSpec[] = [
  { module_id: 1, row_index: 0, start_hp: 0 },
  { module_id: 2, row_index: 0, start_hp: 10 },
];
const resolveHp = (id: number) => MODULES[id]?.hp ?? null;

function renderRail(overrides: Partial<Parameters<typeof PlacementRail>[0]> = {}) {
  const onMove = vi.fn();
  const onRemove = vi.fn();
  const onPickSlot = vi.fn();
  render(
    <PlacementRail
      rows={[
        { row: 0, capacity: 84, used: 18, free: 66 },
        { row: 1, capacity: 84, used: 0, free: 84 },
      ]}
      placements={placements}
      moduleFor={(spec) => MODULES[spec.module_id]}
      resolveHp={resolveHp}
      preview={null}
      batchPlan={[]}
      onPickSlot={onPickSlot}
      checkSlot={(slot, ignore) =>
        checkSlot(
          slot,
          placements,
          [84, 84],
          resolveHp,
          (spec) => MODULES[spec.module_id].name,
          ignore,
        )
      }
      onMove={onMove}
      onRemove={onRemove}
      {...overrides}
    />,
  );
  return { onMove, onRemove, onPickSlot };
}

const block = (name: string) => screen.getByRole("button", { name: new RegExp(name) });

/** A row's track, laid out 840 px wide from x = 0 (10 px per HP), as jsdom has no layout. */
function trackOf(row: number) {
  const track = document.querySelector<HTMLElement>(`[data-rail-row="${row}"]`)!;
  track.getBoundingClientRect = () =>
    ({ left: 0, width: 840, top: 0, height: 120, right: 840, bottom: 120 }) as DOMRect;
  return track;
}

describe("PlacementRail keyboard moves", () => {
  it("picks a module up, moves it 1 HP or 4 with Shift, and drops it", async () => {
    const user = userEvent.setup();
    const { onMove, onPickSlot } = renderRail();
    block("Beta").focus();

    await user.keyboard("{Enter}");
    expect(screen.getByText(/Beta picked up at row 0 at 10 HP/)).toBeInTheDocument();

    await user.keyboard("{ArrowRight}{Shift>}{ArrowRight}{/Shift}");
    expect(screen.getByText("row 0 at 15 HP.")).toBeInTheDocument();

    await user.keyboard("{Enter}");
    expect(onMove).toHaveBeenCalledWith(1, 0, 15);
    // Enter moved the module; it did not also pick a slot for the next placement.
    expect(onPickSlot).not.toHaveBeenCalled();
  });

  it("changes rows with Down", async () => {
    const user = userEvent.setup();
    const { onMove } = renderRail();
    block("Alpha").focus();

    await user.keyboard("{Enter}{ArrowDown}{Enter}");

    expect(onMove).toHaveBeenCalledWith(0, 1, 0);
  });

  it("shows a blocked slot in red with the reason, and won't drop there", async () => {
    const user = userEvent.setup();
    const { onMove } = renderRail();
    block("Alpha").focus();

    await user.keyboard("{Enter}{ArrowRight}");
    expect(screen.getByText("Can't go there. Overlaps Beta at HP 10 to 17.")).toBeInTheDocument();
    expect(document.querySelector(".rack-row-map__block--ghost")).toHaveAttribute(
      "data-state",
      "blocked",
    );

    await user.keyboard("{Enter}");
    expect(onMove).not.toHaveBeenCalled();
    expect(
      screen.getByText(/Alpha can't go there\. Overlaps Beta at HP 10 to 17\. It stays at row 0/),
    ).toBeInTheDocument();
  });

  it("puts the module back with Escape", async () => {
    const user = userEvent.setup();
    const { onMove } = renderRail();
    block("Beta").focus();

    await user.keyboard("{Enter}{ArrowRight}{Escape}");

    expect(onMove).not.toHaveBeenCalled();
    expect(screen.getByText("Beta put back at row 0 at 10 HP.")).toBeInTheDocument();
    expect(document.querySelector(".rack-row-map__block--ghost")).toBeNull();
  });

  it("removes a module with Delete", async () => {
    const user = userEvent.setup();
    const { onRemove } = renderRail();
    block("Beta").focus();

    await user.keyboard("{Delete}");

    expect(onRemove).toHaveBeenCalledWith(1);
  });

  it("waits while a save is under way", async () => {
    const user = userEvent.setup();
    const { onMove } = renderRail({ busy: true });
    block("Beta").focus();

    await user.keyboard("{Enter}{ArrowRight}{Enter}");

    expect(onMove).not.toHaveBeenCalled();
  });

  it("moves a module with two clicks, no dragging needed", async () => {
    const user = userEvent.setup();
    const { onMove, onPickSlot } = renderRail();
    const track = trackOf(0);

    await user.click(block("Beta"));
    expect(
      screen.getByText(/Beta picked up at row 0 at 10 HP\. Click or tap its new spot/),
    ).toBeInTheDocument();

    // 10 px per HP: a click at HP 42 centres the 8 HP module there, so it starts at 38.
    fireEvent.click(track, { clientX: 420 });
    expect(onMove).toHaveBeenCalledWith(1, 0, 38);
    // A placed module is never offered as the next placement's slot.
    expect(onPickSlot).not.toHaveBeenCalled();
  });

  it("keeps a clicked module picked up on a spot it can't take, and says why", async () => {
    const user = userEvent.setup();
    const { onMove } = renderRail();
    const track = trackOf(0);

    await user.click(block("Beta"));
    fireEvent.click(track, { clientX: 60 });

    expect(onMove).not.toHaveBeenCalled();
    expect(screen.getByText("Can't go there. Overlaps Alpha at HP 0 to 9.")).toBeInTheDocument();
    expect(document.querySelector(".rack-row-map__block--ghost")).toHaveAttribute(
      "data-state",
      "blocked",
    );

    await user.click(block("Beta"));
    expect(screen.getByText("Beta put back at row 0 at 10 HP.")).toBeInTheDocument();
    expect(document.querySelector(".rack-row-map__block--ghost")).toBeNull();
  });

  it("shows the reason under the row the blocked slot is on", async () => {
    const user = userEvent.setup();
    renderRail();
    block("Alpha").focus();

    await user.keyboard("{Enter}{ArrowRight}");

    const why = screen.getByText("Can't go there. Overlaps Beta at HP 10 to 17.");
    expect(why.closest(".hp-usage__row")).toHaveTextContent("Row 0");
  });

  it("keeps its hint drawn while a save is under way", () => {
    renderRail({ busy: true });
    expect(screen.getByText("Saving…")).toBeInTheDocument();
  });
});
