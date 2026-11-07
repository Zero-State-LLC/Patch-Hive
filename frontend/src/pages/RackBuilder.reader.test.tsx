/**
 * The rack builder holds what a reader may see: the module picker has more rows for a signed-in
 * reader (owner decision 39), and rigs belong to an account. Signing out stays on this page, so
 * none of it may stay on screen. Each mock answers for whoever holds the token at the time of the
 * call, as the API would.
 */
import { act, cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useAuthStore } from "@/lib/store";
import type { User } from "@/types/api";

const api = vi.hoisted(() => ({
  canonApi: { listRigs: vi.fn(), getRig: vi.fn() },
  caseApi: { list: vi.fn() },
  caseCatalogApi: { list: vi.fn(), compatibility: vi.fn() },
  moduleApi: { list: vi.fn() },
  evidenceApi: { listInventory: vi.fn() },
  rackApi: { compatibility: vi.fn(), create: vi.fn() },
}));

vi.mock("@/lib/api", () => api);

import RackBuilderPage from "./RackBuilder";

const moduleRow = (id: number, name: string) => ({
  id,
  brand: "Maker",
  name,
  hp: 8,
  module_type: "VCO",
  power_12v_ma: 20,
});
const KNOWN = moduleRow(1, "Known Osc");
const LEAD = moduleRow(2, "Lead Osc");

const RIG = {
  id: 7,
  rig_id: 7,
  rack_id: 7,
  name: "Private rig",
  case_id: 10,
  user_id: 1,
  generation_seed: 1,
  modules: [],
  case: {
    id: 10,
    brand: "Sim Co",
    name: "Sim 84",
    total_hp: 84,
    rows: 1,
    hp_per_row: [84],
    power_12v_ma: 2000,
    power_neg12v_ma: 1200,
    power_5v_ma: 500,
  },
};

const hasToken = () => Boolean(useAuthStore.getState().token);
const signIn = (token = "token") =>
  useAuthStore.getState().setAuth({ id: 1, username: "reader" } as unknown as User, token);
const modulesFor = (rows: unknown[]) => ({ data: { total: rows.length, modules: rows } });

function serveByReader({ publicRig = true } = {}) {
  api.moduleApi.list.mockImplementation(async () =>
    modulesFor(hasToken() ? [KNOWN, LEAD] : [KNOWN]),
  );
  api.canonApi.getRig.mockImplementation(async () => {
    if (hasToken() || publicRig) return { data: RIG };
    throw Object.assign(new Error("not found"), { response: { status: 404 } });
  });
  api.canonApi.listRigs.mockImplementation(async () => ({
    data: { total: 0, rigs: hasToken() ? [RIG] : [] },
  }));
  api.rackApi.compatibility.mockResolvedValue({
    data: { bridge_status: "ok", message: "ok", compatibility: null },
  });
  api.caseApi.list.mockResolvedValue({ data: { total: 0, cases: [] } });
  api.caseCatalogApi.list.mockResolvedValue({ data: { total: 0, cases: [] } });
}

const renderEditor = () =>
  render(
    <MemoryRouter initialEntries={["/racks/7/edit"]}>
      <Routes>
        <Route path="/racks/:id/edit" element={<RackBuilderPage />} />
      </Routes>
    </MemoryRouter>,
  );

const renderCreate = () =>
  render(
    <MemoryRouter initialEntries={["/racks/new"]}>
      <Routes>
        <Route path="/racks/new" element={<RackBuilderPage />} />
      </Routes>
    </MemoryRouter>,
  );

beforeEach(() => {
  serveByReader();
});

afterEach(() => {
  cleanup();
  vi.resetAllMocks();
  useAuthStore.getState().clear();
});

describe("a change of reader on the rack builder", () => {
  it("asks again on sign-out, and the picker shows only what an anonymous reader may see", async () => {
    signIn();
    renderEditor();
    await screen.findAllByText(/Lead Osc/);

    act(() => useAuthStore.getState().clear());

    await waitFor(() => expect(api.moduleApi.list).toHaveBeenCalledTimes(2));
    await screen.findAllByText(/Known Osc/);
    expect(screen.queryByText(/Lead Osc/)).toBeNull();
  });

  it("ignores a signed-in answer that arrives after sign-out", async () => {
    let answer: (value: unknown) => void = () => {};
    api.moduleApi.list.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          answer = resolve;
        }),
    );
    signIn();
    renderEditor();
    await waitFor(() => expect(api.moduleApi.list).toHaveBeenCalledTimes(1));

    act(() => useAuthStore.getState().clear());
    await waitFor(() => expect(api.moduleApi.list).toHaveBeenCalledTimes(2));
    await screen.findAllByText(/Known Osc/);

    await act(async () => answer(modulesFor([KNOWN, LEAD])));

    expect(screen.queryByText(/Lead Osc/)).toBeNull();
  });

  it("drops a private rig on sign-out and says it can't be loaded", async () => {
    serveByReader({ publicRig: false });
    signIn();
    renderEditor();
    await screen.findAllByText(/Private rig/);

    act(() => useAuthStore.getState().clear());

    await screen.findByText(/Unable to load rig for placement/);
    expect(screen.queryByText(/Private rig/)).toBeNull();
  });

  it("drops the choice of a module the anonymous reader can't see", async () => {
    const user = userEvent.setup();
    signIn();
    renderEditor();
    const picker = await screen.findByRole("combobox", { name: /module/i });
    await screen.findAllByText(/Lead Osc/);
    await user.selectOptions(picker, "2");

    act(() => useAuthStore.getState().clear());

    await screen.findAllByText(/Known Osc/);
    const after = screen.getByRole("combobox", { name: /module/i }) as HTMLSelectElement;
    expect(after.value).not.toBe("2");
  });

  it("drops the signed-in reader's rigs from the create page on sign-out", async () => {
    signIn();
    renderCreate();
    await screen.findByRole("option", { name: /Private rig/ });

    act(() => useAuthStore.getState().clear());

    await waitFor(() => expect(api.canonApi.listRigs).toHaveBeenCalledTimes(2));
    await screen.findByText(/Create a rig first/);
    expect(screen.queryByRole("option", { name: /Private rig/ })).toBeNull();
  });

  it("clears what the signed-in reader typed on the create page", async () => {
    const user = userEvent.setup();
    signIn();
    renderCreate();
    await user.type(await screen.findByLabelText(/search cases/i), "Secret search");

    act(() => useAuthStore.getState().clear());

    await waitFor(() => expect(api.canonApi.listRigs).toHaveBeenCalledTimes(2));
    expect(screen.queryByDisplayValue("Secret search")).toBeNull();
  });

  it("stays put when a rig created before sign-out comes back after it", async () => {
    let answer: (value: unknown) => void = () => {};
    api.rackApi.create.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          answer = resolve;
        }),
    );
    function Where() {
      const { pathname, search } = useLocation();
      return <output data-testid="where">{`${pathname}${search}`}</output>;
    }
    const user = userEvent.setup();
    signIn();
    render(
      <MemoryRouter initialEntries={["/racks/new?case_id=10"]}>
        <Where />
        <Routes>
          <Route path="/racks/new" element={<RackBuilderPage />} />
          <Route path="/racks/:id/edit" element={<RackBuilderPage />} />
        </Routes>
      </MemoryRouter>,
    );
    await user.click(await screen.findByRole("button", { name: "Create empty rig" }));
    await waitFor(() => expect(api.rackApi.create).toHaveBeenCalledTimes(1));

    act(() => useAuthStore.getState().clear());
    await waitFor(() => expect(api.canonApi.listRigs).toHaveBeenCalledTimes(2));

    await act(async () => answer({ data: { id: 7 } }));

    expect(screen.getByTestId("where").textContent).toBe("/racks/new?case_id=10");
  });

  it("starts over when a renewal brings back a different account", async () => {
    signIn();
    renderCreate();
    await screen.findByRole("option", { name: /Private rig/ });

    act(() =>
      useAuthStore.getState().setAuth({ id: 2, username: "other" } as unknown as User, "other"),
    );

    await waitFor(() => expect(api.canonApi.listRigs).toHaveBeenCalledTimes(2));
  });

  it("does nothing on a token renewal, which isn't a change of reader", async () => {
    const user = userEvent.setup();
    signIn();
    renderCreate();
    const search = await screen.findByLabelText(/search cases/i);
    await user.type(search, "Keep this");
    const reads = api.canonApi.listRigs.mock.calls.length;

    act(() => signIn("renewed-token"));

    expect((screen.getByLabelText(/search cases/i) as HTMLInputElement).value).toBe("Keep this");
    expect(api.canonApi.listRigs).toHaveBeenCalledTimes(reads);
  });
});
