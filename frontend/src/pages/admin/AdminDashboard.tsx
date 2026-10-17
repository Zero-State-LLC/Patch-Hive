import { Link } from "react-router-dom";
import { AdminGuard } from "./AdminGuard";
import { AdminNav } from "./AdminNav";

const areas = [
  {
    title: "Users",
    description: "Roles, credit grants, and profile maintenance. Mutations are audited.",
    to: "/admin/users",
  },
  {
    title: "Modules",
    description: "Deprecate, tombstone, or merge catalog modules. No hard deletes.",
    to: "/admin/modules",
  },
  {
    title: "Gallery",
    description: "Inspect gallery revisions and inventory evidence state.",
    to: "/admin/gallery",
  },
  {
    title: "Runs",
    description: "Browse generation runs bound to rig revisions and seeds.",
    to: "/admin/runs",
  },
  {
    title: "Exports",
    description: "Canonical export ledger and fulfillment status.",
    to: "/admin/exports",
  },
  {
    title: "Leaderboards",
    description: "Community ranking surfaces when feature flags allow.",
    to: "/admin/leaderboards",
  },
] as const;

export default function AdminDashboard() {
  return (
    <AdminGuard>
      <div className="admin-shell">
        <header className="workspace-header">
          <div>
            <p className="eyebrow">Ops</p>
            <h1>Admin console</h1>
            <p className="muted">
              Manage users, catalog, gallery revisions, runs, exports, and leaderboards. All
              mutations append audit rows; credits only move through the ledger.
            </p>
          </div>
        </header>
        <AdminNav />
        <div className="panel">
          <p className="eyebrow">Guardrails</p>
          <ul className="auth-brand-list" style={{ marginTop: "var(--space-3)" }}>
            <li>All admin mutations are audited</li>
            <li>Credit changes append to the canonical ledger</li>
            <li>Modules are deprecated or tombstoned (no hard deletes)</li>
          </ul>
        </div>
        <ul className="ops-link-list">
          {areas.map((area) => (
            <li key={area.to}>
              <div>
                <h2>{area.title}</h2>
                <p>{area.description}</p>
              </div>
              <Link className="button button-secondary" to={area.to}>
                Open
              </Link>
            </li>
          ))}
        </ul>
      </div>
    </AdminGuard>
  );
}
