/**
 * Toast — a short message at the foot of the screen, announced politely, with an optional action
 * (Undo). A plain message leaves on its own after a few seconds, never while the pointer or focus
 * is on it. One with an action stays until it is used, dismissed or replaced, however long that
 * takes, and Ctrl+Z (Cmd+Z on a Mac) runs its action from anywhere outside a text field. The live
 * region is always mounted, so screen readers hear each new message.
 */
import { useEffect, useRef, useState } from "react";
import type { ToastMessage } from "@/lib/useToast";

const TOAST_MS = 6000;

/** Where Ctrl+Z belongs to the field being typed in, not to the toast. */
function editsText(target: EventTarget | null): boolean {
  const el = target as HTMLElement | null;
  return Boolean(el?.closest?.("input, textarea, select, [contenteditable='true']"));
}

export default function Toast({
  toast,
  onDismiss,
  actionDisabled = false,
}: {
  toast: ToastMessage | null;
  onDismiss: () => void;
  /** The action waits, such as Undo while a save is still under way. */
  actionDisabled?: boolean;
}) {
  const [held, setHeld] = useState(false);
  const region = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!toast || held || toast.action) return;
    const timer = window.setTimeout(onDismiss, TOAST_MS);
    return () => window.clearTimeout(timer);
  }, [toast, held, onDismiss]);

  const action = toast?.action;
  useEffect(() => {
    if (!action || actionDisabled) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key.toLowerCase() !== "z" || !(event.ctrlKey || event.metaKey)) return;
      if (event.shiftKey || event.altKey || editsText(event.target)) return;
      event.preventDefault();
      action.run();
      onDismiss();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [action, actionDisabled, onDismiss]);

  // A toast that leaves while held would strand the hold; a new one starts unheld.
  useEffect(() => setHeld(false), [toast?.id]);

  return (
    <div
      ref={region}
      className="toast-region"
      role="status"
      aria-live="polite"
      onMouseEnter={() => setHeld(true)}
      onMouseLeave={() => setHeld(false)}
      onFocus={() => setHeld(true)}
      onBlur={(event) => {
        if (!region.current?.contains(event.relatedTarget as Node | null)) setHeld(false);
      }}
    >
      {toast ? (
        <div key={toast.id} className="toast" data-tone={toast.tone}>
          <p className="toast__text">{toast.text}</p>
          {toast.action ? (
            <button
              className="button button-secondary toast__action"
              type="button"
              disabled={actionDisabled}
              aria-keyshortcuts="Control+Z Meta+Z"
              onClick={() => {
                toast.action?.run();
                onDismiss();
              }}
            >
              {toast.action.label}
            </button>
          ) : null}
          <button
            className="button button-quiet toast__dismiss"
            type="button"
            onClick={() => {
              toast.returnFocus?.();
              onDismiss();
            }}
          >
            Dismiss
          </button>
        </div>
      ) : null}
    </div>
  );
}
