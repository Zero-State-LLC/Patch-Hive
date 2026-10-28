/**
 * Global state management using Zustand.
 *
 * The access token lives only in memory: script injected into the page cannot lift it
 * from storage, and it expires in minutes. The session survives reloads through the
 * API's HttpOnly refresh cookie (see lib/session.ts).
 */
import { create } from "zustand";
import type { User } from "@/types/api";

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

  setAuth: (user, token) => set({ user, token }),

  setUser: (user) => set({ user }),

  clear: () => set({ user: null, token: null }),

  isAuthenticated: () => !!get().token,
}));
