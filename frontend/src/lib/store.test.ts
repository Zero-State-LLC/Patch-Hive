/**
 * The store holds who's reading, and every account-keyed page follows it. A profile answer can land
 * after its reader has gone, so `setUser` may only refresh the account already held.
 */
import { afterEach, describe, expect, it } from "vitest";
import type { User } from "@/types/api";
import { useAuthStore } from "./store";

const account = (id: number, display_name: string) =>
  ({ id, username: `reader-${id}`, display_name }) as unknown as User;

afterEach(() => {
  useAuthStore.getState().clear();
});

describe("setUser", () => {
  it("refreshes the account that's signed in", () => {
    useAuthStore.getState().setAuth(account(1, "Before"), "token");

    useAuthStore.getState().setUser(account(1, "After"));

    expect(useAuthStore.getState().user?.display_name).toBe("After");
  });

  it("ignores another account's profile", () => {
    const second = account(2, "Second");
    useAuthStore.getState().setAuth(second, "token-2");

    useAuthStore.getState().setUser(account(1, "First"));

    expect(useAuthStore.getState().user).toBe(second);
  });

  it("doesn't fill the slot after sign-out", () => {
    useAuthStore.getState().setAuth(account(1, "First"), "token");
    useAuthStore.getState().clear();

    useAuthStore.getState().setUser(account(1, "First"));

    expect(useAuthStore.getState().user).toBeNull();
  });
});
