import { afterEach, describe, expect, it, vi } from "vitest";

const post = vi.fn();
vi.mock("axios", () => ({ default: { post: (...args: unknown[]) => post(...args) } }));

import { refreshSession, signOut, SESSION_HEADER } from "./session";
import { useAuthStore } from "./store";

const user = { id: 1, username: "u" } as never;

afterEach(() => {
  post.mockReset();
  useAuthStore.getState().clear();
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
