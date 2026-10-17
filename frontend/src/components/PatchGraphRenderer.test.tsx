import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import axe from "axe-core";
import { describe, expect, it } from "vitest";
import PatchGraphRenderer from "./PatchGraphRenderer";
import { CANON_SCHEMA_VERSION, type PatchGraph } from "@/types/canon";

const graph: PatchGraph = {
  schema_version: CANON_SCHEMA_VERSION,
  artifact_id: "patch-1",
  nodes: [
    {
      schema_version: CANON_SCHEMA_VERSION,
      node_id: "osc",
      module_instance_id: "osc",
      label: "Oscillator",
      ports: [
        {
          schema_version: CANON_SCHEMA_VERSION,
          port_id: "osc.out",
          module_instance_id: "osc",
          module_port_id: "out",
          label: "OUT",
          direction: "output",
          signal_type: "audio",
        },
      ],
    },
    {
      schema_version: CANON_SCHEMA_VERSION,
      node_id: "filter",
      module_instance_id: "filter",
      label: "Filter",
      ports: [
        {
          schema_version: CANON_SCHEMA_VERSION,
          port_id: "filter.in",
          module_instance_id: "filter",
          module_port_id: "in",
          label: "IN",
          direction: "input",
          signal_type: "audio",
        },
      ],
    },
  ],
  edges: [
    {
      schema_version: CANON_SCHEMA_VERSION,
      edge_id: "cable-1",
      source_port_id: "osc.out",
      target_port_id: "filter.in",
      signal_type: "audio",
    },
  ],
};

describe("PatchGraphRenderer", () => {
  it("provides three views and a structured cable alternative", async () => {
    const user = userEvent.setup();
    render(<PatchGraphRenderer graph={graph} />);
    expect(screen.getByRole("table", { name: /structured cable list/i })).toBeInTheDocument();
    expect(screen.getByText(/osc · out/i)).toBeInTheDocument();
    await act(async () => {
      await user.click(screen.getByLabelText("Diagnostic"));
    });
    expect(screen.getByLabelText("Diagnostic")).toBeChecked();
  });

  it("synchronizes cable selection and exposes zoom controls", async () => {
    const user = userEvent.setup();
    render(<PatchGraphRenderer graph={graph} />);
    const cable = screen.getByRole("button", { name: "cable-1" });
    await act(async () => {
      await user.click(cable);
    });
    expect(cable).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "Zoom in" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Zoom out" })).toBeInTheDocument();
  });

  it("has no automated axe violations", async () => {
    const { container } = render(
      <main>
        <PatchGraphRenderer graph={graph} />
      </main>,
    );
    const results = await axe.run(container, {
      rules: { "color-contrast": { enabled: false } },
    });
    expect(results.violations).toEqual([]);
  });
});
