/**
 * Deleting an account can't be undone, so the control has to state the terms, make the person
 * mean it, and never read a failure as success.
 */
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const api = vi.hoisted(() => ({ accountApi: { deleteAccount: vi.fn() } }));
const session = vi.hoisted(() => ({ endLocalSession: vi.fn() }));

vi.mock("@/lib/api", () => api);
vi.mock("@/lib/session", () => session);

import DeleteAccount from "./DeleteAccount";

const USERNAME = "demo-user";
const PASSWORD = "correct horse";

function refusal(status: number, detail?: string) {
  return Object.assign(new Error(`HTTP ${status}`), { response: { status, data: { detail } } });
}

function renderControl() {
  const onDeleted = vi.fn();
  render(<DeleteAccount username={USERNAME} onDeleted={onDeleted} />);
  return { onDeleted, user: userEvent.setup() };
}

async function openAndFill(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByRole("button", { name: "Delete account…" }));
  await user.type(screen.getByLabelText(/Type your username/), USERNAME);
  await user.type(screen.getByLabelText("Current password"), PASSWORD);
}

const submit = () => screen.getByRole("button", { name: /Delete my account|Deleting/ });

beforeEach(() => {
  api.accountApi.deleteAccount.mockReset();
  session.endLocalSession.mockReset();
});

describe("DeleteAccount", () => {
  it("stays closed until asked, then lands on the terms", async () => {
    const { user } = renderControl();

    expect(screen.queryByLabelText("Current password")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Delete account…" }));

    expect(screen.getByRole("heading", { level: 3, name: "Confirm deletion" })).toHaveFocus();
    expect(screen.getByRole("heading", { level: 4, name: "What's removed" })).toBeVisible();
    expect(
      screen.getByRole("heading", { level: 4, name: "What's kept, anonymised" }),
    ).toBeVisible();
  });

  it("states what's removed and what's kept, as the backend does it", async () => {
    const { user } = renderControl();
    await user.click(screen.getByRole("button", { name: "Delete account…" }));

    expect(screen.getByText(/This can't be undone/)).toBeVisible();
    for (const removed of [
      /email address, username, display name, avatar URL, bio, password and referral code/,
      /Every session is revoked/,
      /comments, votes, patch overlays, patch annotations and style recipes are deleted/,
      /rigs are hidden and made private/,
      /publications are set to removed/,
      /rig photos expire now and their files are deleted, unless another stored upload/,
      /waits for the expiry job, which isn't scheduled yet/,
    ]) {
      expect(screen.getByText(removed)).toBeVisible();
    }
    for (const kept of [
      /Credit ledger, referral rows, export records and exported files/,
      /Rig revisions, generation runs, patches and their receipts/,
      /Photo records and classification records/,
      /Admin audit records/,
      /Text inside these rows isn't cleared/,
      /Deletion doesn't reach backups or logs/,
    ]) {
      expect(screen.getByText(kept)).toBeVisible();
    }
  });

  it("needs the exact username and a password before it can be pressed", async () => {
    const { user } = renderControl();
    await user.click(screen.getByRole("button", { name: "Delete account…" }));

    expect(submit()).toBeDisabled();
    await user.type(screen.getByLabelText("Current password"), PASSWORD);
    expect(submit()).toBeDisabled();
    await user.type(screen.getByLabelText(/Type your username/), USERNAME.toUpperCase());
    expect(submit()).toBeDisabled();

    await user.clear(screen.getByLabelText(/Type your username/));
    await user.type(screen.getByLabelText(/Type your username/), USERNAME);
    expect(submit()).toBeEnabled();
    expect(api.accountApi.deleteAccount).not.toHaveBeenCalled();
  });

  it("doesn't send anything on Enter while the username doesn't match", async () => {
    const { user } = renderControl();
    await user.click(screen.getByRole("button", { name: "Delete account…" }));
    await user.type(screen.getByLabelText("Current password"), `${PASSWORD}{Enter}`);

    expect(api.accountApi.deleteAccount).not.toHaveBeenCalled();
  });

  it("sends the password once, signs out here and reports success", async () => {
    let finish: () => void = () => {};
    api.accountApi.deleteAccount.mockReturnValue(
      new Promise<void>((resolve) => (finish = resolve)),
    );
    const { user, onDeleted } = renderControl();
    await openAndFill(user);

    await user.click(submit());

    expect(api.accountApi.deleteAccount).toHaveBeenCalledWith(PASSWORD);
    expect(submit()).toBeDisabled();
    expect(submit()).toHaveTextContent("Deleting…");
    expect(screen.getByRole("button", { name: "Keep my account" })).toBeDisabled();
    expect(session.endLocalSession).not.toHaveBeenCalled();
    expect(onDeleted).not.toHaveBeenCalled();

    finish();

    await waitFor(() => expect(onDeleted).toHaveBeenCalledTimes(1));
    expect(session.endLocalSession).toHaveBeenCalledTimes(1);
    expect(api.accountApi.deleteAccount).toHaveBeenCalledTimes(1);
  });

  it("shows a wrong password in place, empties the field and stays signed in", async () => {
    api.accountApi.deleteAccount.mockRejectedValue(refusal(403, "PASSWORD_INCORRECT"));
    const { user, onDeleted } = renderControl();
    await openAndFill(user);

    await user.click(submit());

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/That password didn't work, so nothing was deleted/);
    expect(alert).toHaveTextContent(/locks for 15 minutes/);
    const field = screen.getByLabelText("Current password");
    expect(field).toHaveValue("");
    expect(field).toHaveFocus();
    expect(field).toHaveAttribute("aria-invalid", "true");
    expect(submit()).toBeDisabled();
    expect(session.endLocalSession).not.toHaveBeenCalled();
    expect(onDeleted).not.toHaveBeenCalled();
  });

  it.each([
    [refusal(429), /Too many attempts, so nothing was deleted/],
    [refusal(401), /Your session has ended/],
    // A 403 that isn't the API's own answer says nothing about the password.
    [refusal(403), /couldn't confirm the deletion/],
    [refusal(503), /couldn't confirm the deletion. PatchHive isn't answering right now/],
    [new Error("Network Error"), /couldn't confirm the deletion. PatchHive can't be reached/],
  ])("shows a failure and keeps the form ready: %s", async (error, message) => {
    api.accountApi.deleteAccount.mockRejectedValue(error);
    const { user, onDeleted } = renderControl();
    await openAndFill(user);

    await user.click(submit());

    expect(await screen.findByRole("alert")).toHaveTextContent(message);
    expect(screen.getByLabelText("Current password")).toHaveValue(PASSWORD);
    expect(submit()).toBeEnabled();
    expect(submit()).toHaveFocus();
    expect(session.endLocalSession).not.toHaveBeenCalled();
    expect(onDeleted).not.toHaveBeenCalled();
  });

  it("clears a failure on the next try, and can still succeed", async () => {
    api.accountApi.deleteAccount
      .mockRejectedValueOnce(new Error("Network Error"))
      .mockResolvedValueOnce(undefined);
    const { user, onDeleted } = renderControl();
    await openAndFill(user);

    await user.click(submit());
    await screen.findByRole("alert");
    await user.click(submit());

    await waitFor(() => expect(onDeleted).toHaveBeenCalledTimes(1));
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("backs out without sending anything, forgets the fields and returns focus", async () => {
    const { user } = renderControl();
    await openAndFill(user);

    await user.click(screen.getByRole("button", { name: "Keep my account" }));

    const trigger = screen.getByRole("button", { name: "Delete account…" });
    expect(trigger).toHaveFocus();
    expect(api.accountApi.deleteAccount).not.toHaveBeenCalled();

    await user.click(trigger);
    expect(screen.getByLabelText(/Type your username/)).toHaveValue("");
    expect(screen.getByLabelText("Current password")).toHaveValue("");
  });
});
