import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Link, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import RouteEffects from "./RouteEffects";

function Shell({ start }: { start: string }) {
  return (
    <MemoryRouter initialEntries={[start]}>
      <RouteEffects />
      <nav>
        <Link to="/modules">Modules</Link>
        <Link to="/modules#filters">Filters</Link>
        <Link to="/racks/2">Second rig</Link>
      </nav>
      <main id="main-content" tabIndex={-1}>
        <Routes>
          <Route path="/racks" element={<p>Rigs screen</p>} />
          <Route path="/racks/:rigId" element={<p>Rigs screen, one rig chosen</p>} />
          <Route path="/modules" element={<p>Modules screen</p>} />
        </Routes>
      </main>
    </MemoryRouter>
  );
}

let scrollTo: ReturnType<typeof vi.spyOn>;

beforeEach(() => {
  scrollTo = vi.spyOn(window, "scrollTo").mockImplementation(() => {});
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("RouteEffects", () => {
  it("names the first screen without moving focus", () => {
    render(<Shell start="/racks" />);
    expect(document.title).toBe("Rigs, PatchHive");
    expect(document.getElementById("main-content")).not.toHaveFocus();
    expect(scrollTo).not.toHaveBeenCalled();
  });

  it("names the new screen, scrolls to the top and focuses the workspace", async () => {
    const user = userEvent.setup();
    render(<Shell start="/racks" />);

    await user.click(screen.getByRole("link", { name: "Modules" }));

    expect(screen.getByText("Modules screen")).toBeInTheDocument();
    expect(document.title).toBe("Modules, PatchHive");
    expect(scrollTo).toHaveBeenCalledWith(0, 0);
    expect(document.getElementById("main-content")).toHaveFocus();
  });

  it("leaves a link to a section of the page to the browser", async () => {
    const user = userEvent.setup();
    render(<Shell start="/racks" />);

    await user.click(screen.getByRole("link", { name: "Filters" }));

    expect(document.title).toBe("Modules, PatchHive");
    expect(scrollTo).not.toHaveBeenCalled();
    expect(document.getElementById("main-content")).not.toHaveFocus();
  });

  it("leaves focus alone for a new selection within the same screen", async () => {
    const user = userEvent.setup();
    render(<Shell start="/racks" />);
    const link = screen.getByRole("link", { name: "Second rig" });

    await user.click(link);

    expect(screen.getByText("Rigs screen, one rig chosen")).toBeInTheDocument();
    expect(document.title).toBe("Rigs, PatchHive");
    expect(scrollTo).not.toHaveBeenCalled();
    expect(link).toHaveFocus();
  });
});
