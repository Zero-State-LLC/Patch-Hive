/**
 * Admin screens say when they are loading and when a load or a change fails, and their controls
 * wait while a change is in flight.
 */
import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useAuthStore } from "@/lib/store";
import type { User } from "@/types/api";

const api = vi.hoisted(() => ({
  adminApi: { listRuns: vi.fn(), listGalleryRevisions: vi.fn(), approveRevision: vi.fn() },
  moduleApi: {},
}));

vi.mock("@/lib/api", () => api);

import AdminGallery from "./AdminGallery";
import AdminRuns from "./AdminRuns";

const ADMIN = { id: 1, username: "admin", role: "Admin" } as unknown as User;
const REVISION = { id: 4, module_key: "maker/vco", revision_id: "rev-4", status: "pending" };

const renderScreen = (screenElement: JSX.Element) =>
  render(<MemoryRouter>{screenElement}</MemoryRouter>);

beforeEach(() => {
  useAuthStore.getState().setAuth(ADMIN, "token");
});

afterEach(() => {
  vi.resetAllMocks();
  useAuthStore.getState().clear();
});

describe("admin screen states", () => {
  it("shows a loading state, then a failure with Retry that loads again", async () => {
    let fail: (reason: unknown) => void = () => {};
    api.adminApi.listRuns.mockReturnValueOnce(new Promise((_, reject) => (fail = reject)));
    renderScreen(<AdminRuns />);

    // The skeleton's status line fills a beat after it mounts (Skeletons.tsx).
    expect(await screen.findByText("Loading runs…")).toHaveAttribute("role", "status");
    expect(screen.queryByText("No runs loaded.")).toBeNull();

    await act(async () => fail({ response: { status: 503 } }));
    expect(screen.getByRole("alert")).toHaveTextContent("The run list didn't load.");

    api.adminApi.listRuns.mockResolvedValueOnce({ data: { runs: [] } });
    await userEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(await screen.findByText("No runs loaded.")).toBeInTheDocument();
  });

  it("holds the controls while a change is in flight, and says when it fails", async () => {
    api.adminApi.listGalleryRevisions.mockResolvedValue({ data: { revisions: [REVISION] } });
    let fail: (reason: unknown) => void = () => {};
    api.adminApi.approveRevision.mockReturnValueOnce(new Promise((_, reject) => (fail = reject)));
    renderScreen(<AdminGallery />);

    const approve = await screen.findByRole("button", { name: "Approve" });
    await userEvent.click(approve);
    expect(approve).toBeDisabled();
    expect(screen.getByRole("button", { name: "Confirm" })).toBeDisabled();

    await act(async () =>
      fail({ response: { status: 409, data: { detail: "already approved" } } }),
    );
    expect(screen.getByRole("alert")).toHaveTextContent(
      "That change was refused: already approved",
    );
    expect(screen.getByRole("button", { name: "Approve" })).toBeEnabled();
  });
});
