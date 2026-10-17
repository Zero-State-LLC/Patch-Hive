/**
 * Global state management using Zustand.
 */
import { create } from "zustand";
import type { User } from "@/types/api";

interface AuthState {
  user: User | null;
  token: string | null;
  setAuth: (user: User, token: string) => void;
  logout: () => void;
  isAuthenticated: () => boolean;
}

export const useAuthStore = create<AuthState>((set, get) => ({
  user: null,
  token: localStorage.getItem("auth_token"),

  setAuth: (user, token) => {
    localStorage.setItem("auth_token", token);
    set({ user, token });
  },

  logout: () => {
    localStorage.removeItem("auth_token");
    set({ user: null, token: null });
  },

  isAuthenticated: () => {
    return !!get().token;
  },
}));
