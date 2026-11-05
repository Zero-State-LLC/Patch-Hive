/**
 * The Account page around the delete control: the whole path from the dashboard to a signed-out
 * "Account deleted" screen, with no sign-out call for a session the API has already ended.
 */
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import axios from "axios";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const api = vi.hoisted(() => ({
  accountApi: {
    deleteAccount: vi.fn(),
    getCredits: vi.fn(),
    getExports: vi.fn(),
    getReferrals: vi.fn(),
  },
  authApi: { getMe: vi.fn(), updateProfile: vi.fn() },
  canonApi: { createDownloadToken: vi.fn() },
}));

vi.mock("@/lib/api", () => api);

import { SESSION_HINT, useAuthStore } from "@/lib/store";
import AccountPage from "./Account";

const USER = {
  id: 1,
  username: "demo-user",
  email: "demo@example.test",
  role: "User",
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

beforeEach(() => {
  useAuthStore.getState().setAuth(USER, "token");
  api.authApi.getMe.mockResolvedValue({ data: USER });
  api.accountApi.getCredits.mockResolvedValue({ data: { balance: 3, entries: [] } });
  api.accountApi.getExports.mockResolvedValue({ data: [] });
  api.accountApi.getReferrals.mockRejectedValue(new Error("off"));
});

afterEach(() => {
  useAuthStore.getState().clear();
  localStorage.removeItem(SESSION_HINT);
  vi.restoreAllMocks();
  api.accountApi.deleteAccount.mockReset();
});

function renderPage() {
  render(
    <MemoryRouter>
      <AccountPage />
    </MemoryRouter>,
  );
}

describe("Account page, deleting the account", () => {
  it("offers the control to the signed-in person", async () => {
    renderPage();

    expect(await screen.findByRole("button", { name: "Delete account…" })).toBeVisible();
    expect(screen.getByRole("heading", { level: 2, name: "Delete account" })).toBeVisible();
  });

  it("signs out without a logout call and replaces the dashboard", async () => {
    const logout = vi.spyOn(axios, "post");
    api.accountApi.deleteAccount.mockResolvedValue(undefined);
    const user = userEvent.setup();
    renderPage();

    await user.click(await screen.findByRole("button", { name: "Delete account…" }));
    await user.type(screen.getByLabelText(/Type your username/), USER.username);
    await user.type(screen.getByLabelText("Current password"), "correct horse");
    await user.click(screen.getByRole("button", { name: "Delete my account" }));

    const heading = await screen.findByRole("heading", { level: 1, name: "Account deleted" });
    await waitFor(() => expect(heading).toHaveFocus());
    expect(screen.getByText(/You're signed out/)).toBeVisible();
    expect(screen.getByRole("link", { name: "Return home" })).toHaveAttribute("href", "/");
    expect(screen.queryByRole("heading", { name: "Credits" })).not.toBeInTheDocument();

    expect(useAuthStore.getState().isAuthenticated()).toBe(false);
    expect(useAuthStore.getState().user).toBeNull();
    expect(localStorage.getItem(SESSION_HINT)).toBe("0");
    expect(logout).not.toHaveBeenCalled();
  });

  it("still shows the failure when the session ends during the request", async () => {
    // The API client's failed renewal clears the store before the error reaches the control.
    api.accountApi.deleteAccount.mockImplementation(async () => {
      useAuthStore.getState().clear();
      throw Object.assign(new Error("HTTP 401"), { response: { status: 401, data: {} } });
    });
    const user = userEvent.setup();
    renderPage();

    await user.click(await screen.findByRole("button", { name: "Delete account…" }));
    await waitFor(() => expect(screen.getByText(/Signed in as/)).toBeVisible());
    await user.type(screen.getByLabelText(/Type your username/), USER.username);
    await user.type(screen.getByLabelText("Current password"), "correct horse");
    await user.click(screen.getByRole("button", { name: "Delete my account" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/Your session has ended/);
    expect(screen.queryByRole("heading", { name: "Account deleted" })).not.toBeInTheDocument();
  });

  it("stays signed in on the dashboard when deletion fails", async () => {
    api.accountApi.deleteAccount.mockRejectedValue(
      Object.assign(new Error("HTTP 403"), {
        response: { status: 403, data: { detail: "PASSWORD_INCORRECT" } },
      }),
    );
    const user = userEvent.setup();
    renderPage();

    await user.click(await screen.findByRole("button", { name: "Delete account…" }));
    await user.type(screen.getByLabelText(/Type your username/), USER.username);
    await user.type(screen.getByLabelText("Current password"), "wrong");
    await user.click(screen.getByRole("button", { name: "Delete my account" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/nothing was deleted/);
    expect(useAuthStore.getState().isAuthenticated()).toBe(true);
    expect(localStorage.getItem(SESSION_HINT)).toBe("1");
    expect(screen.getByRole("heading", { level: 1, name: "Credits & profile" })).toBeVisible();
  });
});
