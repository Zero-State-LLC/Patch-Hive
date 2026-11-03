import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";

const api = vi.hoisted(() => ({
  getPatch: vi.fn(),
  getRig: vi.fn(),
  getOverlay: vi.fn(),
  upsertOverlay: vi.fn(),
}));

vi.mock("@/lib/api", () => ({
  patchApi: { get: api.getPatch },
  canonApi: { getRig: api.getRig, getOverlay: api.getOverlay, upsertOverlay: api.upsertOverlay },
  legacyPatchRef: (id: number) => `legacy-patch-${id}`,
}));

import PatchDetailPage from "./PatchDetail";

const STAMP = "2026-01-01T00:00:00Z";

const PATCH = {
  id: 501,
  rack_id: 8,
  run_id: 11,
  name: "Generated name",
  suggested_name: "Slow drift",
  category: "Voice",
  description: "A filtered voice with a slow envelope",
  connections: [
    { from_module_id: 11, from_port: "Out", to_module_id: 12, to_port: "In", cable_type: "audio" },
  ],
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
  name: "Travel rig",
  name_suggested: null,
  description: null,
  tags: [],
  is_public: false,
  module_count: 2,
  created_at: STAMP,
  updated_at: STAMP,
  generation_seed: 1,
  vote_count: 0,
  modules: [
    {
      id: 101,
      module_id: 11,
      row_index: 0,
      start_hp: 0,
      module: { id: 11, brand: "Sim Co", name: "Oscillator", hp: 12, module_type: "VCO" },
    },
    {
      id: 102,
      module_id: 12,
      row_index: 0,
      start_hp: 14,
      module: { id: 12, brand: "Sim Co", name: "Filter", hp: 10, module_type: "VCF" },
    },
  ],
  case: { id: 2, brand: "Sim Co", name: "Sim 84", total_hp: 84, rows: 1, hp_per_row: [84] },
};

function Where() {
  const location = useLocation();
  return <p data-testid="where">{location.pathname}</p>;
}

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/rigs/:rigId/patches/:patchId" element={<PatchDetailPage />} />
      </Routes>
      <Where />
    </MemoryRouter>,
  );
}

const httpError = (status: number) =>
  Object.assign(new Error(`HTTP ${status}`), { response: { status } });

beforeEach(() => {
  vi.clearAllMocks();
  api.getPatch.mockResolvedValue({ data: PATCH });
  api.getRig.mockResolvedValue({ data: RIG });
  api.getOverlay.mockRejectedValue(httpError(404));
  api.upsertOverlay.mockResolvedValue({ data: {} });
});

describe("Patch detail", () => {
  it("shows the patch on its rig's rail with the user's notes", async () => {
    const { container } = renderAt("/rigs/8/patches/501");

    expect(
      await screen.findByRole("heading", { level: 1, name: "Slow drift" }),
    ).toBeInTheDocument();
    expect(screen.getByText("A filtered voice with a slow envelope")).toBeInTheDocument();
    expect(screen.getByText(/Voice, .*1 cable\. Seed 42, generator v1\./)).toBeInTheDocument();
    expect(container.querySelectorAll(".patch-cable")).toHaveLength(1);
    expect(screen.getByRole("link", { name: "Travel rig" })).toHaveAttribute(
      "href",
      "/rigs/8?tab=patches&patch=501",
    );
    expect(screen.getByRole("heading", { name: "Your notes" })).toBeInTheDocument();
  });

  it("saves the user's notes against this patch", async () => {
    const user = userEvent.setup();
    renderAt("/rigs/8/patches/501");
    await screen.findByRole("heading", { level: 1, name: "Slow drift" });
    // The fields open once the saved notes (none yet) have loaded.
    await waitFor(() => expect(screen.getByLabelText("Notes")).toBeEnabled());

    await user.type(screen.getByLabelText("Notes"), "Try a slower envelope");
    await user.click(screen.getByLabelText("Favorite"));
    await user.click(screen.getByRole("button", { name: "Save notes" }));

    expect(api.upsertOverlay).toHaveBeenCalledWith("legacy-patch-501", {
      notes: "Try a slower envelope",
      favorite: true,
      tried: false,
    });
    expect(await screen.findByRole("status")).toHaveTextContent("Saved.");
  });

  it("says so when the patch does not exist", async () => {
    api.getPatch.mockRejectedValue(httpError(404));
    renderAt("/rigs/8/patches/999");

    expect(await screen.findByText("No patch here.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Back to the rig/ })).toHaveAttribute(
      "href",
      "/racks/8?tab=patches",
    );
  });

  it("offers a retry when the patch fails to load", async () => {
    const user = userEvent.setup();
    api.getPatch.mockRejectedValueOnce(httpError(500));
    renderAt("/rigs/8/patches/501");

    await user.click(await screen.findByRole("button", { name: "Retry" }));

    expect(
      await screen.findByRole("heading", { level: 1, name: "Slow drift" }),
    ).toBeInTheDocument();
  });

  it("moves a link with the wrong rig to the patch's own rig", async () => {
    renderAt("/rigs/7/patches/501");
    // The redirect is a navigation, which settles after render.
    await waitFor(() =>
      expect(screen.getByTestId("where")).toHaveTextContent("/rigs/8/patches/501"),
    );
  });

  it("keeps the notes when the rig fails to load", async () => {
    api.getRig.mockRejectedValue(httpError(500));
    renderAt("/rigs/8/patches/501");

    expect(
      await screen.findByRole("heading", { level: 1, name: "Slow drift" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("can't be drawn on the rail");
    expect(screen.getByRole("heading", { name: "Your notes" })).toBeInTheDocument();
  });

  it("keeps the notes closed when they fail to load, so they can't be saved over", async () => {
    const user = userEvent.setup();
    api.getOverlay.mockRejectedValueOnce(httpError(500));
    renderAt("/rigs/8/patches/501");

    expect(await screen.findByText("Couldn't load your notes.")).toBeInTheDocument();
    expect(screen.queryByLabelText("Notes")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Save notes" })).not.toBeInTheDocument();

    api.getOverlay.mockResolvedValueOnce({
      data: { notes: "Saved earlier", favorite: true, tried: false },
    });
    await user.click(screen.getByRole("button", { name: "Retry" }));

    expect(await screen.findByDisplayValue("Saved earlier")).toBeInTheDocument();
  });

  it("asks a signed-out visitor to sign in to keep notes", async () => {
    api.getOverlay.mockRejectedValueOnce(httpError(401));
    renderAt("/rigs/8/patches/501");

    expect(await screen.findByText(/Sign in to keep your own notes/)).toBeInTheDocument();
    expect(screen.queryByLabelText("Notes")).not.toBeInTheDocument();
  });

  it("says when a save fails for a reason other than signing in", async () => {
    const user = userEvent.setup();
    api.upsertOverlay.mockRejectedValueOnce(httpError(500));
    renderAt("/rigs/8/patches/501");
    await screen.findByRole("heading", { level: 1, name: "Slow drift" });

    const save = await screen.findByRole("button", { name: "Save notes" });
    await waitFor(() => expect(save).toBeEnabled());
    await user.click(save);

    expect(await screen.findByText("Couldn't save your notes. Try again.")).toBeInTheDocument();
  });
});
