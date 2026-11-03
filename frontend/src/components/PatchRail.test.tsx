import { act, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import axe from "axe-core";
import { describe, expect, it } from "vitest";
import PatchRail from "./PatchRail";
import type { Connection, Patch, Rack, RackModule } from "@/types/api";

function placed(id: number, moduleId: number, startHp: number, name: string, hp = 8): RackModule {
  return {
    id,
    module_id: moduleId,
    row_index: 0,
    start_hp: startHp,
    module: { id: moduleId, brand: "Test", name, hp, module_type: "VCO" },
  };
}

function rackWith(modules: RackModule[], hpPerRow: number[] = [84]): Rack {
  return {
    id: 1,
    user_id: 1,
    case_id: 1,
    name: "Bench rig",
    tags: [],
    is_public: false,
    vote_count: 0,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    modules,
    case: {
      id: 1,
      brand: "Test",
      name: "Case",
      total_hp: hpPerRow.reduce((a, b) => a + b, 0),
      rows: hpPerRow.length,
      hp_per_row: hpPerRow,
    },
  };
}

function patchWith(connections: Connection[], id = 7): Patch {
  return {
    id,
    rack_id: 1,
    name: "Slow drift",
    category: "texture",
    connections,
    generation_seed: 1,
    generation_version: "test",
    is_public: false,
    vote_count: 0,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  };
}

const cable = (from: number, to: number, type = "audio"): Connection => ({
  from_module_id: from,
  from_port: "out",
  to_module_id: to,
  to_port: "in",
  cable_type: type,
});

const modules = [placed(101, 1, 0, "Oscillator"), placed(102, 2, 10, "Filter")];

describe("PatchRail", () => {
  it("draws a cable for every connection with an end on the rig", () => {
    const { container } = render(
      <PatchRail
        rack={rackWith(modules)}
        patch={patchWith([cable(1, 2), cable(1, 99, "cv"), cable(98, 97)])}
      />,
    );
    const drawn = container.querySelectorAll(".patch-cable");
    expect(drawn).toHaveLength(2);
    expect(drawn[1]).toHaveClass("patch-cable--cv");
    expect(screen.getByText("Slow drift: 3 cables, 2 drawn on the rail")).toBeInTheDocument();
  });

  it("lists every cable in the table and names ends that are not on the rig", () => {
    render(<PatchRail rack={rackWith(modules)} patch={patchWith([cable(1, 2), cable(1, 99)])} />);
    const rows = screen.getAllByRole("row").slice(1);
    expect(rows).toHaveLength(2);
    const [from, to] = within(rows[0]).getAllByRole("cell");
    expect(from).toHaveTextContent("Test Oscillatorout");
    expect(to).toHaveTextContent("Test Filterin");
    expect(within(rows[0]).queryByText(/not on this rig/)).not.toBeInTheDocument();
    expect(within(rows[1]).getByText("Module #99")).toBeInTheDocument();
    expect(within(rows[1]).getByText("an end is not on this rig")).toBeInTheDocument();
  });

  it("draws a module placed twice at its first position and says so", () => {
    const twice = [...modules, placed(103, 2, 40, "Filter")];
    const { container } = render(
      <PatchRail rack={rackWith(twice)} patch={patchWith([cable(1, 2)])} />,
    );
    expect(container.querySelectorAll(".patch-cable")).toHaveLength(1);
    expect(
      screen.getByText("module placed twice; drawn at its first position"),
    ).toBeInTheDocument();
  });

  it("fills the output plug, rings the input and stacks jacks that share a faceplate", () => {
    const { container } = render(
      <PatchRail rack={rackWith(modules)} patch={patchWith([cable(1, 2), cable(2, 1)])} />,
    );
    const [first, second] = Array.from(container.querySelectorAll(".patch-cable"));
    const plugs = (g: Element) => Array.from(g.querySelectorAll("circle"));
    expect(plugs(first)[0]).toHaveClass("patch-cable__plug--out");
    expect(plugs(first)[1]).not.toHaveClass("patch-cable__plug--out");
    // The filter's second cable plugs in one step below its first.
    const firstY = Number(plugs(first)[1].getAttribute("cy"));
    const secondY = Number(plugs(second)[0].getAttribute("cy"));
    expect(secondY - firstY).toBe(10);
  });

  it("clears the picked cable when the patch changes", async () => {
    const user = userEvent.setup();
    const rack = rackWith(modules);
    const { container, rerender } = render(
      <PatchRail rack={rack} patch={patchWith([cable(1, 2), cable(2, 1, "gate")])} />,
    );
    await act(async () => {
      await user.click(screen.getByRole("button", { name: "Cable 2" }));
    });
    expect(container.querySelector(".is-dimmed")).not.toBeNull();

    rerender(<PatchRail rack={rack} patch={patchWith([cable(1, 2)], 8)} />);
    expect(container.querySelector(".is-dimmed")).toBeNull();
    expect(container.querySelector(".is-selected")).toBeNull();
    expect(screen.getByRole("button", { name: "Cable 1" })).toHaveAttribute(
      "aria-pressed",
      "false",
    );
  });

  it("says so when a patch has no cables", () => {
    render(<PatchRail rack={rackWith(modules)} patch={patchWith([])} />);
    expect(screen.getByText("This patch has no cables yet.")).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("highlights the picked cable and dims the rest", async () => {
    const user = userEvent.setup();
    const { container } = render(
      <PatchRail rack={rackWith(modules)} patch={patchWith([cable(1, 2), cable(2, 1, "gate")])} />,
    );
    const pick = screen.getByRole("button", { name: "Cable 2" });
    expect(pick).toHaveAttribute("aria-pressed", "false");
    await act(async () => {
      await user.click(pick);
    });
    expect(pick).toHaveAttribute("aria-pressed", "true");
    const drawn = container.querySelectorAll(".patch-cable");
    expect(drawn[0]).toHaveClass("is-dimmed");
    expect(drawn[1]).toHaveClass("is-selected");
    await act(async () => {
      await user.click(pick);
    });
    expect(pick).toHaveAttribute("aria-pressed", "false");
    expect(container.querySelector(".is-dimmed")).toBeNull();
  });

  it("draws the cables without the table where the rail is only shown", () => {
    const { container } = render(
      <PatchRail rack={rackWith(modules)} patch={patchWith([cable(1, 2)])} table={false} />,
    );
    expect(container.querySelectorAll(".patch-cable")).toHaveLength(1);
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Cable 1" })).not.toBeInTheDocument();
  });

  it("falls back to the table when the case states no HP per row", () => {
    const { container } = render(
      <PatchRail rack={rackWith(modules, [])} patch={patchWith([cable(1, 2)])} />,
    );
    expect(container.querySelector(".patch-rail__cables")).toBeNull();
    expect(screen.getByText(/does not state HP per row/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Cable 1" })).toBeInTheDocument();
  });

  it("has no automated axe violations", async () => {
    const { container } = render(
      <main>
        <PatchRail rack={rackWith(modules)} patch={patchWith([cable(1, 2), cable(1, 99, "cv")])} />
      </main>,
    );
    const results = await axe.run(container, {
      rules: { "color-contrast": { enabled: false } },
    });
    expect(results.violations).toEqual([]);
  });
});
