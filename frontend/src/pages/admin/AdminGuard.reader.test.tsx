/**
 * Admin screens fetch above their guard, so the guard is what takes their data off the screen when
 * the reader signs out. Each mock answers for whoever holds the token at the time of the call, as
 * the API would.
 */
import { act, cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { useAuthStore } from "@/lib/store";
import type { User } from "@/types/api";

const api = vi.hoisted(() => ({ adminApi: { listUsers: vi.fn() } }));

vi.mock("@/lib/api", () => api);

import AdminUsers from "./AdminUsers";

const ADMIN = { id: 1, username: "admin", role: "Admin" } as unknown as User;
const LISTED = {
  id: 9,
  username: "private-member",
  email: "member@example.test",
  role: "User",
  created_at: "2026-01-01T00:00:00Z",
  avatar_url: null,
  credits_balance: 0,
};

afterEach(() => {
  cleanup();
  vi.resetAllMocks();
  useAuthStore.getState().clear();
});

describe("a change of reader on an admin screen", () => {
  it("takes the screen's data away on sign-out, even if an answer lands afterwards", async () => {
    let answer: (value: unknown) => void = () => {};
    api.adminApi.listUsers.mockResolvedValueOnce({ data: { total: 1, users: [LISTED] } });
    useAuthStore.getState().setAuth(ADMIN, "token");
    render(
      <MemoryRouter>
        <AdminUsers />
      </MemoryRouter>,
    );
    await screen.findByText(/private-member/);
    api.adminApi.listUsers.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          answer = resolve;
        }),
    );

    act(() => useAuthStore.getState().clear());
    await act(async () => answer({ data: { total: 1, users: [LISTED] } }));

    expect(screen.getByText("Admin access required")).toBeInTheDocument();
    expect(screen.queryByText(/private-member/)).toBeNull();
  });
});
