/**
 * useToast — one short message at a time, with an optional action such as Undo. A newer
 * message replaces the one showing. Pairs with components/Toast.
 */
import { useCallback, useState } from "react";

export type ToastTone = "neutral" | "warning" | "danger";

export interface ToastMessage {
  /** Changes with every message, so the same text shown twice still restarts its timer. */
  id: number;
  text: string;
  tone: ToastTone;
  action?: { label: string; run: () => void };
  /** Where focus goes when the person dismisses it, such as the module it was about. */
  returnFocus?: () => void;
}

export function useToast() {
  const [toast, setToast] = useState<ToastMessage | null>(null);

  const show = useCallback(
    (text: string, options: Pick<Partial<ToastMessage>, "tone" | "action" | "returnFocus"> = {}) =>
      setToast((last) => ({
        id: (last?.id ?? 0) + 1,
        text,
        tone: options.tone ?? "neutral",
        action: options.action,
        returnFocus: options.returnFocus,
      })),
    [],
  );
  const dismiss = useCallback(() => setToast(null), []);

  return { toast, show, dismiss };
}
