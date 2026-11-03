import { AxiosError, CanceledError } from "axios";
import { describe, expect, it } from "vitest";
import { failureKind, failureReason, isCancelled } from "./loadError";

const withStatus = (status: number) =>
  new AxiosError("failed", AxiosError.ERR_BAD_RESPONSE, undefined, null, {
    status,
    statusText: "",
    data: {},
    headers: {},
    config: {} as never,
  });

describe("loadError", () => {
  it("knows a request the page cancelled from one that failed", () => {
    expect(isCancelled(new CanceledError())).toBe(true);
    expect(isCancelled({ code: "ERR_CANCELED" })).toBe(true);
    expect(isCancelled(new AxiosError("offline", AxiosError.ERR_NETWORK))).toBe(false);
    expect(isCancelled(null)).toBe(false);
  });

  it("tells a timeout, an unreachable API and the server's answers apart", () => {
    expect(failureKind(new AxiosError("slow", AxiosError.ECONNABORTED))).toBe("timeout");
    expect(failureKind(new AxiosError("slow", AxiosError.ETIMEDOUT))).toBe("timeout");
    expect(failureKind(new AxiosError("offline", AxiosError.ERR_NETWORK))).toBe("offline");
    expect(failureKind(withStatus(502))).toBe("unavailable");
    expect(failureKind(withStatus(503))).toBe("unavailable");
    expect(failureKind(withStatus(404))).toBe("missing");
    expect(failureKind(withStatus(403))).toBe("denied");
    expect(failureKind(withStatus(500))).toBe("server");
  });

  it("says why in one sentence", () => {
    expect(failureReason(new AxiosError("slow", AxiosError.ECONNABORTED))).toBe(
      "PatchHive took too long to answer.",
    );
    expect(failureReason(new AxiosError("offline", AxiosError.ERR_NETWORK))).toMatch(
      /can't be reached/,
    );
    expect(failureReason(withStatus(503))).toBe(
      "PatchHive isn't answering right now. Try again in a moment.",
    );
    expect(failureReason(withStatus(500))).toMatch(/\.$/);
  });
});
