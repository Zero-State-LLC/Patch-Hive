/**
 * The selected rig, tab and patch live in the URL: a link or reload restores the same view,
 * and choosing in the page updates the URL.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";

const api = vi.hoisted(() => ({
  listRigs: vi.fn(),
  getRig: vi.fn(),
  listRuns: vi.fn(),
  patches: vi.fn(),
}));

vi.mock("@/lib/api", () => ({
  canonApi: { listRigs: api.listRigs, getRig: api.getRig, listRuns: api.listRuns },
  rackApi: { compatibility: vi.fn().mockRejectedValue(new Error("not needed")) },
  patchApi: { generate: vi.fn() },
  runApi: { patches: api.patches },
  exportApi: { rackPdf: () => "#" },
}));

import RacksPage from "./Racks";

const STAMP = "2026-01-01T00:00:00Z";

const summary = (id: number, name: string) => ({
  rig_id: id,
  rack_id: id,
  user_id: 1,
  case_id: 2,
  name,
  name_suggested: null,
  description: null,
  tags: [],
  is_public: false,
  module_count: 1,
  created_at: STAMP,
  updated_at: STAMP,
});

const detail = (id: number, name: string) => ({
  ...summary(id, name),
  generation_seed: 1,
  vote_count: 0,
  modules: [
    {
      id: 100 + id,
      module_id: 11,
      row_index: 0,
      start_hp: 0,
      module: { id: 11, brand: "Sim Co", name: "Oscillator", hp: 12, module_type: "VCO" },
    },
  ],
  case: { id: 2, brand: "Sim Co", name: "Sim 84", total_hp: 84, rows: 1, hp_per_row: [84] },
});

const patch = (id: number, name: string) => ({
  id,
  rack_id: 8,
  run_id: 11,
  name,
  category: "Voice",
  connections: [],
  generation_seed: 1,
  generation_version: "test",
  is_public: false,
  vote_count: 0,
  created_at: STAMP,
  updated_at: STAMP,
});

function Where() {
  const location = useLocation();
  return <output data-testid="where">{`${location.pathname}${location.search}`}</output>;
}

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/racks" element={<RacksPage />} />
        <Route path="/racks/:rigId" element={<RacksPage />} />
      </Routes>
      <Where />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  api.listRigs.mockResolvedValue({
    data: { total: 2, rigs: [summary(7, "Bench rig"), summary(8, "Travel rig")] },
  });
  api.getRig.mockImplementation(async (id: number) => ({
    data: detail(id, id === 7 ? "Bench rig" : "Travel rig"),
  }));
  api.listRuns.mockResolvedValue({
    data: {
      total: 1,
      runs: [{ id: 11, rack_id: 8, status: "succeeded", created_at: STAMP }],
    },
  });
  api.patches.mockResolvedValue({
    data: { total: 2, patches: [patch(501, "Slow drift"), patch(502, "Clock lattice")] },
  });
});

describe("Racks deep links", () => {
  it("restores the rig, tab and patch from the URL", async () => {
    renderAt("/racks/8?tab=patches&patch=502");

    expect(
      await screen.findByRole("heading", { level: 1, name: "Travel rig" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Travel rig/ })).toHaveAttribute(
      "aria-current",
      "true",
    );
    expect(await screen.findByRole("tab", { name: "Patches" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    const list = await screen.findByRole("list", { name: "Patches in this run" });
    expect(within(list).getByRole("button", { name: /Clock lattice/ })).toHaveAttribute(
      "aria-current",
      "true",
    );
    expect(screen.getByRole("link", { name: "Revisions and runs" })).toHaveAttribute(
      "href",
      "/rigs/8",
    );
  });

  it("moves a bare /racks to the first rig without adding a history entry", async () => {
    renderAt("/racks");
    expect(await screen.findByRole("heading", { level: 1, name: "Bench rig" })).toBeInTheDocument();
    expect(screen.getByTestId("where")).toHaveTextContent("/racks/7");
  });

  it("writes choices back to the URL", async () => {
    const user = userEvent.setup();
    renderAt("/racks/8?tab=patches&patch=502");
    const list = await screen.findByRole("list", { name: "Patches in this run" });

    await user.click(within(list).getByRole("button", { name: /Slow drift/ }));
    expect(screen.getByTestId("where")).toHaveTextContent("/racks/8?tab=patches&patch=501");

    await user.click(screen.getByRole("tab", { name: "Overview" }));
    expect(screen.getByTestId("where")).toHaveTextContent(/^\/racks\/8$/);

    await user.click(screen.getByRole("button", { name: /Bench rig/ }));
    expect(screen.getByTestId("where")).toHaveTextContent(/^\/racks\/7$/);
    expect(await screen.findByRole("heading", { level: 1, name: "Bench rig" })).toBeInTheDocument();
  });
});
