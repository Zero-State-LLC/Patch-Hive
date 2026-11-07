/**
 * Rigs, their runs and their patches belong to an account. Signing out stays on this page, so none
 * of it may stay on screen. Each mock answers for whoever holds the token at the time of the call,
 * as the API would.
 */
import { act, cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useAuthStore } from "@/lib/store";
import type { User } from "@/types/api";

const api = vi.hoisted(() => ({
  canonApi: { listRigs: vi.fn(), getRig: vi.fn(), listRuns: vi.fn() },
  rackApi: { compatibility: vi.fn() },
  patchApi: { generate: vi.fn() },
  runApi: { patches: vi.fn() },
  exportApi: { downloadRackPdf: vi.fn() },
}));

const download = vi.hoisted(() => ({
  saveBlob: vi.fn(),
  filenameFromDisposition: (_header: unknown, fallback: string) => fallback,
}));

vi.mock("@/lib/api", () => api);
vi.mock("@/lib/download", () => download);

import RacksPage from "./Racks";

const STAMP = "2026-01-01T00:00:00Z";

const summary = (id: number, name: string, user_id: number) => ({
  rig_id: id,
  rack_id: id,
  user_id,
  case_id: 2,
  name,
  name_suggested: null,
  description: null,
  tags: [],
  is_public: id === PUBLIC_RIG,
  module_count: 1,
  created_at: STAMP,
  updated_at: STAMP,
});
const detail = (id: number, name: string, user_id: number) => ({
  ...summary(id, name, user_id),
  generation_seed: 1,
  vote_count: 0,
  case: null,
  modules: [
    {
      id: 101,
      module_id: 11,
      row_index: 0,
      start_hp: 0,
      module: { id: 11, brand: "Sim Co", name: "Oscillator", hp: 12, module_type: "VCO" },
    },
  ],
});

const PRIVATE_RIG = 7;
const PUBLIC_RIG = 9;
const RUN = {
  id: 11,
  rack_id: PRIVATE_RIG,
  status: "succeeded",
  created_at: STAMP,
  rig_revision_id: "rig-rev-a",
  source_run_id: "gen-run-11",
  artifact_manifest_hash: "a".repeat(64),
  export_bridge_ready: true,
};
const PATCH = {
  id: 501,
  rack_id: PRIVATE_RIG,
  run_id: 11,
  name: "Private patch",
  category: "Voice",
  connections: [],
  generation_seed: 42,
  generation_version: "v1",
  is_public: false,
  vote_count: 0,
  created_at: STAMP,
  updated_at: STAMP,
};

const notFound = () => Object.assign(new Error("not found"), { response: { status: 404 } });
const reader = () => useAuthStore.getState().user?.id ?? null;
const signIn = (token = "token", id = 1) =>
  useAuthStore.getState().setAuth({ id, username: `reader-${id}` } as unknown as User, token);
const rigList = (rows: unknown[]) => ({ data: { total: rows.length, rigs: rows } });

function serveByReader({ anonymousRigs = [summary(PUBLIC_RIG, "Public rig", 2)] } = {}) {
  api.canonApi.listRigs.mockImplementation(async () => {
    if (reader() === 1) return rigList([summary(PRIVATE_RIG, "Private rig", 1)]);
    if (reader() === 2) return rigList([summary(8, "Second account's rig", 2)]);
    return rigList(anonymousRigs);
  });
  api.canonApi.getRig.mockImplementation(async (id: number) => {
    if (id === PRIVATE_RIG && reader() === 1) {
      return { data: detail(PRIVATE_RIG, "Private rig", 1) };
    }
    if (id === PUBLIC_RIG) return { data: detail(PUBLIC_RIG, "Public rig", 2) };
    throw notFound();
  });
  api.canonApi.listRuns.mockImplementation(async (id: number) => {
    if (id === PRIVATE_RIG && reader() === 1) return { data: { runs: [RUN] } };
    if (id === PUBLIC_RIG) return { data: { runs: [] } };
    throw notFound();
  });
  api.runApi.patches.mockImplementation(async () => {
    if (reader() === 1) return { data: { patches: [PATCH] } };
    throw notFound();
  });
  api.rackApi.compatibility.mockRejectedValue(new Error("not needed"));
}

function Where() {
  const { pathname, search } = useLocation();
  return <output data-testid="where">{`${pathname}${search}`}</output>;
}

const renderAt = (url: string) =>
  render(
    <MemoryRouter initialEntries={[url]}>
      <Where />
      <Routes>
        <Route path="/racks" element={<RacksPage />} />
        <Route path="/racks/:rigId" element={<RacksPage />} />
      </Routes>
    </MemoryRouter>,
  );

const where = () => screen.getByTestId("where").textContent;
const signOut = () => act(() => useAuthStore.getState().clear());
const rigHeading = (name: string) => screen.findByRole("heading", { level: 2, name });
const expectGone = (text: RegExp) => expect(screen.queryAllByText(text)).toHaveLength(0);

beforeEach(() => {
  serveByReader();
});

afterEach(() => {
  cleanup();
  vi.resetAllMocks();
  useAuthStore.getState().clear();
});

describe("a change of reader on the rigs page", () => {
  it("drops the reader's rig, runs and patches on sign-out, and asks again", async () => {
    signIn();
    renderAt(`/racks/${PRIVATE_RIG}?tab=patches`);
    await rigHeading("Private rig");
    await screen.findAllByText(/Private patch/);

    signOut();

    await waitFor(() => expect(api.canonApi.listRigs).toHaveBeenCalledTimes(2));
    await screen.findByText("Public rig");
    await screen.findByText("Unable to load rig details. Please try again.");
    expectGone(/Private rig/);
    expectGone(/Private patch/);
  });

  it("shows nothing from the last reader while the new answers are on their way", async () => {
    signIn();
    renderAt(`/racks/${PRIVATE_RIG}`);
    await rigHeading("Private rig");

    api.canonApi.listRigs.mockImplementation(() => new Promise(() => {}));
    api.canonApi.getRig.mockImplementation(() => new Promise(() => {}));
    signOut();

    expectGone(/Private rig/);
  });

  it("doesn't move to the reader's first rig when its list arrives after sign-out", async () => {
    serveByReader({ anonymousRigs: [] });
    let answer: (value: unknown) => void = () => {};
    api.canonApi.listRigs.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          answer = resolve;
        }),
    );
    signIn();
    renderAt("/racks");
    await waitFor(() => expect(api.canonApi.listRigs).toHaveBeenCalledTimes(1));

    signOut();
    await waitFor(() => expect(api.canonApi.listRigs).toHaveBeenCalledTimes(2));
    await screen.findByText("Select a rig to begin");

    await act(async () => answer(rigList([summary(PRIVATE_RIG, "Private rig", 1)])));

    expect(where()).toBe("/racks");
    expectGone(/Private rig/);
    expect(api.canonApi.getRig).not.toHaveBeenCalled();
  });

  it("ignores a signed-in answer for the rig's details that arrives after sign-out", async () => {
    let answer: (value: unknown) => void = () => {};
    api.canonApi.getRig.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          answer = resolve;
        }),
    );
    signIn();
    renderAt(`/racks/${PRIVATE_RIG}`);
    await screen.findAllByText("Private rig");

    signOut();
    await screen.findByText("Unable to load rig details. Please try again.");

    await act(async () => answer({ data: detail(PRIVATE_RIG, "Private rig", 1) }));

    expectGone(/Private rig/);
  });

  it("stays put when a generation started before sign-out finishes after it", async () => {
    let answer: (value: unknown) => void = () => {};
    api.patchApi.generate.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          answer = resolve;
        }),
    );
    const user = userEvent.setup();
    signIn();
    renderAt(`/racks/${PRIVATE_RIG}`);
    await user.click(await screen.findByRole("button", { name: "Generate patch library" }));

    signOut();
    await screen.findByText("Unable to load rig details. Please try again.");
    const before = where();

    await act(async () => answer({ data: { run_id: 11, generated_count: 1, patches: [PATCH] } }));

    expect(where()).toBe(before);
  });

  it("doesn't save the reader's PDF when it arrives after sign-out", async () => {
    let answer: (value: unknown) => void = () => {};
    api.exportApi.downloadRackPdf.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          answer = resolve;
        }),
    );
    const user = userEvent.setup();
    signIn();
    renderAt(`/racks/${PRIVATE_RIG}?tab=exports`);
    await user.click(await screen.findByRole("button", { name: "Export Patch Book PDF" }));
    await waitFor(() => expect(api.exportApi.downloadRackPdf).toHaveBeenCalledTimes(1));

    signOut();
    await screen.findByText("Unable to load rig details. Please try again.");

    await act(async () => answer({ data: new Blob(["%PDF"]), headers: {} }));

    expect(download.saveBlob).not.toHaveBeenCalled();
  });

  it("does nothing on a token renewal, which isn't a change of reader", async () => {
    signIn();
    renderAt(`/racks/${PRIVATE_RIG}`);
    const heading = await rigHeading("Private rig");
    const lists = api.canonApi.listRigs.mock.calls.length;
    const details = api.canonApi.getRig.mock.calls.length;

    act(() => signIn("renewed-token"));

    expect(api.canonApi.listRigs).toHaveBeenCalledTimes(lists);
    expect(api.canonApi.getRig).toHaveBeenCalledTimes(details);
    expect(screen.getByRole("heading", { level: 2, name: "Private rig" })).toBe(heading);
  });

  it("starts over when a renewal brings back a different account", async () => {
    signIn();
    renderAt(`/racks/${PRIVATE_RIG}`);
    await rigHeading("Private rig");

    act(() => signIn("other-token", 2));

    await screen.findByText("Second account's rig");
    expectGone(/Private rig/);
  });
});
