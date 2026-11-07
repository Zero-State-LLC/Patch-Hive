/**
 * A patch page holds the patch, its rig and the reader's own notes. Signing out stays on this page,
 * so none of what was theirs may stay on screen. Each mock answers for whoever holds the token at
 * the time of the call, as the API would.
 */
import { act, cleanup, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useAuthStore } from "@/lib/store";
import type { User } from "@/types/api";

const api = vi.hoisted(() => ({
  patchApi: { get: vi.fn() },
  canonApi: { getRig: vi.fn(), getOverlay: vi.fn(), upsertOverlay: vi.fn() },
  legacyPatchRef: (id: number) => `legacy-patch-${id}`,
}));

vi.mock("@/lib/api", () => api);

import PatchDetailPage from "./PatchDetail";

const STAMP = "2026-01-01T00:00:00Z";
const PATCH = {
  id: 501,
  rack_id: 8,
  run_id: 11,
  name: "Private patch",
  category: "Voice",
  description: null,
  connections: [],
  generation_seed: 42,
  generation_version: "v1",
  is_public: false,
  vote_count: 0,
  created_at: STAMP,
  updated_at: STAMP,
};
const RIG = {
  rig_id: 8,
  rack_id: 8,
  user_id: 1,
  case_id: 2,
  name: "Private rig",
  name_suggested: null,
  description: null,
  tags: [],
  is_public: false,
  module_count: 0,
  created_at: STAMP,
  updated_at: STAMP,
  generation_seed: 1,
  vote_count: 0,
  modules: [],
  case: null,
};
const NOTES = { notes: "My private note", favorite: false, tried: false };

const refused = (status: number) =>
  Object.assign(new Error(`HTTP ${status}`), { response: { status } });
const hasToken = () => Boolean(useAuthStore.getState().token);
const signIn = (token = "token") =>
  useAuthStore.getState().setAuth({ id: 1, username: "reader" } as unknown as User, token);

function serveByReader({ publicPatch = false } = {}) {
  api.patchApi.get.mockImplementation(async () => {
    if (hasToken() || publicPatch) return { data: PATCH };
    throw refused(404);
  });
  api.canonApi.getRig.mockImplementation(async () => {
    if (hasToken() || publicPatch) return { data: RIG };
    throw refused(404);
  });
  api.canonApi.getOverlay.mockImplementation(async () => {
    if (hasToken()) return { data: NOTES };
    throw refused(401);
  });
}

const renderPage = () =>
  render(
    <MemoryRouter initialEntries={["/rigs/8/patches/501"]}>
      <Routes>
        <Route path="/rigs/:rigId/patches/:patchId" element={<PatchDetailPage />} />
      </Routes>
    </MemoryRouter>,
  );

const signOut = () => act(() => useAuthStore.getState().clear());

beforeEach(() => {
  serveByReader();
});

afterEach(() => {
  cleanup();
  vi.resetAllMocks();
  useAuthStore.getState().clear();
});

describe("a change of reader on a patch page", () => {
  it("drops a private patch and the reader's notes on sign-out", async () => {
    signIn();
    renderPage();
    await screen.findByRole("heading", { level: 1, name: "Private patch" });
    await screen.findByDisplayValue("My private note");

    signOut();

    await screen.findByRole("heading", { level: 1, name: "No patch here." });
    expect(screen.queryByText(/Private patch/)).toBeNull();
    expect(screen.queryByText(/Private rig/)).toBeNull();
    expect(screen.queryByDisplayValue("My private note")).toBeNull();
  });

  it("keeps a public patch on sign-out, but not the reader's notes", async () => {
    serveByReader({ publicPatch: true });
    signIn();
    renderPage();
    await screen.findByDisplayValue("My private note");

    signOut();

    await waitFor(() => expect(api.canonApi.getOverlay).toHaveBeenCalledTimes(2));
    await screen.findByRole("heading", { level: 1, name: "Private patch" });
    await waitFor(() => expect(screen.queryByDisplayValue("My private note")).toBeNull());
  });

  it("shows nothing from the last reader while the new answers are on their way", async () => {
    signIn();
    renderPage();
    await screen.findByRole("heading", { level: 1, name: "Private patch" });

    api.patchApi.get.mockImplementation(() => new Promise(() => {}));
    api.canonApi.getRig.mockImplementation(() => new Promise(() => {}));
    signOut();

    expect(screen.queryByText(/Private patch/)).toBeNull();
  });

  it("ignores a signed-in answer that arrives after sign-out", async () => {
    let answer: (value: unknown) => void = () => {};
    api.patchApi.get.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          answer = resolve;
        }),
    );
    signIn();
    renderPage();
    await waitFor(() => expect(api.patchApi.get).toHaveBeenCalledTimes(1));

    signOut();
    await screen.findByRole("heading", { level: 1, name: "No patch here." });

    await act(async () => answer({ data: PATCH }));

    expect(screen.queryByText(/Private patch/)).toBeNull();
  });

  it("does nothing on a token renewal, which isn't a change of reader", async () => {
    signIn();
    renderPage();
    const heading = await screen.findByRole("heading", { level: 1, name: "Private patch" });
    await screen.findByDisplayValue("My private note");
    const reads = api.patchApi.get.mock.calls.length;

    act(() => signIn("renewed-token"));

    expect(api.patchApi.get).toHaveBeenCalledTimes(reads);
    expect(screen.getByRole("heading", { level: 1, name: "Private patch" })).toBe(heading);
    expect(screen.getByDisplayValue("My private note")).toBeInTheDocument();
  });
});
