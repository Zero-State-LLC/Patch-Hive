/**
 * The API client renews an expired access token once and retries the request once, and never
 * loops: a second 401, a refused renewal or a sign-in call fails as it is.
 */
import {
  AxiosError,
  type AxiosAdapter,
  type AxiosResponse,
  type InternalAxiosRequestConfig,
} from "axios";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const refreshSession = vi.fn<() => Promise<string | null>>();
vi.mock("./session", () => ({ refreshSession: () => refreshSession() }));

import api from "./api";
import { useAuthStore } from "./store";

const original = api.defaults.adapter;
/** The Authorization header of each request as it was sent. */
let seen: string[] = [];

const bearer = (config: InternalAxiosRequestConfig) => String(config.headers.Authorization);

/** Answers every request with the status `reply` picks, as the server would. */
function serve(reply: (config: InternalAxiosRequestConfig) => number) {
  const adapter: AxiosAdapter = async (config) => {
    seen.push(bearer(config));
    const status = reply(config);
    const response: AxiosResponse = {
      status,
      statusText: String(status),
      data: { ok: status < 400 },
      headers: {},
      config,
    };
    if (status >= 400) {
      throw new AxiosError(`status ${status}`, AxiosError.ERR_BAD_REQUEST, config, null, response);
    }
    return response;
  };
  api.defaults.adapter = adapter;
}

/** A renewal that succeeds stores its token, as the real refreshSession does. */
const renewTo = (token: string) =>
  refreshSession.mockImplementation(async () => {
    useAuthStore.setState({ token });
    return token;
  });

beforeEach(() => {
  seen = [];
  useAuthStore.getState().setAuth({ id: 1, username: "u" } as never, "stale");
});

afterEach(() => {
  api.defaults.adapter = original;
  refreshSession.mockReset();
  useAuthStore.getState().clear();
});

describe("401 renewal", () => {
  it("renews once and retries the request with the new token", async () => {
    renewTo("fresh");
    serve((config) => (bearer(config) === "Bearer fresh" ? 200 : 401));

    const response = await api.get("/canon/rigs");

    expect(response.data).toEqual({ ok: true });
    expect(refreshSession).toHaveBeenCalledTimes(1);
    expect(seen).toEqual(["Bearer stale", "Bearer fresh"]);
  });

  it("gives up after one retry instead of looping", async () => {
    renewTo("fresh");
    serve(() => 401);

    await expect(api.get("/canon/rigs")).rejects.toMatchObject({ response: { status: 401 } });

    expect(refreshSession).toHaveBeenCalledTimes(1);
    expect(seen).toHaveLength(2);
  });

  it("fails as it is when the renewal is refused", async () => {
    refreshSession.mockResolvedValue(null);
    serve(() => 401);

    await expect(api.get("/canon/rigs")).rejects.toMatchObject({ response: { status: 401 } });

    expect(seen).toHaveLength(1);
  });

  it("never renews for sign-in and session calls", async () => {
    serve(() => 401);

    await expect(api.post("/community/auth/login", {})).rejects.toMatchObject({
      response: { status: 401 },
    });

    expect(refreshSession).not.toHaveBeenCalled();
    expect(seen).toHaveLength(1);
  });

  it("leaves other failures alone", async () => {
    serve(() => 500);

    await expect(api.get("/canon/rigs")).rejects.toMatchObject({ response: { status: 500 } });

    expect(refreshSession).not.toHaveBeenCalled();
    expect(seen).toHaveLength(1);
  });
});

describe("timeout", () => {
  it("ends a request that hangs after 15 seconds", () => {
    expect(api.defaults.timeout).toBe(15_000);
  });
});
