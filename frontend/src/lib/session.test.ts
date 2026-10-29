import { afterEach, describe, expect, it, vi } from "vitest";

const post = vi.fn();
vi.mock("axios", () => ({ default: { post: (...args: unknown[]) => post(...args) } }));

import { refreshSession, restoreSession, signOut, SESSION_HEADER } from "./session";
import { SESSION_HINT, useAuthStore } from "./store";

const user = { id: 1, username: "u" } as never;

afterEach(() => {
  post.mockReset();
  useAuthStore.getState().clear();
  localStorage.removeItem(SESSION_HINT);
});

describe("refreshSession", () => {
  it("shares one request between concurrent callers and stores the token in memory", async () => {
    post.mockResolvedValue({ data: { access_token: "fresh", user } });
    const [a, b] = await Promise.all([refreshSession(), refreshSession()]);
    expect(post).toHaveBeenCalledTimes(1);
    expect(post.mock.calls[0][2]).toMatchObject({ withCredentials: true, headers: SESSION_HEADER });
    expect([a, b]).toEqual(["fresh", "fresh"]);
    expect(useAuthStore.getState().token).toBe("fresh");
    expect(localStorage.getItem("auth_token")).toBeNull();
  });

  it("clears the session when the refresh cookie is refused", async () => {
    useAuthStore.getState().setAuth(user, "stale");
    post.mockRejectedValue(new Error("401"));
    expect(await refreshSession()).toBeNull();
    expect(useAuthStore.getState().token).toBeNull();
  });
});

describe("signOut", () => {
  it("clears memory even when the API call fails", async () => {
    useAuthStore.getState().setAuth(user, "token");
    post.mockRejectedValue(new Error("offline"));
    await expect(signOut()).rejects.toThrow();
    expect(useAuthStore.getState().token).toBeNull();
  });
});

describe("session hint", () => {
  it("is set by a successful renewal and cleared by a refused one", async () => {
    post.mockResolvedValueOnce({ data: { access_token: "fresh", user } });
    await refreshSession();
    expect(localStorage.getItem(SESSION_HINT)).toBe("1");

    post.mockRejectedValueOnce({ response: { status: 401 } });
    await refreshSession();
    expect(localStorage.getItem(SESSION_HINT)).toBe("0");
  });

  it("survives a network error, which says nothing about the cookie", async () => {
    localStorage.setItem(SESSION_HINT, "1");
    post.mockRejectedValueOnce(new Error("offline"));
    await refreshSession();
    expect(localStorage.getItem(SESSION_HINT)).toBe("1");
  });

  it("makes a signed-out page load skip the refresh call", async () => {
    localStorage.setItem(SESSION_HINT, "0");
    expect(await restoreSession()).toBeNull();
    expect(post).not.toHaveBeenCalled();
  });

  it("still tries once with no hint (first visit, or a session from before the hint)", async () => {
    post.mockResolvedValueOnce({ data: { access_token: "fresh", user } });
    expect(await restoreSession()).toBe("fresh");
    expect(post).toHaveBeenCalledTimes(1);
  });

  it("is set by sign-in and cleared by sign-out", async () => {
    useAuthStore.getState().setAuth(user, "token");
    expect(localStorage.getItem(SESSION_HINT)).toBe("1");
    post.mockResolvedValueOnce({});
    await signOut();
    expect(localStorage.getItem(SESSION_HINT)).toBe("0");
  });
});
