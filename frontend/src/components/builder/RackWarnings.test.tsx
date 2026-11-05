import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import RackWarnings from "./RackWarnings";

const supply = {
  field: "power",
  message: "Any power supplied by the in-rack SYSTEM module Eowave SOURCE MK3 isn't counted.",
  details: { code: "IN_RACK_SUPPLY_NOT_COUNTED" },
};
const tombstone = {
  field: "modules[0].module_id",
  message: "Sim Alpha is retired from the catalog",
  details: { code: "MODULE_TOMBSTONED" },
};

describe("RackWarnings", () => {
  it("draws nothing for a rig with no warnings", () => {
    const { container } = render(<RackWarnings warnings={[]} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("draws nothing when the rig reload carries no warnings field", () => {
    const { container } = render(<RackWarnings warnings={undefined} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("shows the in-rack supply warning from the rig's list", () => {
    render(<RackWarnings warnings={[supply]} />);
    expect(screen.getByRole("status")).toHaveTextContent("Eowave SOURCE MK3 isn't counted");
  });

  it("leaves a retired module to the banner that gives its alternatives", () => {
    const { container } = render(<RackWarnings warnings={[tombstone]} />);
    expect(container).toBeEmptyDOMElement();
  });
});
