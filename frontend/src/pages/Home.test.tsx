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

  it("walks the path from rig to book in order", () => {
    renderHome();
    const path = screen.getByRole("region", { name: "From rig to book" });
    expect(
      within(path)
        .getAllByRole("listitem")
        .map((li) => li.querySelector("strong")?.textContent),
    ).toEqual(["Confirm the rig", "Generate patches", "Export the book"]);
    expect(screen.queryByText("Product law")).not.toBeInTheDocument();
  });

  it("offers sign-in when accounts are open and the visitor is signed out", () => {
    renderHome();
    expect(screen.getByRole("link", { name: "Sign in" })).toHaveAttribute("href", "/login");
    expect(screen.getByRole("link", { name: "Placeable modules" })).toHaveClass("button-secondary");
  });

  it("opens rigs for a signed-in visitor", () => {
    useAuthStore.setState({ token: "token" });
    renderHome();
    expect(screen.getByRole("link", { name: "Open rigs" })).toHaveAttribute("href", "/racks");
    expect(screen.queryByRole("link", { name: "Sign in" })).not.toBeInTheDocument();
  });

  it("leaves only the catalog when accounts are closed", () => {
    accounts.open = false;
    renderHome();
    expect(screen.queryByRole("link", { name: "Sign in" })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Placeable modules" })).toHaveClass("button-primary");
  });
});
