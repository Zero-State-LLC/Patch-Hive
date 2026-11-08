import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import ModulesToPlace from "./ModulesToPlace";

const matched = {
  instance_id: "inst-1",
  module_revision_id: "catalog-cand-1",
  manufacturer: "Make Noise",
  model: "Maths",
  module_id: 7,
};

function renderList(props: Parameters<typeof ModulesToPlace>[0]) {
  return render(
    <MemoryRouter>
      <ModulesToPlace {...props} />
    </MemoryRouter>,
  );
}

describe("ModulesToPlace", () => {
  it("draws nothing when every confirmed module is placed", () => {
    renderList({ modules: [], rackId: 3 });
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("sends a catalog module to the rack builder, preselected", () => {
    renderList({ modules: [matched], rackId: 3 });
    expect(screen.getByRole("status")).toHaveTextContent("Make Noise Maths");
    expect(screen.getByRole("link", { name: "Place it" })).toHaveAttribute(
      "href",
      "/racks/3/edit?module_id=7",
    );
  });

  it("says a module with no catalog match can't be placed yet, and never guesses an id", () => {
    renderList({ modules: [{ ...matched, module_id: null }], rackId: 3 });
    expect(screen.getByRole("status")).toHaveTextContent(
      "no catalog match yet, so it can't be placed until the catalog has it",
    );
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
  });

  it("falls back to the revision label when a confirmed item has no name", () => {
    renderList({
      modules: [{ ...matched, manufacturer: null, model: null, module_id: null }],
      rackId: 3,
    });
    expect(screen.getByRole("status")).toHaveTextContent("catalog-cand-1");
  });
});
