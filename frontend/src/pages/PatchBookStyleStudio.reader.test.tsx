/**
 * Style recipes belong to an account, and the studio holds the one being worked on. Signing out
 * stays on this page, so none of it may stay on screen. Each mock answers for whoever holds the
 * token at the time of the call, as the API would.
 */
import { act, cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useAuthStore } from "@/lib/store";
import type { User } from "@/types/api";

const api = vi.hoisted(() => ({
  canonApi: { listStyleRecipes: vi.fn() },
}));

vi.mock("@/lib/api", () => api);

import PatchBookStyleStudioPage from "./PatchBookStyleStudio";

const RECIPE = {
  id: 3,
  name: "My private recipe",
  recipe_hash: "a".repeat(64),
  style_recipe: { mode: "technical", template_family: "ledger" },
};

const hasToken = () => Boolean(useAuthStore.getState().token);
const signIn = (token = "token") =>
  useAuthStore.getState().setAuth({ id: 1, username: "reader" } as unknown as User, token);
const refused = () => Object.assign(new Error("HTTP 401"), { response: { status: 401 } });

const renderPage = () =>
  render(
    <MemoryRouter initialEntries={["/rigs/7/patchbook-studio"]}>
      <Routes>
        <Route path="/rigs/:rigId/patchbook-studio" element={<PatchBookStyleStudioPage />} />
      </Routes>
    </MemoryRouter>,
  );

beforeEach(() => {
  api.canonApi.listStyleRecipes.mockImplementation(async () => {
    if (hasToken()) return { data: [RECIPE] };
    throw refused();
  });
});

afterEach(() => {
  cleanup();
  vi.resetAllMocks();
  useAuthStore.getState().clear();
});

describe("a change of reader in the style studio", () => {
  it("drops the reader's recipes on sign-out and asks again", async () => {
    signIn();
    renderPage();
    await screen.findByText("My private recipe");

    act(() => useAuthStore.getState().clear());

    expect(screen.queryByText("My private recipe")).toBeNull();
    await waitFor(() => expect(api.canonApi.listStyleRecipes).toHaveBeenCalledTimes(2));
    expect(screen.queryByText("My private recipe")).toBeNull();
  });

  it("clears what the reader was working on", async () => {
    const user = userEvent.setup();
    signIn();
    renderPage();
    await screen.findByText("My private recipe");
    await user.type(screen.getByPlaceholderText("Recipe name"), "Secret draft");

    act(() => useAuthStore.getState().clear());

    await waitFor(() => expect(api.canonApi.listStyleRecipes).toHaveBeenCalledTimes(2));
    expect(screen.queryByDisplayValue("Secret draft")).toBeNull();
  });

  it("ignores a signed-in answer that arrives after sign-out", async () => {
    let answer: (value: unknown) => void = () => {};
    api.canonApi.listStyleRecipes.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          answer = resolve;
        }),
    );
    signIn();
    renderPage();
    await waitFor(() => expect(api.canonApi.listStyleRecipes).toHaveBeenCalledTimes(1));

    act(() => useAuthStore.getState().clear());
    await waitFor(() => expect(api.canonApi.listStyleRecipes).toHaveBeenCalledTimes(2));

    await act(async () => answer({ data: [RECIPE] }));

    expect(screen.queryByText("My private recipe")).toBeNull();
  });

  it("does nothing on a token renewal, which isn't a change of reader", async () => {
    const user = userEvent.setup();
    signIn();
    renderPage();
    await screen.findByText("My private recipe");
    await user.type(screen.getByPlaceholderText("Recipe name"), "Keep this");
    const reads = api.canonApi.listStyleRecipes.mock.calls.length;

    act(() => signIn("renewed-token"));

    expect(api.canonApi.listStyleRecipes).toHaveBeenCalledTimes(reads);
    expect((screen.getByPlaceholderText("Recipe name") as HTMLInputElement).value).toBe(
      "Keep this",
    );
  });
});
