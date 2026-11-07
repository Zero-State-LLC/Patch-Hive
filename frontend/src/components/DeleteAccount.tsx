/**
 * DeleteAccount — the Account page's way to `DELETE /api/me` (owner decision 47). Closed until
 * asked. Open, it states what goes and what stays, then needs the username typed and the current
 * password. A refusal is shown in place and changes nothing; success ends the session here, since
 * the API has already revoked it. REMOVED and KEPT mirror backend/account/deletion.py: a change to
 * what deletion does has to change them too, and the privacy notice with them.
 */
import { useEffect, useId, useRef, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { accountApi } from "@/lib/api";
import { failureReason } from "@/lib/loadError";
import { endLocalSession } from "@/lib/session";
import { useAuthStore } from "@/lib/store";

const REMOVED = [
  "Your email address, username, display name, avatar URL, bio, password and referral code are replaced or cleared.",
  "Every session is revoked, so you're signed out everywhere.",
  "Your comments, votes, patch overlays, patch annotations and style recipes are deleted.",
  "Your rigs are hidden and made private, and their names, descriptions and tags are cleared.",
  "Any publications are set to removed, with their text cleared and downloads turned off, and you're detached from any reports you filed.",
  "Your rig photos expire now and their files are deleted, unless another stored upload is the identical file. If storage fails, the file waits for the expiry job, which isn't scheduled yet.",
];

const KEPT = [
  "Credit ledger, referral rows, export records and exported files.",
  "Rig revisions, generation runs, patches and their receipts.",
  "Photo records and classification records.",
  "Admin audit records, including one that records this deletion with counts only.",
];

type Failure = { text: string; wrongPassword: boolean };

/** What the API said, in words. Only a refusal can promise that nothing was deleted. */
function describeFailure(error: unknown): Failure {
  const response = (error as { response?: { status?: number; data?: { detail?: unknown } } } | null)
    ?.response;
  if (response?.status === 403 && response.data?.detail === "PASSWORD_INCORRECT") {
    return {
      text: "That password didn't work, so nothing was deleted. After 5 wrong tries the account locks for 15 minutes, even with the right password.",
      wrongPassword: true,
    };
  }
  if (response?.status === 429) {
    return {
      text: "Too many attempts, so nothing was deleted. Wait a minute, then try again.",
      wrongPassword: false,
    };
  }
  if (response?.status === 401) {
    return {
      text: "Your session has ended. Sign in again to delete your account.",
      wrongPassword: false,
    };
  }
  return {
    text: `PatchHive couldn't confirm the deletion. ${failureReason(error)}`,
    wrongPassword: false,
  };
}

export default function DeleteAccount({
  username,
  onDeleted,
  onHoldPage,
}: {
  username: string;
  onDeleted: () => void;
  /** True from asking until the outcome is told, so a session ending meanwhile doesn't hide it. */
  onHoldPage?: (hold: boolean) => void;
}) {
  const id = useId();
  const [open, setOpen] = useState(false);
  const [typedUsername, setTypedUsername] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [failure, setFailure] = useState<Failure | null>(null);

  const trigger = useRef<HTMLButtonElement>(null);
  const panelHeading = useRef<HTMLHeadingElement>(null);
  const passwordInput = useRef<HTMLInputElement>(null);
  const submitButton = useRef<HTMLButtonElement>(null);
  const wasOpen = useRef(false);

  // Exact on purpose: a username can start or end with a space, and trimming locks that person out.
  const canSubmit = typedUsername === username && password.length > 0 && !submitting;

  // Opening lands on the panel's heading, so the terms are read before the form; closing goes
  // back to the button that opened it.
  useEffect(() => {
    if (open) panelHeading.current?.focus();
    else if (wasOpen.current) trigger.current?.focus();
    wasOpen.current = open;
  }, [open]);

  // Disabled controls lose focus during the request, so a failure puts it back where the next
  // step is: the emptied password field, or the button to try again.
  useEffect(() => {
    if (!failure) return;
    (failure.wrongPassword ? passwordInput : submitButton).current?.focus();
  }, [failure]);

  const close = () => {
    setOpen(false);
    setTypedUsername("");
    setPassword("");
    setFailure(null);
    onHoldPage?.(false);
  };

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    if (!canSubmit) return;
    setSubmitting(true);
    setFailure(null);
    onHoldPage?.(true);
    try {
      await accountApi.deleteAccount(password);
    } catch (error: unknown) {
      const next = describeFailure(error);
      if (next.wrongPassword) setPassword("");
      setFailure(next);
      setSubmitting(false);
      // With the session gone, closing this control is what lets the page move on.
      if (useAuthStore.getState().isAuthenticated()) onHoldPage?.(false);
      return;
    }
    endLocalSession();
    onDeleted();
  };

  return (
    <section className="ops-section account-delete" aria-labelledby={`${id}-heading`}>
      <h2 id={`${id}-heading`}>Delete account</h2>
      {open ? (
        <div className="account-delete__panel">
          <h3 ref={panelHeading} tabIndex={-1}>
            Confirm deletion
          </h3>
          <p className="status status-danger">
            This can&apos;t be undone. You won&apos;t be able to sign in again, and you&apos;ll lose
            access to your credits and exports.
          </p>
          <div className="account-delete__terms">
            <div>
              <h4>What&apos;s removed</h4>
              <ul className="account-delete__list">
                {REMOVED.map((line) => (
                  <li key={line}>{line}</li>
                ))}
              </ul>
            </div>
            <div>
              <h4>What&apos;s kept, anonymised</h4>
              <ul className="account-delete__list">
                {KEPT.map((line) => (
                  <li key={line}>{line}</li>
                ))}
              </ul>
              <p>
                Text inside these rows isn&apos;t cleared. Patch names and descriptions, for
                example, stay as they were. Deletion doesn&apos;t reach backups or logs, or anything
                at a payment or AI provider.
              </p>
            </div>
          </div>
          <form className="ops-form" onSubmit={(event) => void handleSubmit(event)} noValidate>
            <label className="field">
              <span>
                Type your username, <strong className="account-delete__name">{username}</strong>, to
                confirm
              </span>
              <input
                type="text"
                autoComplete="off"
                autoCapitalize="none"
                autoCorrect="off"
                spellCheck={false}
                value={typedUsername}
                onChange={(event) => setTypedUsername(event.target.value)}
                disabled={submitting}
              />
            </label>
            <label className="field">
              Current password
              <input
                ref={passwordInput}
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                disabled={submitting}
                aria-invalid={failure?.wrongPassword ? true : undefined}
                aria-describedby={failure?.wrongPassword ? `${id}-failure` : undefined}
              />
            </label>
            <p id={`${id}-hint`} className="muted">
              Delete my account turns on once your username matches and you&apos;ve entered your
              password.
            </p>
            {failure ? (
              <p id={`${id}-failure`} className="status status-danger" role="alert">
                {failure.text}
              </p>
            ) : null}
            <div className="account-delete__actions">
              <button
                ref={submitButton}
                type="submit"
                className="button button-secondary"
                disabled={!canSubmit}
                aria-describedby={`${id}-hint`}
              >
                {submitting ? "Deleting…" : "Delete my account"}
              </button>
              <button
                type="button"
                className="button button-quiet"
                onClick={close}
                disabled={submitting}
              >
                Keep my account
              </button>
            </div>
          </form>
        </div>
      ) : (
        <>
          <p>
            Deleting your account anonymises it and removes your personal content. You&apos;ll see
            what&apos;s removed and what&apos;s kept before you confirm.
          </p>
          <button
            ref={trigger}
            type="button"
            className="button button-secondary"
            onClick={() => setOpen(true)}
          >
            Delete account…
          </button>
        </>
      )}
    </section>
  );
}

/** What the Account page becomes once the account is gone. Focus lands on its heading. */
export function AccountDeleted() {
  const heading = useRef<HTMLHeadingElement>(null);

  useEffect(() => {
    heading.current?.focus();
  }, []);

  return (
    <section aria-labelledby="account-deleted-title">
      <header className="workspace-header">
        <div>
          <h1 id="account-deleted-title" ref={heading} tabIndex={-1}>
            Account deleted
          </h1>
          <p className="muted">
            You&apos;re signed out, and you can&apos;t sign in to this account again. The anonymised
            records listed before you confirmed are kept.
          </p>
        </div>
      </header>
      <Link className="button button-primary" to="/">
        Return home
      </Link>
    </section>
  );
}
