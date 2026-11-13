import { lazy, Suspense, useEffect, useState } from "react";
import { BrowserRouter, Navigate, NavLink, Route, Routes, useLocation } from "react-router-dom";
import { RouteErrorBoundary } from "@/components/ErrorBoundary";
import PrimaryNav from "@/components/PrimaryNav";
import RouteEffects from "@/components/RouteEffects";
import { ListSkeleton } from "@/components/Skeletons";
import { restoreSession, signOut } from "@/lib/session";
import { sessionHint, useAuthStore } from "@/lib/store";
import Home from "@/pages/Home";
import LoginPage from "@/pages/Login";
import NotFoundPage from "@/pages/NotFound";
import PatchesPage from "@/pages/Patches";
import RacksPage from "@/pages/Racks";
import RigDetailPage from "@/pages/RigDetail";
import { ACCOUNTS_OPEN } from "@/lib/apiBase";

// Screens most visits never open load on demand, keeping them out of the first download.
const AccountPage = lazy(() => import("@/pages/Account"));
const AdminDashboard = lazy(() => import("@/pages/admin/AdminDashboard"));
const AdminExports = lazy(() => import("@/pages/admin/AdminExports"));
const AdminGallery = lazy(() => import("@/pages/admin/AdminGallery"));
const AdminInvites = lazy(() => import("@/pages/admin/AdminInvites"));
const AdminLeaderboards = lazy(() => import("@/pages/admin/AdminLeaderboards"));
const AdminModules = lazy(() => import("@/pages/admin/AdminModules"));
const AdminRuns = lazy(() => import("@/pages/admin/AdminRuns"));
const AdminUsers = lazy(() => import("@/pages/admin/AdminUsers"));
const PatchBookStyleStudioPage = lazy(() => import("@/pages/PatchBookStyleStudio"));
const PatchDetailPage = lazy(() => import("@/pages/PatchDetail"));
const PrivacyPage = lazy(() => import("@/pages/Privacy"));
const RackBuilderPage = lazy(() => import("@/pages/RackBuilder"));
const RigPhotoPage = lazy(() => import("@/pages/RigPhoto"));
const RigReadingPage = lazy(() => import("@/pages/RigReading"));

type Theme = "dark" | "light";

const THEME_KEY = "patchhive-theme";
/** The browser chrome colour per theme: each theme's --color-paper (styles/tokens.css). */
const THEME_COLOR: Record<Theme, string> = { dark: "#08090b", light: "#e9ebef" };

/** Every screen. The edge worker mirrors these paths (worker/routes.ts), and its test reads them here. */
function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<Home />} />
      {/* The catalog pages left the public routes (spec 009, decision 58); old links go home. */}
      <Route path="/modules" element={<Navigate to="/" replace />} />
      <Route path="/products" element={<Navigate to="/" replace />} />
      <Route path="/cases" element={<Navigate to="/" replace />} />
      <Route path="/cases/:slug" element={<Navigate to="/" replace />} />
      <Route path="/racks" element={<RacksPage />} />
      <Route path="/racks/new" element={<RackBuilderPage />} />
      <Route path="/racks/:id/edit" element={<RackBuilderPage />} />
      <Route path="/racks/:rigId" element={<RacksPage />} />
      <Route path="/rigs/new/photo" element={<RigPhotoPage />} />
      <Route path="/rigs/:rigId/photo" element={<RigPhotoPage />} />
      <Route path="/rigs/:rigId/reading" element={<RigReadingPage />} />
      <Route path="/rigs/:rigId" element={<RigDetailPage />} />
      <Route path="/rigs/:rigId/patchbook-studio" element={<PatchBookStyleStudioPage />} />
      <Route path="/rigs/:rigId/patches/:patchId" element={<PatchDetailPage />} />
      <Route path="/patches" element={<PatchesPage />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/account" element={<AccountPage />} />
      <Route path="/privacy" element={<PrivacyPage />} />
      <Route path="/admin" element={<AdminDashboard />} />
      <Route path="/admin/users" element={<AdminUsers />} />
      <Route path="/admin/invites" element={<AdminInvites />} />
      <Route path="/admin/modules" element={<AdminModules />} />
      <Route path="/admin/gallery" element={<AdminGallery />} />
      <Route path="/admin/runs" element={<AdminRuns />} />
      <Route path="/admin/exports" element={<AdminExports />} />
      <Route path="/admin/leaderboards" element={<AdminLeaderboards />} />
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}

/** Sign in, remembering the screen to come back to. */
function SignInLink() {
  const { pathname } = useLocation();
  return (
    <NavLink
      className="button button-primary"
      to="/login"
      state={pathname === "/login" ? undefined : { from: pathname }}
    >
      Sign in
    </NavLink>
  );
}

/** Dark is the default; a remembered choice wins (public/theme-init.js applies it before paint). */
function initialTheme(): Theme {
  try {
    return window.localStorage.getItem(THEME_KEY) === "light" ? "light" : "dark";
  } catch {
    return "dark";
  }
}

function App() {
  const { user, isAuthenticated } = useAuthStore();
  // A visitor known to be signed out has nothing to restore, so never makes them wait.
  const [sessionSettled, setSessionSettled] = useState(
    () => !ACCOUNTS_OPEN || sessionHint() === "0",
  );
  // Restore the session from the API's refresh cookie after a reload. Child effects run
  // before this one, so pages must not mount until it settles or they fetch signed out.
  useEffect(() => {
    if (ACCOUNTS_OPEN) void restoreSession().finally(() => setSessionSettled(true));
  }, []);
  const [theme, setTheme] = useState<Theme>(initialTheme);
  // Mirror the theme onto <html> so the page behind the shell, form controls and the browser
  // chrome follow it, and remember the choice.
  useEffect(() => {
    const root = document.documentElement;
    root.dataset.theme = theme;
    root.style.colorScheme = theme;
    document.querySelector('meta[name="theme-color"]')?.setAttribute("content", THEME_COLOR[theme]);
    try {
      window.localStorage.setItem(THEME_KEY, theme);
    } catch {
      /* the choice just isn't remembered */
    }
  }, [theme]);
  // Another open tab changed the theme: follow it.
  useEffect(() => {
    const follow = (event: StorageEvent) => {
      if (event.key === THEME_KEY) setTheme(event.newValue === "light" ? "light" : "dark");
    };
    window.addEventListener("storage", follow);
    return () => window.removeEventListener("storage", follow);
  }, []);
  const canSeeAdmin = user && ["Admin", "Ops", "Support", "ReadOnly"].includes(user.role);

  return (
    <BrowserRouter>
      <RouteEffects />
      <div className="app-shell" data-theme={theme}>
        <a className="skip-link" href="#main-content">
          Skip to workspace
        </a>
        <header className="app-header">
          <NavLink className="wordmark" to="/" aria-label="PatchHive home">
            <span aria-hidden="true" className="wordmark-mark" />
            <span>PatchHive</span>
          </NavLink>
          <PrimaryNav signedIn={isAuthenticated()} canSeeAdmin={Boolean(canSeeAdmin)} />
          <div className="header-actions">
            <button
              className="button button-quiet"
              type="button"
              onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
              aria-label={`Use ${theme === "dark" ? "light" : "dark"} theme`}
            >
              {theme === "dark" ? "Light" : "Dark"}
            </button>
            {isAuthenticated() ? (
              <button
                className="button button-secondary"
                type="button"
                onClick={() => void signOut()}
              >
                Sign out {user?.username}
              </button>
            ) : ACCOUNTS_OPEN ? (
              <SignInLink />
            ) : null}
          </div>
        </header>

        <main id="main-content" className="workspace" tabIndex={-1}>
          {sessionSettled ? (
            <RouteErrorBoundary>
              <Suspense fallback={<ListSkeleton label="Loading this screen" />}>
                <AppRoutes />
              </Suspense>
            </RouteErrorBoundary>
          ) : (
            <p className="muted" role="status">
              Restoring session…
            </p>
          )}
        </main>

        <footer className="app-footer">
          <span>
            Canonical rig revisions and deterministic runs. Exports are the credit boundary.
          </span>
          <NavLink to="/privacy">Privacy notice</NavLink>
          <span className="zero-state-credit">Designed and engineered by Zero State</span>
        </footer>
      </div>
    </BrowserRouter>
  );
}

export default App;
