/**
 * Global state management using Zustand.
 *
 * The access token lives only in memory: script injected into the page cannot lift it
 * from storage, and it expires in minutes. The session survives reloads through the
 * API's HttpOnly refresh cookie (see lib/session.ts).
 */
import { create } from "zustand";
import type { User } from "@/types/api";

/**
 * Whether this browser may hold a refresh cookie: "1" after sign-in or a renewal, "0"
 * after sign-out or a refused renewal, absent before either. Not a credential, only a
 * hint, so a signed-out page load skips the refresh call (and its 401).
 */
export const SESSION_HINT = "ph_session_hint";

export function setSessionHint(signedIn: boolean): void {
  try {
    localStorage.setItem(SESSION_HINT, signedIn ? "1" : "0");
  } catch {
    // storage unavailable: page loads keep trying the refresh call
  }
}

export function sessionHint(): "1" | "0" | null {
  try {
    const value = localStorage.getItem(SESSION_HINT);
    return value === "1" || value === "0" ? value : null;
  } catch {
    return null;
  }
}

// Tokens used to be kept here; remove any left behind by an older build.
try {
  localStorage.removeItem("auth_token");
} catch {
  // storage unavailable (private mode): nothing to clean up
}

interface AuthState {
  user: User | null;
  token: string | null;
  setAuth: (user: User, token: string) => void;
  setUser: (user: User) => void;
  clear: () => void;
  isAuthenticated: () => boolean;
}

export const useAuthStore = create<AuthState>((set, get) => ({
  user: null,
  token: null,

  setAuth: (user, token) => {
    setSessionHint(true);
    set({ user, token });
  },

  setUser: (user) => set({ user }),

  clear: () => set({ user: null, token: null }),

  isAuthenticated: () => !!get().token,
}));
