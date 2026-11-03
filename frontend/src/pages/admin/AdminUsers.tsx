import { useEffect, useState } from "react";
import LoadFailure from "@/components/LoadFailure";
import { adminApi } from "@/lib/api";
import type { AdminUser } from "@/types/admin";
import { AdminGuard } from "./AdminGuard";
import { AdminNav } from "./AdminNav";

const ROLE_OPTIONS = ["Admin", "Ops", "Support", "ReadOnly", "User"];

export default function AdminUsers() {
  const [query, setQuery] = useState("");
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [reasonByUser, setReasonByUser] = useState<Record<number, string>>({});
  const [loadError, setLoadError] = useState<unknown>(null);

  const fetchUsers = async () => {
    setLoadError(null);
    try {
      const response = await adminApi.listUsers(query || undefined);
      setUsers(response.data.users);
    } catch (err: unknown) {
      setUsers([]);
      setLoadError(err);
    }
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
            <h1>Users</h1>
            <p className="muted">Role changes and credit grants require an audit reason.</p>
          </div>
        </header>
        <AdminNav />
        <div className="toolbar ops-toolbar">
          <label className="field ops-grow">
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
        {users.length ? (
          <div className="ops-table-wrap">
            <table className="data-table ops-table-stack">
              <thead>
                <tr>
                  <th>User</th>
                  <th>Role</th>
                  <th>Display name</th>
                  <th>Audit reason</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {users.map((user) => (
                  <tr key={user.id}>
                    <td data-label="User">
                      <div className="ops-cell-stack">
                        <strong>{user.username}</strong>
                        <span className="muted">{user.email}</span>
                      </div>
                    </td>
                    <td data-label="Role">
                      <label className="inline-field">
                        <span className="visually-hidden">Role</span>
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
                    </td>
                    <td data-label="Display name">{user.display_name || "unknown"}</td>
                    <td data-label="Audit reason">
                      <label className="field">
                        <span className="visually-hidden">Audit reason</span>
                        <input
                          value={reasonByUser[user.id] || ""}
                          onChange={(e) =>
                            setReasonByUser((prev) => ({ ...prev, [user.id]: e.target.value }))
                          }
                          placeholder="Required for mutations"
                        />
                      </label>
                    </td>
                    <td data-label="Actions">
                      <div className="ops-cell-actions">
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
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : loadError ? (
          <LoadFailure what="The user list" error={loadError} onRetry={() => void fetchUsers()} />
        ) : (
          <div className="screen-state">
            <p className="status status-warning">No users match this search.</p>
          </div>
        )}
      </div>
    </AdminGuard>
  );
}
