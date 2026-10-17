import { useEffect, useState } from "react";
import { adminApi } from "@/lib/api";
import type { AdminUser } from "@/types/admin";
import { AdminGuard } from "./AdminGuard";
import { AdminNav } from "./AdminNav";

const ROLE_OPTIONS = ["Admin", "Ops", "Support", "ReadOnly", "User"];

export default function AdminUsers() {
  const [query, setQuery] = useState("");
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [reasonByUser, setReasonByUser] = useState<Record<number, string>>({});

  const fetchUsers = async () => {
    const response = await adminApi.listUsers(query || undefined);
    setUsers(response.data.users);
  };

  useEffect(() => {
    void fetchUsers();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <AdminGuard>
      <div className="admin-shell">
        <header className="workspace-header">
          <div>
            <p className="eyebrow">Ops</p>
            <h1>Users</h1>
            <p className="muted">Role changes and credit grants require an audit reason.</p>
          </div>
        </header>
        <AdminNav />
        <div className="panel toolbar" style={{ marginBottom: 0 }}>
          <label className="field" style={{ flex: "1 1 14rem" }}>
            Search
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Username or email"
            />
          </label>
          <button
            className="button button-secondary"
            type="button"
            onClick={() => void fetchUsers()}
          >
            Search
          </button>
        </div>
        <div className="catalog-grid">
          {users.map((user) => (
            <article key={user.id} className="catalog-card">
              <h2>{user.username}</h2>
              <p className="catalog-card-meta">{user.email}</p>
              <p className="muted" style={{ margin: 0, fontSize: "0.9rem" }}>
                Role: {user.role} · Display: {user.display_name || "—"}
              </p>
              <label className="field">
                Audit reason
                <input
                  value={reasonByUser[user.id] || ""}
                  onChange={(e) =>
                    setReasonByUser((prev) => ({ ...prev, [user.id]: e.target.value }))
                  }
                  placeholder="Required for mutations"
                />
              </label>
              <div className="toolbar">
                <label className="inline-field">
                  Role
                  <select
                    value={user.role}
                    onChange={async (e) => {
                      const reason = reasonByUser[user.id] || "role update";
                      await adminApi.updateUserRole(user.id, e.target.value, reason);
                      void fetchUsers();
                    }}
                  >
                    {ROLE_OPTIONS.map((role) => (
                      <option key={role} value={role}>
                        {role}
                      </option>
                    ))}
                  </select>
                </label>
                <button
                  type="button"
                  className="button button-primary"
                  onClick={async () => {
                    const reason = reasonByUser[user.id] || "grant credits";
                    await adminApi.grantCredits(user.id, 3, reason);
                    void fetchUsers();
                  }}
                >
                  Grant 3 credits
                </button>
                <button
                  type="button"
                  className="button button-quiet"
                  onClick={async () => {
                    const reason = reasonByUser[user.id] || "clear avatar";
                    await adminApi.updateUserAvatar(user.id, null, reason);
                    void fetchUsers();
                  }}
                >
                  Clear avatar
                </button>
              </div>
            </article>
          ))}
        </div>
        {users.length === 0 ? (
          <div className="panel">
            <p className="status status-warning">No users match this search.</p>
          </div>
        ) : null}
      </div>
    </AdminGuard>
  );
}
