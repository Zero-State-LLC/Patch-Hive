import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it } from "vitest";
import Tabs from "./Tabs";

type Key = "overview" | "patches" | "exports" | "gallery";

function Harness({ exportsDisabled = false }: { exportsDisabled?: boolean }) {
  const [active, setActive] = useState<Key>("overview");
  return (
    <Tabs
      label="Rig sections"
      tabs={[
        { key: "overview", label: "Overview" },
        { key: "patches", label: "Patches" },
        { key: "exports", label: "Exports", disabled: exportsDisabled },
        { key: "gallery", label: "Module gallery" },
      ]}
      active={active}
      onChange={setActive}
    />
  );
}

describe("Tabs", () => {
  it("keeps only the selected tab in the tab order and points it at its panel", () => {
    render(<Harness />);
    const overview = screen.getByRole("tab", { name: "Overview" });
    expect(overview).toHaveAttribute("aria-selected", "true");
    expect(overview).toHaveAttribute("tabindex", "0");
    expect(overview).toHaveAttribute("aria-controls", "panel-overview");
    expect(screen.getByRole("tab", { name: "Patches" })).toHaveAttribute("tabindex", "-1");
  });

  it("moves and selects with the arrow keys, wrapping and skipping disabled tabs", async () => {
    const user = userEvent.setup();
    render(<Harness exportsDisabled />);
    await user.click(screen.getByRole("tab", { name: "Overview" }));

    await user.keyboard("{ArrowRight}");
    expect(screen.getByRole("tab", { name: "Patches" })).toHaveFocus();
    expect(screen.getByRole("tab", { name: "Patches" })).toHaveAttribute("aria-selected", "true");

    await user.keyboard("{ArrowRight}");
    expect(screen.getByRole("tab", { name: "Module gallery" })).toHaveFocus();

    await user.keyboard("{ArrowRight}");
    expect(screen.getByRole("tab", { name: "Overview" })).toHaveFocus();

    await user.keyboard("{ArrowLeft}");
    expect(screen.getByRole("tab", { name: "Module gallery" })).toHaveFocus();
  });

  it("jumps to the ends with Home and End", async () => {
    const user = userEvent.setup();
    render(<Harness />);
    await user.click(screen.getByRole("tab", { name: "Patches" }));

    await user.keyboard("{End}");
    expect(screen.getByRole("tab", { name: "Module gallery" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    await user.keyboard("{Home}");
    expect(screen.getByRole("tab", { name: "Overview" })).toHaveFocus();
  });
});
