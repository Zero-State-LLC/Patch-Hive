/**
 * Hard-reload race: routes must not mount (and fetch) until the session restore settles,
 * or signed-in screens load as signed out. A visitor known to be signed out never waits.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, render, screen } from "@testing-library/react";

const session = vi.hoisted(() => ({ restoreSession: vi.fn(), signOut: vi.fn() }));

vi.mock("@/lib/session", () => session);
vi.mock("@/pages/Home", () => ({ default: () => <h1>Home route</h1> }));

import App from "./App";
import { SESSION_HINT } from "@/lib/store";

beforeEach(() => {
  window.history.pushState({}, "", "/");
});

afterEach(() => {
  session.restoreSession.mockReset();
  localStorage.removeItem(SESSION_HINT);
});

describe("App session restore", () => {
  it("serves the privacy notice and links it from the footer", async () => {
    session.restoreSession.mockResolvedValue(null);
    window.history.pushState({}, "", "/privacy");

    render(<App />);

    expect(await screen.findByRole("heading", { level: 1 })).toHaveTextContent("Privacy notice");
    expect(screen.getByRole("contentinfo")).toContainElement(
      screen.getByRole("link", { name: "Privacy notice" }),
    );
    expect(screen.getByRole("link", { name: "Privacy notice" })).toHaveAttribute(
      "href",
      "/privacy",
    );
  });

  it("holds the routes back while the restore is pending, and renders them once it settles", async () => {
    let settle: (token: string | null) => void = () => {};
    session.restoreSession.mockReturnValue(new Promise((resolve) => (settle = resolve)));

    render(<App />);

    expect(screen.getByRole("status")).toHaveTextContent("Restoring session…");
    expect(screen.queryByText("Home route")).not.toBeInTheDocument();
    // The header and footer do not wait.
    expect(screen.getByRole("navigation", { name: "Primary navigation" })).toBeInTheDocument();
    expect(screen.getByText(/Exports are the credit boundary/)).toBeInTheDocument();

    await act(async () => settle("fresh"));

    expect(screen.getByText("Home route")).toBeInTheDocument();
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("renders the routes after a failed restore too", async () => {
    let settle: (token: string | null) => void = () => {};
    session.restoreSession.mockReturnValue(new Promise((resolve) => (settle = resolve)));

    render(<App />);
    await act(async () => settle(null));

    expect(screen.getByText("Home route")).toBeInTheDocument();
  });

  it("does not make a known signed-out visitor wait", () => {
    localStorage.setItem(SESSION_HINT, "0");
    session.restoreSession.mockReturnValue(new Promise(() => {}));

    render(<App />);

    expect(screen.getByText("Home route")).toBeInTheDocument();
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });
});
