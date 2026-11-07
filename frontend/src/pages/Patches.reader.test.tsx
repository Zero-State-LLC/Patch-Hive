/**
 * The patch list answers with what the reader may read, which includes their own private patches.
 * Signing out stays on this page, so those may not stay on screen. Each mock answers for whoever
 * holds the token at the time of the call, as the API would.
 */
import { act, cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useAuthStore } from "@/lib/store";
import type { User } from "@/types/api";

const api = vi.hoisted(() => ({ patchApi: { list: vi.fn() } }));

vi.mock("@/lib/api", () => api);

import PatchesPage from "./Patches";

const row = (id: number, name: string) => ({
  id,
  rack_id: 7,
  name,
  category: "Voice",
  connections: [],
  generation_seed: 42,
  generation_version: "v1",
  is_public: true,
  vote_count: 0,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
});
const PRIVATE = row(1, "Private patch");
const PUBLIC = row(2, "Public patch");

const hasToken = () => Boolean(useAuthStore.getState().token);
const signIn = (token = "token") =>
  useAuthStore.getState().setAuth({ id: 1, username: "reader" } as unknown as User, token);
const listOf = (patches: unknown[]) => ({ data: { total: patches.length, patches } });

const renderPage = () =>
  render(
    <MemoryRouter>
      <PatchesPage />
    </MemoryRouter>,
  );

beforeEach(() => {
  api.patchApi.list.mockImplementation(async () =>
    listOf(hasToken() ? [PRIVATE, PUBLIC] : [PUBLIC]),
  );
});

afterEach(() => {
  cleanup();
  vi.resetAllMocks();
  useAuthStore.getState().clear();
});

describe("a change of reader on the patch list", () => {
  it("asks again on sign-out and shows only what an anonymous reader may see", async () => {
    signIn();
    renderPage();
    await screen.findByText("Private patch");

    act(() => useAuthStore.getState().clear());

    await waitFor(() => expect(api.patchApi.list).toHaveBeenCalledTimes(2));
    await screen.findByText("Public patch");
    expect(screen.queryByText("Private patch")).toBeNull();
  });

  it("shows nothing from the last reader while the new answer is on its way", async () => {
    signIn();
    renderPage();
    await screen.findByText("Private patch");

    api.patchApi.list.mockImplementation(() => new Promise(() => {}));
    act(() => useAuthStore.getState().clear());

    expect(screen.queryByText("Private patch")).toBeNull();
  });

  it("ignores a signed-in answer that arrives after sign-out", async () => {
    let answer: (value: unknown) => void = () => {};
    api.patchApi.list.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          answer = resolve;
        }),
    );
    signIn();
    renderPage();
    await waitFor(() => expect(api.patchApi.list).toHaveBeenCalledTimes(1));

    act(() => useAuthStore.getState().clear());
    await screen.findByText("Public patch");

    await act(async () => answer(listOf([PRIVATE, PUBLIC])));

    expect(screen.queryByText("Private patch")).toBeNull();
  });

  it("does nothing on a token renewal, which isn't a change of reader", async () => {
    const user = userEvent.setup();
    signIn();
    renderPage();
    await screen.findByText("Private patch");
    await user.selectOptions(screen.getByLabelText("Category"), "Voice");
    await waitFor(() => expect(api.patchApi.list).toHaveBeenCalledTimes(2));
    await screen.findByText("Private patch");

    act(() => signIn("renewed-token"));

    expect(api.patchApi.list).toHaveBeenCalledTimes(2);
    expect((screen.getByLabelText("Category") as HTMLSelectElement).value).toBe("Voice");
    expect(screen.getByText("Private patch")).toBeInTheDocument();
  });
});
