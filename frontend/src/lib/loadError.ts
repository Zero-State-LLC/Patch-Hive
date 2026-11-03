/**
 * loadError — tells the ways a load can fail apart, so a page never shows a failure as an empty
 * result: the page cancelled it, it timed out, PatchHive can't be reached, or the server said no.
 */
import axios from "axios";

export type FailureKind = "timeout" | "offline" | "unavailable" | "missing" | "denied" | "server";

/** A request the page cancelled itself because it moved on. Never shown as a failure. */
export function isCancelled(error: unknown): boolean {
  return axios.isCancel(error) || (error as { code?: string } | null)?.code === "ERR_CANCELED";
}

export function failureKind(error: unknown): FailureKind {
  const e = error as { code?: string; response?: { status?: number } } | null;
  if (e?.code === "ECONNABORTED" || e?.code === "ETIMEDOUT") return "timeout";
  const status = e?.response?.status;
  if (status == null) return "offline";
  // A gateway answering for a server that is down or restarting.
  if (status === 502 || status === 503 || status === 504) return "unavailable";
  if (status === 404) return "missing";
  if (status === 401 || status === 403) return "denied";
  return "server";
}

/** One plain sentence on why, to follow "X didn't load." */
export function failureReason(error: unknown): string {
  switch (failureKind(error)) {
    case "timeout":
      return "PatchHive took too long to answer.";
    case "offline":
      return "PatchHive can't be reached. Check your connection.";
    case "unavailable":
      return "PatchHive isn't answering right now. Try again in a moment.";
    case "missing":
      return "PatchHive couldn't find it.";
    case "denied":
      return "Your account can't open it.";
    default:
      return "Something went wrong on our side.";
  }
}
