// Session renewal: the API keeps a rotating refresh token in an HttpOnly cookie on its
// own host; these calls trade it for a short-lived access token held in memory.
import axios from "axios";
import type { TokenResponse } from "@/types/api";
import { API_BASE_URL } from "./apiBase";
import { useAuthStore } from "./store";

// Cookie-authenticated calls must carry this header; a cross-site form cannot set it.
export const SESSION_HEADER = { "X-PatchHive-Session": "1" };

let inFlight: Promise<string | null> | null = null;

/** Renew the access token from the refresh cookie. Concurrent callers share one request. */
export function refreshSession(): Promise<string | null> {
  if (!API_BASE_URL) return Promise.resolve(null);
  inFlight ??= axios
    .post<TokenResponse>(`${API_BASE_URL}/community/auth/refresh`, null, {
      withCredentials: true,
      headers: SESSION_HEADER,
    })
    .then((res) => {
      useAuthStore.getState().setAuth(res.data.user, res.data.access_token);
      return res.data.access_token;
    })
    .catch(() => {
      useAuthStore.getState().clear();
      return null;
    })
    .finally(() => {
      inFlight = null;
    });
  return inFlight;
}

/** Sign out this browser: the API revokes the refresh cookie, and memory is cleared. */
export async function signOut(): Promise<void> {
  try {
    if (API_BASE_URL) {
      await axios.post(`${API_BASE_URL}/community/auth/logout`, null, {
        withCredentials: true,
        headers: SESSION_HEADER,
      });
    }
  } finally {
    useAuthStore.getState().clear();
  }
}
