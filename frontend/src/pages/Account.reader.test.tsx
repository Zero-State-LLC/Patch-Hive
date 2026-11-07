/**
 * The account page holds the most private data in the app: balance, ledger, exports, referral link
 * and profile. Signing out or a refused renewal leaves it for sign-in, with one exception: a session
 * that ends during a deletion still has to say what happened. The routes are real here, because a
 * redirect shows only with them.
 */
import { act, cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useAuthStore } from "@/lib/store";
import type { User } from "@/types/api";

const api = vi.hoisted(() => ({
  accountApi: {
    deleteAccount: vi.fn(),
    getCredits: vi.fn(),
    getExports: vi.fn(),
    getReferrals: vi.fn(),
  },
  authApi: { getMe: vi.fn(), updateProfile: vi.fn() },
  canonApi: { createDownloadToken: vi.fn(), getCommerce: vi.fn() },
}));

vi.mock("@/lib/api", () => api);

import AccountPage from "./Account";

const USER = {
  id: 1,
  username: "demo-user",
  display_name: "Private Name",
  email: "demo@example.test",
  role: "User",
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
} as unknown as User;
const SECOND = { ...USER, id: 2, username: "second-user", display_name: "Second Name" };

const CREDITS = {
  balance: 41,
  entries: [
    {
      id: 1,
      entry_type: "Grant",
      amount: 5,
      created_at: "2026-01-01T00:00:00Z",
      description: "Private ledger note",
    },
  ],
};
const REFERRALS = {
  referral_code: "PRIVATECODE",
  referral_link: "https://example.test/r/PRIVATECODE",
  pending_count: 0,
  rewarded_count: 0,
  earned_credits: 0,
};

function serve() {
  api.authApi.getMe.mockImplementation(async () => ({
    data: useAuthStore.getState().user?.id === 2 ? SECOND : USER,
  }));
  api.accountApi.getCredits.mockImplementation(async () => ({
    data: useAuthStore.getState().user?.id === 2 ? { balance: 7, entries: [] } : CREDITS,
  }));
  api.accountApi.getExports.mockResolvedValue({ data: [] });
  api.accountApi.getReferrals.mockResolvedValue({ data: REFERRALS });
  api.canonApi.getCommerce.mockResolvedValue({
    data: {
      test_mode: true,
      credit_offer: null,
      plan_offers: [],
      subscription: null,
      allowance: null,
    },
  });
}

/** The header's name for whoever the store holds. */
function Reader() {
  const username = useAuthStore((st) => st.user?.username ?? "nobody");
  return <p>Store holds {username}</p>;
}

function LoginProbe() {
  const { state } = useLocation();
  return <h1>Login screen, back to {(state as { from?: string } | null)?.from}</h1>;
}

const renderPage = () =>
  render(
    <MemoryRouter initialEntries={["/account"]}>
      <Reader />
      <Routes>
        <Route path="/account" element={<AccountPage />} />
        <Route path="/login" element={<LoginProbe />} />
      </Routes>
    </MemoryRouter>,
  );

/** The page by itself, so the redirect can't hide what it leaves on screen. */
const renderWithoutRoutes = () =>
  render(
    <MemoryRouter initialEntries={["/account"]}>
      <AccountPage />
    </MemoryRouter>,
  );

const loaded = async () => {
  await screen.findByText("41");
  await screen.findByText(/Private ledger note/);
  await screen.findByDisplayValue("https://example.test/r/PRIVATECODE");
  await screen.findByDisplayValue("Private Name");
};
const expectNothingPrivate = () => {
  expect(screen.queryByText("41")).toBeNull();
  expect(screen.queryByText(/Private ledger note/)).toBeNull();
  expect(screen.queryByDisplayValue(/PRIVATECODE/)).toBeNull();
  expect(screen.queryByDisplayValue("Private Name")).toBeNull();
  expect(screen.queryByText(/Signed in as/)).toBeNull();
};

const openDeleteAndSubmit = async () => {
  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: "Delete account…" }));
  await user.type(screen.getByLabelText(/Type your username/), USER.username);
  await user.type(screen.getByLabelText("Current password"), "correct horse");
  await user.click(screen.getByRole("button", { name: "Delete my account" }));
  return user;
};

beforeEach(() => {
  serve();
  useAuthStore.getState().setAuth(USER, "token");
});

afterEach(() => {
  cleanup();
  vi.resetAllMocks();
  useAuthStore.getState().clear();
});

describe("a change of reader on the account page", () => {
  it("goes to sign-in on sign-out, ready to come back", async () => {
    renderPage();
    await loaded();

    act(() => useAuthStore.getState().clear());

    await screen.findByRole("heading", { name: "Login screen, back to /account" });
    expectNothingPrivate();
  });

  it("leaves nothing private on the page itself once the reader is gone", async () => {
    renderWithoutRoutes();
    await loaded();

    act(() => useAuthStore.getState().clear());

    expectNothingPrivate();
  });

  it("goes to sign-in when a renewal is refused during the load", async () => {
    // A refused renewal clears the session, then the request fails with its 401 (lib/api.ts).
    api.accountApi.getCredits.mockImplementationOnce(async () => {
      useAuthStore.getState().clear();
      throw Object.assign(new Error("Unauthorized"), { response: { status: 401 } });
    });
    renderPage();

    await screen.findByRole("heading", { name: "Login screen, back to /account" });
  });

  it("doesn't put the reader back in the store when a profile load finishes after sign-out", async () => {
    let answer: (value: unknown) => void = () => {};
    api.authApi.getMe.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          answer = resolve;
        }),
    );
    renderPage();
    await waitFor(() => expect(api.authApi.getMe).toHaveBeenCalledTimes(1));

    act(() => useAuthStore.getState().clear());
    await screen.findByRole("heading", { name: "Login screen, back to /account" });

    await act(async () => answer({ data: USER }));

    expect(useAuthStore.getState().user).toBeNull();
  });

  it("doesn't put the reader back in the store when a profile save finishes after sign-out", async () => {
    let answer: (value: unknown) => void = () => {};
    api.authApi.updateProfile.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          answer = resolve;
        }),
    );
    const user = userEvent.setup();
    renderPage();
    await loaded();
    await user.click(screen.getByRole("button", { name: "Save profile" }));

    act(() => useAuthStore.getState().clear());
    await screen.findByRole("heading", { name: "Login screen, back to /account" });

    await act(async () => answer({ data: USER }));

    expect(useAuthStore.getState().user).toBeNull();
  });

  it("keeps the next account when the last one's profile save lands after it", async () => {
    let answer: (value: unknown) => void = () => {};
    api.authApi.updateProfile.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          answer = resolve;
        }),
    );
    const user = userEvent.setup();
    renderPage();
    await loaded();
    await user.click(screen.getByRole("button", { name: "Save profile" }));

    act(() => useAuthStore.getState().clear());
    await screen.findByRole("heading", { name: "Login screen, back to /account" });
    act(() => useAuthStore.getState().setAuth(SECOND, "second-token"));

    await act(async () => answer({ data: USER }));

    expect(useAuthStore.getState().user).toBe(SECOND);
    expect(screen.getByText("Store holds second-user")).toBeInTheDocument();
    expect(screen.queryByText(/demo-user/)).toBeNull();
  });

  it("drops a profile save's answer once the page has gone, even for the same account", async () => {
    let answer: (value: unknown) => void = () => {};
    api.authApi.updateProfile.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          answer = resolve;
        }),
    );
    const user = userEvent.setup();
    renderPage();
    await loaded();
    await user.click(screen.getByRole("button", { name: "Save profile" }));

    act(() => useAuthStore.getState().clear());
    await screen.findByRole("heading", { name: "Login screen, back to /account" });
    const signedInAgain = { ...USER, display_name: "From sign-in" };
    act(() => useAuthStore.getState().setAuth(signedInAgain, "new-token"));

    await act(async () => answer({ data: { ...USER, display_name: "From the old save" } }));

    expect(useAuthStore.getState().user).toBe(signedInAgain);
  });

  it("does nothing on a token renewal, which isn't a change of reader", async () => {
    const user = userEvent.setup();
    renderPage();
    await loaded();
    const name = screen.getByDisplayValue("Private Name") as HTMLInputElement;
    await user.clear(name);
    await user.type(name, "Half typed");
    const reads = api.accountApi.getCredits.mock.calls.length;

    act(() => useAuthStore.getState().setAuth(USER, "renewed-token"));

    expect(api.accountApi.getCredits).toHaveBeenCalledTimes(reads);
    expect(screen.getByDisplayValue("Half typed")).toBe(name);
  });

  it("starts over when a renewal brings back a different account", async () => {
    renderPage();
    await loaded();

    act(() => useAuthStore.getState().setAuth(SECOND, "other-token"));

    expectNothingPrivate();
    await screen.findByDisplayValue("Second Name");
    await screen.findByText("7");
  });
});

describe("a deletion that ends the session, with the real routes", () => {
  it("keeps the deleted screen instead of redirecting to sign-in", async () => {
    api.accountApi.deleteAccount.mockImplementation(async () => {
      // The API has revoked the session; the control then ends it here.
    });
    renderPage();
    await loaded();

    await openDeleteAndSubmit();

    await screen.findByRole("heading", { level: 1, name: "Account deleted" });
    expect(screen.queryByRole("heading", { name: /Login screen/ })).toBeNull();
    expect(useAuthStore.getState().isAuthenticated()).toBe(false);
  });

  it("says the session ended and shows nothing else, then goes to sign-in when closed", async () => {
    api.accountApi.deleteAccount.mockImplementation(async () => {
      useAuthStore.getState().clear();
      throw Object.assign(new Error("HTTP 401"), { response: { status: 401, data: {} } });
    });
    renderPage();
    await loaded();

    const user = await openDeleteAndSubmit();

    expect(await screen.findByRole("alert")).toHaveTextContent(/Your session has ended/);
    expect(screen.queryByRole("heading", { name: /Login screen/ })).toBeNull();
    expectNothingPrivate();

    await user.click(screen.getByRole("button", { name: "Keep my account" }));

    await screen.findByRole("heading", { name: "Login screen, back to /account" });
  });

  it("still tells the outcome, and can be closed, when the profile never loaded", async () => {
    api.authApi.getMe.mockRejectedValue(new Error("offline"));
    api.accountApi.deleteAccount.mockImplementation(async () => {
      useAuthStore.getState().clear();
      throw Object.assign(new Error("HTTP 401"), { response: { status: 401, data: {} } });
    });
    renderPage();

    const user = await openDeleteAndSubmit();

    expect(await screen.findByRole("alert")).toHaveTextContent(/Your session has ended/);

    await user.click(screen.getByRole("button", { name: "Keep my account" }));

    await screen.findByRole("heading", { name: "Login screen, back to /account" });
  });

  it("goes to sign-in on a later sign-out when a deletion was refused", async () => {
    api.accountApi.deleteAccount.mockRejectedValue(
      Object.assign(new Error("HTTP 403"), {
        response: { status: 403, data: { detail: "PASSWORD_INCORRECT" } },
      }),
    );
    renderPage();
    await loaded();

    await openDeleteAndSubmit();
    await screen.findByRole("alert");

    act(() => useAuthStore.getState().clear());

    await screen.findByRole("heading", { name: "Login screen, back to /account" });
    expectNothingPrivate();
  });
});
