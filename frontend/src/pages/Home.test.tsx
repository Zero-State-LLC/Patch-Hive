/**
 * Home shows the product: the golden demo rig on its rail with one patch's cables, then the
 * path from rig to book. The actions keep their sign-in gating.
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { DEMO_PATCH, DEMO_RIG } from "@/lib/demoRig";
import { useAuthStore } from "@/lib/store";

const accounts = vi.hoisted(() => ({ open: true }));

vi.mock("@/lib/apiBase", () => ({
  get ACCOUNTS_OPEN() {
    return accounts.open;
  },
}));

import Home from "./Home";

function renderHome() {
  return render(
    <MemoryRouter>
      <Home />
    </MemoryRouter>,
  );
}

afterEach(() => {
  accounts.open = true;
  useAuthStore.setState({ user: null, token: null });
});

describe("Home", () => {
  it("draws the demo rig on its rail with every cable of its patch", () => {
    const { container } = renderHome();
    expect(
      screen.getByRole("img", {
        name: "Voltage Lab Control Rack: 11 modules on 2 rows of 104 and 104 HP",
      }),
    ).toBeInTheDocument();
    expect(container.querySelectorAll(".home-rig .patch-cable")).toHaveLength(5);
    // Shown, not worked: the cable table stays on the workbench.
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
    expect(screen.getByText(DEMO_PATCH.name)).toBeInTheDocument();
  });

  it("plugs every demo cable into a module on the demo rig", () => {
    const placed = new Set(DEMO_RIG.modules.map((m) => m.module_id));
    for (const c of DEMO_PATCH.connections) {
      expect(placed.has(c.from_module_id) && placed.has(c.to_module_id)).toBe(true);
    }
  });

  it("keys only the signals the patch uses", () => {
    renderHome();
    const key = screen.getByRole("list", { name: "Cable key" });
    expect(
      within(key)
        .getAllByRole("listitem")
        .map((li) => li.textContent),
    ).toEqual(["Audio", "CV", "Gate"]);
  });

  it("walks the path from photo to book in order", () => {
    renderHome();
    const path = screen.getByRole("region", { name: "From photo to book" });
    expect(
      within(path)
        .getAllByRole("listitem")
        .map((li) => li.querySelector("strong")?.textContent),
    ).toEqual(["Photograph the Rig", "Check the reading", "Export the book"]);
    expect(screen.queryByText("Product law")).not.toBeInTheDocument();
  });

  it("shows an example reading of the demo rig, in words", () => {
    renderHome();
    const example = screen.getByRole("list", { name: "An example reading" });
    const items = within(example).getAllByRole("listitem");
    expect(items).toHaveLength(3);
    expect(items[0]).toHaveTextContent(/^Sure/);
    expect(items[0]).toHaveTextContent(DEMO_RIG.modules[0].module?.name ?? "");
  });

  it("asks a signed-out visitor to sign in before photographing their Rig", () => {
    renderHome();
    expect(screen.getByRole("link", { name: "Photograph your Rig" })).toHaveAttribute(
      "href",
      "/login",
    );
    // The catalog is what a reading matches against, not something to browse (decision 58).
    expect(screen.queryByRole("link", { name: "Placeable modules" })).not.toBeInTheDocument();
  });

  it("takes a signed-in owner straight to the photo, and to their Rigs", () => {
    useAuthStore.setState({ token: "token" });
    renderHome();
    const primary = screen.getByRole("link", { name: "Photograph your Rig" });
    expect(primary).toHaveAttribute("href", "/rigs/new/photo");
    expect(primary).toHaveClass("button-primary");
    expect(screen.getByRole("link", { name: "My Rigs" })).toHaveAttribute("href", "/racks");
  });

  it("keeps the photo as the main action when accounts are closed", () => {
    accounts.open = false;
    renderHome();
    expect(screen.getByRole("link", { name: "Photograph your Rig" })).toHaveClass("button-primary");
  });
});
