/**
 * While sign-up is invite-only, the form asks for a code and sends it. Otherwise it doesn't ask.
 */
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const api = vi.hoisted(() => ({
  authApi: { login: vi.fn(), register: vi.fn(), signupOptions: vi.fn() },
}));

vi.mock("@/lib/api", () => api);
vi.mock("@/lib/apiBase", () => ({ ACCOUNTS_OPEN: true }));

import LoginPage from "./Login";

const renderForm = async (user: ReturnType<typeof userEvent.setup>) => {
  render(
    <MemoryRouter>
      <LoginPage />
    </MemoryRouter>,
  );
  await waitFor(() => expect(api.authApi.signupOptions).toHaveBeenCalled());
  await user.click(screen.getByRole("tab", { name: "Create account" }));
};

const fill = async (user: ReturnType<typeof userEvent.setup>) => {
  await user.type(screen.getByLabelText("Username"), "tester");
  await user.type(screen.getByLabelText("Email"), "tester@example.test");
  await user.type(screen.getByLabelText("Password"), "correct-horse-1");
};

const submit = (user: ReturnType<typeof userEvent.setup>) =>
  user.click(screen.getByRole("button", { name: /Create account & continue/ }));

beforeEach(() => {
  api.authApi.login.mockResolvedValue({ data: { user: { id: 1 }, access_token: "t" } });
  api.authApi.register.mockResolvedValue({ data: { id: 1 } });
});

afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});

describe("the invite code on the sign-up form", () => {
  it("is asked for and sent while sign-up is invite-only", async () => {
    api.authApi.signupOptions.mockResolvedValue({ data: { invite_required: true } });
    const user = userEvent.setup();
    await renderForm(user);
    await fill(user);
    await user.type(await screen.findByLabelText("Invite code"), "good-code");
    await submit(user);
    await waitFor(() =>
      expect(api.authApi.register).toHaveBeenCalledWith(
        expect.objectContaining({ invite_code: "good-code" }),
      ),
    );
  });

  it("isn't asked for when sign-up is open", async () => {
    api.authApi.signupOptions.mockResolvedValue({ data: { invite_required: false } });
    const user = userEvent.setup();
    await renderForm(user);
    expect(screen.queryByLabelText("Invite code")).toBeNull();
    await fill(user);
    await submit(user);
    await waitFor(() => expect(api.authApi.register).toHaveBeenCalled());
    expect(api.authApi.register.mock.calls[0][0]).not.toHaveProperty("invite_code");
  });

  it("appears when the server says a code is needed, even if the options call failed", async () => {
    api.authApi.signupOptions.mockRejectedValue(new Error("offline"));
    api.authApi.register.mockRejectedValue({ response: { data: { detail: "INVITE_REQUIRED" } } });
    const user = userEvent.setup();
    await renderForm(user);
    await fill(user);
    await submit(user);
    expect(await screen.findByLabelText("Invite code")).toBeTruthy();
    expect(screen.getByRole("alert").textContent).toContain("isn't valid");
  });
});
