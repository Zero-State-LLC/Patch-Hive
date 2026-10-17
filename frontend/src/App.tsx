import { useState } from "react";
import { BrowserRouter, NavLink, Route, Routes } from "react-router-dom";
import { useAuthStore } from "@/lib/store";
import AccountPage from "@/pages/Account";
import AdminDashboard from "@/pages/admin/AdminDashboard";
import AdminExports from "@/pages/admin/AdminExports";
import AdminGallery from "@/pages/admin/AdminGallery";
import AdminModules from "@/pages/admin/AdminModules";
import AdminRuns from "@/pages/admin/AdminRuns";
import AdminUsers from "@/pages/admin/AdminUsers";
import CaseDetailPage from "@/pages/CaseDetail";
import CasesPage from "@/pages/Cases";
import Home from "@/pages/Home";
import LoginPage from "@/pages/Login";
import ModulesPage from "@/pages/Modules";
import NotFoundPage from "@/pages/NotFound";
import PatchesPage from "@/pages/Patches";
import RackBuilderPage from "@/pages/RackBuilder";
import RacksPage from "@/pages/Racks";
import RigDetailPage from "@/pages/RigDetail";
import PatchBookStyleStudioPage from "@/pages/PatchBookStyleStudio";
import RegistryPage from "@/pages/Registry";

type Theme = "dark" | "light";

function App() {
  const { user, logout, isAuthenticated } = useAuthStore();
  const [theme, setTheme] = useState<Theme>("dark");
  const canSeeAdmin = user && ["Admin", "Ops", "Support", "ReadOnly"].includes(user.role);

  return (
    <BrowserRouter>
      <div className="app-shell" data-theme={theme}>
        <a className="skip-link" href="#main-content">
          Skip to workspace
        </a>
        <header className="app-header">
          <NavLink className="wordmark" to="/" aria-label="PatchHive home">
            <span aria-hidden="true" className="wordmark-mark" />
            <span>PatchHive</span>
          </NavLink>
          <nav className="primary-nav" aria-label="Primary navigation">
            <NavLink to="/racks">Rigs</NavLink>
            <NavLink to="/modules">Modules</NavLink>
            <NavLink to="/products">Products</NavLink>
            <NavLink to="/cases">Cases</NavLink>
            <NavLink to="/patches">Patches</NavLink>
            {isAuthenticated() && <NavLink to="/account">Account</NavLink>}
            {canSeeAdmin ? <NavLink to="/admin">Ops</NavLink> : null}
          </nav>
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
              <button className="button button-secondary" type="button" onClick={logout}>
                Sign out {user?.username}
              </button>
            ) : (
              <NavLink className="button button-primary" to="/login">
                Sign in
              </NavLink>
            )}
          </div>
        </header>

        <main id="main-content" className="workspace" tabIndex={-1}>
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/modules" element={<ModulesPage />} />
            <Route path="/cases" element={<CasesPage />} />
            <Route path="/cases/:slug" element={<CaseDetailPage />} />
            <Route path="/racks" element={<RacksPage />} />
            <Route path="/racks/new" element={<RackBuilderPage />} />
            <Route path="/racks/:id/edit" element={<RackBuilderPage />} />
            <Route path="/rigs/:rigId" element={<RigDetailPage />} />
            <Route path="/rigs/:rigId/patchbook-studio" element={<PatchBookStyleStudioPage />} />
            <Route path="/patches" element={<PatchesPage />} />
            <Route path="/products" element={<RegistryPage />} />
            <Route path="/login" element={<LoginPage />} />
            <Route path="/account" element={<AccountPage />} />
            <Route path="/admin" element={<AdminDashboard />} />
            <Route path="/admin/users" element={<AdminUsers />} />
            <Route path="/admin/modules" element={<AdminModules />} />
            <Route path="/admin/gallery" element={<AdminGallery />} />
            <Route path="/admin/runs" element={<AdminRuns />} />
            <Route path="/admin/exports" element={<AdminExports />} />
            <Route path="*" element={<NotFoundPage />} />
          </Routes>
        </main>

        <footer className="app-footer">
          Canonical rig revisions · deterministic runs · exports are the credit boundary
          <span className="zero-state-credit">Designed and engineered by Zero State</span>
        </footer>
      </div>
    </BrowserRouter>
  );
}

export default App;
