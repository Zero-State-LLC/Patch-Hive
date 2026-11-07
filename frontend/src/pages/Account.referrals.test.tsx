/**
 * The Account page's referral summary (spec 004 FR-031): what the API counted, in words a person
 * reads, and a plain note while referrals are off.
 */
import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const api = vi.hoisted(() => ({
  accountApi: {
    deleteAccount: vi.fn(),
    getCredits: vi.fn(),
    getExports: vi.fn(),
    getReferrals: vi.fn(),
  },
  authApi: { getMe: vi.fn(), updateProfile: vi.fn() },
  canonApi: { createDownloadToken: vi.fn() },
}));

vi.mock("@/lib/api", () => api);

import { SESSION_HINT, useAuthStore } from "@/lib/store";
import AccountPage from "./Account";

const USER = {
  id: 1,
  username: "demo-user",
  email: "demo@example.test",
  role: "User",
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

beforeEach(() => {
  useAuthStore.getState().setAuth(USER, "token");
  api.authApi.getMe.mockResolvedValue({ data: USER });
  api.accountApi.getCredits.mockResolvedValue({ data: { balance: 3, entries: [] } });
  api.accountApi.getExports.mockResolvedValue({ data: [] });
});

afterEach(() => {
  useAuthStore.getState().clear();
  localStorage.removeItem(SESSION_HINT);
  vi.restoreAllMocks();
});

function renderPage() {
  render(
    <MemoryRouter>
      <AccountPage />
    </MemoryRouter>,
  );
}

function readout(section: HTMLElement, term: string) {
  const label = within(section).getByText(term);
  return label.parentElement?.querySelector("dd")?.textContent;
}

describe("Account page, referrals", () => {
  it("shows pending, rewarded and the credits earned", async () => {
    api.accountApi.getReferrals.mockResolvedValue({
      data: {
        referral_code: "REFCODE",
        referral_link: "https://patch-hive.test/signup?ref=REFCODE",
        pending_count: 2,
        rewarded_count: 1,
        earned_credits: 3,
        recent_referrals: [],
      },
    });

    renderPage();

    expect(await screen.findByDisplayValue(/signup\?ref=REFCODE/)).toBeTruthy();
    const section = screen.getByRole("region", { name: "Referrals" });
    expect(readout(section, "Pending")).toBe("2");
    expect(readout(section, "Rewarded")).toBe("1");
    expect(readout(section, "Credits earned")).toBe("3");
  });

  it("says referrals aren't open when the route answers 404", async () => {
    api.accountApi.getReferrals.mockRejectedValue(new Error("off"));

    renderPage();

    expect(await screen.findByText(/Referrals aren.t open yet/)).toBeTruthy();
  });
});
