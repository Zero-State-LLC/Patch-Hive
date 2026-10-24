/**
 * Spec 008 review fix: a failed rig detail load (GET /api/canon/rigs/{id}) must
 * show an error in the workspace with a Retry that re-requests the detail.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

const api = vi.hoisted(() => ({
  listRigs: vi.fn(),
  getRig: vi.fn(),
  listRuns: vi.fn(),
  compatibility: vi.fn(),
}));

vi.mock("@/lib/api", () => ({
  canonApi: { listRigs: api.listRigs, getRig: api.getRig, listRuns: api.listRuns },
  rackApi: { compatibility: api.compatibility },
  patchApi: { generate: vi.fn() },
  runApi: { patches: vi.fn().mockResolvedValue({ data: { patches: [] } }) },
  exportApi: { rackPdf: () => "#" },
}));

import RacksPage from "./Racks";

const summary = {
  rig_id: 7,
  rack_id: 7,
  user_id: 1,
  case_id: 2,
  name: "Golden Rig",
  name_suggested: null,
  description: "Seeded rig",
  tags: [],
  is_public: false,
  module_count: 0,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

function renderPage() {
  return render(
    <MemoryRouter>
      <RacksPage />
    </MemoryRouter>,
  );
}

describe("Racks page rig detail load", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.listRigs.mockResolvedValue({ data: { total: 1, rigs: [summary] } });
    api.listRuns.mockResolvedValue({ data: { runs: [] } });
    api.compatibility.mockRejectedValue(new Error("not needed"));
  });

  it("shows the detail error with a retry instead of the empty workspace", async () => {
    api.getRig.mockRejectedValueOnce(new Error("boom"));
    renderPage();

    expect(await screen.findByText("Unable to load rig details. Please try again.")).toBeInTheDocument();
    expect(screen.queryByText("Select a rig to begin")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
    expect(api.getRig).toHaveBeenCalledTimes(1);
    expect(api.getRig).toHaveBeenCalledWith(7);
  });

  it("retry re-invokes the detail load and renders the rig on success", async () => {
    api.getRig
      .mockRejectedValueOnce(new Error("boom"))
      .mockResolvedValueOnce({
        data: { ...summary, generation_seed: null, modules: [], case: null, vote_count: 0 },
      });
    renderPage();

    const retry = await screen.findByRole("button", { name: "Retry" });
    await userEvent.click(retry);

    await waitFor(() => expect(api.getRig).toHaveBeenCalledTimes(2));
    expect(api.getRig).toHaveBeenLastCalledWith(7);
    expect(await screen.findByRole("heading", { level: 1, name: "Golden Rig" })).toBeInTheDocument();
    expect(screen.queryByText("Unable to load rig details. Please try again.")).not.toBeInTheDocument();
  });
});
