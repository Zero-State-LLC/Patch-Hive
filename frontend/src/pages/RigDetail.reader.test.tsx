/**
 * A rig's workspace holds what belongs to its owner: the rig, its runs, its revisions, its inventory
 * receipt, and the reader's own credits. Signing out stays on this page, so none of it may stay on
 * screen. Each mock answers for whoever holds the token at the time of the call, as the API would.
 */
import { act, cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useAuthStore } from "@/lib/store";
import type { User } from "@/types/api";

const api = vi.hoisted(() => ({
  canonApi: {
    getRig: vi.fn(),
    listRuns: vi.fn(),
    listRevisions: vi.fn(),
    getBalance: vi.fn(),
    getCommerce: vi.fn(),
    getOverlay: vi.fn(),
    createExport: vi.fn(),
  },
  evidenceApi: { listInventory: vi.fn() },
  patchApi: { generate: vi.fn() },
  runApi: { patches: vi.fn() },
  legacyPatchRef: (id: number) => `legacy-patch-${id}`,
}));

vi.mock("@/lib/api", () => api);

import RigDetailPage from "./RigDetail";

const STAMP = "2026-01-01T00:00:00Z";
const RIG_ID = 7;
const RIG = {
  rig_id: RIG_ID,
  rack_id: RIG_ID,
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
const REVISION = "rig-rev-" + "a".repeat(32);
const RUN = {
  id: 11,
  rack_id: RIG_ID,
  status: "succeeded",
  created_at: STAMP,
  rig_revision_id: REVISION,
  source_run_id: "gen-run-11",
  artifact_manifest_hash: "a".repeat(64),
  export_bridge_ready: true,
};

const notFound = () => Object.assign(new Error("not found"), { response: { status: 404 } });
const reader = () => useAuthStore.getState().user?.id ?? null;
const signIn = (token = "token", id = 1) =>
  useAuthStore.getState().setAuth({ id, username: `reader-${id}` } as unknown as User, token);

function ownerOnly<T>(answer: T) {
  return async () => {
    if (reader() === 1) return { data: answer };
    throw notFound();
  };
}

function serveByReader() {
  api.canonApi.getRig.mockImplementation(ownerOnly(RIG));
  api.canonApi.listRuns.mockImplementation(ownerOnly({ runs: [RUN] }));
  api.canonApi.listRevisions.mockImplementation(
    ownerOnly({
      revisions: [
        {
          rig_revision_id: REVISION,
          run_count: 1,
          latest_run_id: 11,
          latest_run_at: STAMP,
          export_bridge_ready: true,
        },
      ],
    }),
  );
  api.evidenceApi.listInventory.mockImplementation(
    ownerOnly({ latest: null, modules_to_place: [] }),
  );
  api.runApi.patches.mockImplementation(ownerOnly({ patches: [] }));
  api.canonApi.getBalance.mockImplementation(async () => ({ data: { balance: 41 } }));
  api.canonApi.getCommerce.mockImplementation(async () => ({ data: { allowance: null } }));
}

function Where() {
  const { pathname, search } = useLocation();
  return <output data-testid="where">{`${pathname}${search}`}</output>;
}

const renderPage = () =>
  render(
    <MemoryRouter initialEntries={[`/rigs/${RIG_ID}`]}>
      <Where />
      <Routes>
        <Route path="/rigs/:rigId" element={<RigDetailPage />} />
      </Routes>
    </MemoryRouter>,
  );

const where = () => screen.getByTestId("where").textContent;
const signOut = () => act(() => useAuthStore.getState().clear());

beforeEach(() => {
  serveByReader();
});

afterEach(() => {
  cleanup();
  vi.resetAllMocks();
  useAuthStore.getState().clear();
});

describe("a change of reader on a rig's workspace", () => {
  it("drops the rig, its runs and the reader's credits on sign-out, and asks again", async () => {
    signIn();
    renderPage();
    await screen.findByRole("heading", { level: 1, name: "Private rig" });
    await screen.findByLabelText("Rig revision");
    await screen.findByText(/41 credits available/);

    signOut();

    await waitFor(() => expect(api.canonApi.getRig).toHaveBeenCalledTimes(2));
    await screen.findByRole("heading", { level: 1, name: "Rig workspace" });
    await screen.findByText(/Couldn't load this rig's details/);
    expect(screen.queryByText(/Private rig/)).toBeNull();
    expect(screen.queryByLabelText("Rig revision")).toBeNull();
    expect(screen.queryByText(/41 credit/)).toBeNull();
  });

  it("shows nothing from the last reader while the new answers are on their way", async () => {
    signIn();
    renderPage();
    await screen.findByRole("heading", { level: 1, name: "Private rig" });

    api.canonApi.getRig.mockImplementation(() => new Promise(() => {}));
    api.canonApi.listRuns.mockImplementation(() => new Promise(() => {}));
    signOut();

    expect(screen.queryByText(/Private rig/)).toBeNull();
    expect(screen.queryByLabelText("Rig revision")).toBeNull();
  });

  it("ignores a signed-in answer that arrives after sign-out", async () => {
    let answer: (value: unknown) => void = () => {};
    api.canonApi.getRig.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          answer = resolve;
        }),
    );
    signIn();
    renderPage();
    await waitFor(() => expect(api.canonApi.getRig).toHaveBeenCalledTimes(1));

    signOut();
    await screen.findByText(/Couldn't load this rig's details/);

    await act(async () => answer({ data: RIG }));

    expect(screen.queryByText(/Private rig/)).toBeNull();
  });

  it("stays put, and says nothing, when a generation finishes after sign-out", async () => {
    let answer: (value: unknown) => void = () => {};
    api.patchApi.generate.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          answer = resolve;
        }),
    );
    const user = userEvent.setup();
    signIn();
    renderPage();
    await user.click(await screen.findByRole("button", { name: /^Generate patches/ }));

    signOut();
    await screen.findByText(/Couldn't load this rig's details/);

    await act(async () =>
      answer({ data: { run_id: 11, generated_count: 3, patches: [], status: "ok" } }),
    );

    expect(where()).toBe(`/rigs/${RIG_ID}`);
    expect(screen.queryByText(/Generated 3 patches/)).toBeNull();
  });

  it("does nothing on a token renewal, which isn't a change of reader", async () => {
    signIn();
    renderPage();
    const heading = await screen.findByRole("heading", { level: 1, name: "Private rig" });
    await screen.findByText(/41 credits available/);
    const reads = api.canonApi.getRig.mock.calls.length;
    const balances = api.canonApi.getBalance.mock.calls.length;

    act(() => signIn("renewed-token"));

    expect(api.canonApi.getRig).toHaveBeenCalledTimes(reads);
    expect(api.canonApi.getBalance).toHaveBeenCalledTimes(balances);
    expect(screen.getByRole("heading", { level: 1, name: "Private rig" })).toBe(heading);
  });
});
