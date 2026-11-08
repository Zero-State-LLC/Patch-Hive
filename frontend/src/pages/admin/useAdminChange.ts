/**
 * useAdminChange — one admin change at a time: the controls that change something wait while one
 * is in flight, and a change that fails is said on the screen instead of being dropped.
 */
import { useState } from "react";
import { failureReason } from "@/lib/loadError";

export function useAdminChange() {
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState("");

  /** Run the change; says whether it went through. */
  const run = async (change: () => Promise<unknown>): Promise<boolean> => {
    setBusy(true);
    setFailure("");
    try {
      await change();
      return true;
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: unknown } } } | null)?.response?.data
        ?.detail;
      setFailure(
        typeof detail === "string"
          ? `That change was refused: ${detail}`
          : `That change didn't save. ${failureReason(err)}`,
      );
      return false;
    } finally {
      setBusy(false);
    }
  };

  return { busy, failure, run };
}
