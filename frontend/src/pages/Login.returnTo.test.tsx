/**
 * Signing in returns to the screen that sent the visitor to sign in, never to another site.
 */
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

const api = vi.hoisted(() => ({
  authApi: { login: vi.fn(), register: vi.fn() },
}));

vi.mock("@/lib/api", () => api);

import LoginPage from "./Login";

const USER = {
  id: 1,
  username: "demo",
  email: "demo@example.test",
  role: "User",
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

function renderAt(state: unknown) {
  render(
    <MemoryRouter initialEntries={[{ pathname: "/login", state }]}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/account" element={<p>Account screen</p>} />
        <Route path="/racks" element={<p>Rigs screen</p>} />
      </Routes>
    </MemoryRouter>,
  );
}

async function signIn() {
  const user = userEvent.setup();
  await user.type(screen.getByLabelText("Username"), "demo");
  await user.type(screen.getByLabelText("Password"), "demo-pass");
  await user.click(screen.getByRole("button", { name: "Sign in to PatchHive" }));
}

beforeEach(() => {
  api.authApi.login.mockReset();
  api.authApi.login.mockResolvedValue({ data: { user: USER, access_token: "token" } });
});

describe("Login return path", () => {
  it("returns to the screen that asked for a sign-in", async () => {
    renderAt({ from: "/account" });
    await signIn();
    expect(await screen.findByText("Account screen")).toBeInTheDocument();
  });

  it("goes to the rigs when nothing asked", async () => {
    renderAt(null);
    await signIn();
    expect(await screen.findByText("Rigs screen")).toBeInTheDocument();
  });

  it("ignores a return path that leaves the app", async () => {
    renderAt({ from: "//evil.example/steal" });
    await signIn();
    expect(await screen.findByText("Rigs screen")).toBeInTheDocument();
  });
});
