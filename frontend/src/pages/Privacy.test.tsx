/**
 * The privacy notice has to stay honest and readable: marked as unreviewed, dated, plain about
 * the expiry job, pointing at the real delete control, and never offering a contact as working until
 * it is.
 */
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api", () => ({
  authApi: {
    login: vi.fn(),
    register: vi.fn(),
    signupOptions: vi.fn(async () => ({ data: { invite_required: false } })),
  },
}));

import LoginPage from "./Login";
import PrivacyPage from "./Privacy";

function renderNotice() {
  return render(
    <MemoryRouter initialEntries={["/privacy"]}>
      <PrivacyPage />
    </MemoryRouter>,
  );
}

describe("PrivacyPage", () => {
  it("has one h1 and headings that step down in order", () => {
    const { container } = renderNotice();
    const levels = [...container.querySelectorAll("h1, h2, h3, h4, h5, h6")].map((heading) =>
      Number(heading.tagName[1]),
    );

    expect(levels.filter((level) => level === 1)).toHaveLength(1);
    expect(levels[0]).toBe(1);
    levels.slice(1).forEach((level, index) => {
      expect(level - levels[index]).toBeLessThanOrEqual(1);
    });
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Privacy notice");
  });

  it("says it has not been reviewed, when it was updated and who operates the service", () => {
    renderNotice();

    expect(screen.getByText("Not yet reviewed by counsel")).toBeVisible();
    expect(screen.getByText("2026-11-04")).toHaveAttribute("datetime", "2026-11-04");
    expect(screen.getByText(/Last updated/)).toBeVisible();
    expect(screen.getByText(/Zero-State LLC operates PatchHive/)).toBeVisible();
  });

  it("lists the data held in a real table", () => {
    renderNotice();
    const table = screen.getByRole("table");

    expect(
      within(table)
        .getAllByRole("columnheader")
        .map((cell) => cell.textContent),
    ).toEqual(["Data", "Where", "How long"]);
    expect(within(table).getByRole("rowheader", { name: /Rig photos/ })).toBeInTheDocument();
    expect(within(table).getByRole("rowheader", { name: /Request logs/ })).toBeInTheDocument();
    expect(within(table).getAllByText("Neon").length).toBeGreaterThan(0);
    expect(within(table).getAllByText(/No period decided/).length).toBeGreaterThan(0);
    // Every stacked cell keeps its column head on a phone.
    table.querySelectorAll("td").forEach((cell) => {
      expect(cell).toHaveAttribute("data-label");
    });
  });

  it("states that expired photos are refused but their files wait for an unscheduled job", () => {
    renderNotice();

    expect(
      screen.getByText(/An expired photo is refused when the system tries to read it/),
    ).toHaveTextContent(/its file stays in storage until the expiry job runs/);
    expect(screen.getByText(/An expired photo is refused/)).toHaveTextContent(
      /That job isn.t scheduled yet/,
    );
    expect(screen.getByText(/A photo you upload is decoded/)).toHaveTextContent(/any JPEG comment/);
  });

  it("points people to the delete control on the account page", () => {
    renderNotice();

    expect(screen.getByText(/You can delete your account from the/)).toBeVisible();
    expect(screen.getByRole("link", { name: "account page" })).toHaveAttribute("href", "/account");
    expect(screen.queryByText("DELETE /api/me")).toBeNull();
  });

  it("keeps the contact gap and names only the planned address, as not working yet", () => {
    const { container } = renderNotice();
    const text = container.textContent ?? "";

    expect(screen.getByText("Gap: no contact address yet.")).toBeVisible();
    expect(text.match(/[\w.+-]+@[\w-]+(?:\.[\w-]+)+/g)).toEqual(["privacy@patch-hive.com"]);
    expect(screen.getByText(/privacy@patch-hive\.com/)).toHaveTextContent(
      /hasn.t been created, so it can.t receive anything today/,
    );
    expect(container.querySelector('a[href^="mailto:"]')).toBeNull();
  });

  it("makes no compliance claim", () => {
    const { container } = renderNotice();

    expect(container.textContent).not.toMatch(/GDPR|CCPA|complian/i);
  });

  it("says photos go to no outside AI provider on production", () => {
    renderNotice();

    expect(screen.getByText(/on production, photos go to none today/)).toBeVisible();
  });
});

describe("the sign-up form", () => {
  it("links the privacy notice when creating an account, not when signing in", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={["/login"]}>
        <LoginPage />
      </MemoryRouter>,
    );

    expect(screen.queryByRole("link", { name: "privacy notice" })).not.toBeInTheDocument();

    await user.click(screen.getByRole("tab", { name: "Create account" }));

    expect(screen.getByRole("link", { name: "privacy notice" })).toHaveAttribute(
      "href",
      "/privacy",
    );
  });
});
