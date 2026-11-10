/**
 * A new invite's code is shown once, and the list says which invites are used.
 */
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const api = vi.hoisted(() => ({
  adminApi: { listInvites: vi.fn(), createInvite: vi.fn() },
}));

vi.mock("@/lib/api", () => api);
vi.mock("./AdminGuard", () => ({ AdminGuard: ({ children }: { children: React.ReactNode }) => children }));

import AdminInvites from "./AdminInvites";

const STAMP = "2026-11-10T00:00:00Z";

beforeEach(() => {
  api.adminApi.listInvites.mockResolvedValue({
    data: {
      invites: [
        { id: 1, credits: 9, note: "A tester", created_at: STAMP, redeemed_at: STAMP },
        { id: 2, credits: 3, note: null, created_at: STAMP, redeemed_at: null },
      ],
    },
  });
});

afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});

const renderPage = () =>
  render(
    <MemoryRouter>
      <AdminInvites />
    </MemoryRouter>,
  );

describe("the invites console", () => {
  it("says which invites are used", async () => {
    renderPage();
    expect(await screen.findByText("A tester: 9 credits, used")).toBeTruthy();
    expect(screen.getByText("Invite 2: 3 credits, not used yet")).toBeTruthy();
  });

  it("shows a new code, and sends the credits and who it's for", async () => {
    api.adminApi.createInvite.mockResolvedValue({ data: { id: 3, credits: 9, code: "fresh-code" } });
    const user = userEvent.setup();
    renderPage();
    await user.type(screen.getByLabelText("Who it's for"), "Second tester");
    await user.click(screen.getByRole("button", { name: "Create invite" }));
    expect((await screen.findByRole("status")).textContent).toContain("fresh-code");
    expect(api.adminApi.createInvite).toHaveBeenCalledWith(9, "Second tester");
  });

  it("says so when an invite can't be created", async () => {
    api.adminApi.createInvite.mockRejectedValue(new Error("no"));
    const user = userEvent.setup();
    renderPage();
    await user.click(screen.getByRole("button", { name: "Create invite" }));
    expect((await screen.findByRole("alert")).textContent).toContain("Could not create");
  });
});
