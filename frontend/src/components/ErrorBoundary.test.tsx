import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Link, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import ErrorBoundary, { RouteErrorBoundary } from "./ErrorBoundary";

function Boom(): never {
  throw new Error("render failed");
}

// React and jsdom both report the thrown render error; keep the test output clean.
const quiet = (event: ErrorEvent) => event.preventDefault();

beforeEach(() => {
  vi.spyOn(console, "error").mockImplementation(() => {});
  window.addEventListener("error", quiet);
});

afterEach(() => {
  window.removeEventListener("error", quiet);
  vi.restoreAllMocks();
});

describe("ErrorBoundary", () => {
  it("renders its children when nothing fails", () => {
    render(
      <ErrorBoundary>
        <p>Rig list</p>
      </ErrorBoundary>,
    );
    expect(screen.getByText("Rig list")).toBeInTheDocument();
  });

  it("shows a way out when a child fails to render", () => {
    render(
      <ErrorBoundary>
        <Boom />
      </ErrorBoundary>,
    );
    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent("This screen stopped working");
    expect(screen.getByRole("button", { name: "Reload" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Go home" })).toHaveAttribute("href", "/");
  });

  it("clears the error when the route changes", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={["/broken"]}>
        <Link to="/fine">Elsewhere</Link>
        <RouteErrorBoundary>
          <Routes>
            <Route path="/broken" element={<Boom />} />
            <Route path="/fine" element={<p>Working screen</p>} />
          </Routes>
        </RouteErrorBoundary>
      </MemoryRouter>,
    );
    expect(screen.getByRole("alert")).toBeInTheDocument();

    await user.click(screen.getByRole("link", { name: "Elsewhere" }));

    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.getByText("Working screen")).toBeInTheDocument();
  });
});
