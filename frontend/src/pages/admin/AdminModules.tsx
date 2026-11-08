import { useEffect, useState } from "react";
import LoadFailure from "@/components/LoadFailure";
import { ListSkeleton } from "@/components/Skeletons";
import { adminApi, moduleApi } from "@/lib/api";
import type { Module } from "@/types/api";
import { AdminGuard } from "./AdminGuard";
import { AdminNav } from "./AdminNav";
import { useAdminChange } from "./useAdminChange";

const STATUS_OPTIONS = ["active", "deprecated", "tombstoned"];

export default function AdminModules() {
  const [modules, setModules] = useState<Module[]>([]);
  const [reason, setReason] = useState("");
  const [mergeTarget, setMergeTarget] = useState<Record<number, number>>({});
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<unknown>(null);
  const { busy, failure, run } = useAdminChange();

  const fetchModules = async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const response = await moduleApi.list({ limit: 50 });
      setModules(response.data.modules);
    } catch (err: unknown) {
      setModules([]);
      setLoadError(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void fetchModules();
  }, []);

  return (
    <AdminGuard>
      <div className="admin-shell">
        <header className="workspace-header">
          <div>
            <h1>Modules</h1>
            <p className="muted">
              Deprecate, tombstone, or merge catalog modules. No hard deletes.
            </p>
          </div>
        </header>
        <AdminNav />
        <div className="panel">
          <label className="field">
            Audit reason (shared)
            <input
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="Required for mutations"
            />
          </label>
        </div>
        {failure ? (
          <p className="status status-danger" role="alert">
            {failure}
          </p>
        ) : null}
        {loading && !modules.length ? (
          <ListSkeleton label="Loading modules…" rows={3} />
        ) : loadError ? (
          <LoadFailure
            what="The module list"
            error={loadError}
            onRetry={() => void fetchModules()}
          />
        ) : modules.length ? (
          <div className="ops-table-wrap">
            <table className="data-table ops-table-stack">
              <thead>
                <tr>
                  <th>Module</th>
                  <th>Status</th>
                  <th>Change status</th>
                  <th>Replacement ID</th>
                  <th>Merge</th>
                </tr>
              </thead>
              <tbody>
                {modules.map((module) => (
                  <tr key={module.id}>
                    <td data-label="Module">
                      {module.brand} {module.name}
                    </td>
                    <td data-label="Status">{module.status || "active"}</td>
                    <td data-label="Change status">
                      <label className="inline-field">
                        <span className="visually-hidden">Status</span>
                        <select
                          disabled={busy}
                          onChange={async (e) => {
                            const status = e.target.value;
                            await run(() =>
                              adminApi.updateModuleStatus(
                                module.id,
                                status,
                                reason || "status update",
                              ),
                            );
                            void fetchModules();
                          }}
                          defaultValue={module.status || "active"}
                        >
                          {STATUS_OPTIONS.map((status) => (
                            <option key={status} value={status}>
                              {status}
                            </option>
                          ))}
                        </select>
                      </label>
                    </td>
                    <td data-label="Replacement ID">
                      <label className="inline-field">
                        <span className="visually-hidden">Replacement ID</span>
                        <input
                          className="ops-id-input"
                          type="number"
                          placeholder="ID"
                          value={mergeTarget[module.id] || ""}
                          onChange={(e) =>
                            setMergeTarget((prev) => ({
                              ...prev,
                              [module.id]: Number(e.target.value),
                            }))
                          }
                        />
                      </label>
                    </td>
                    <td data-label="Merge">
                      <button
                        type="button"
                        className="button button-secondary"
                        disabled={busy}
                        onClick={async () => {
                          const replacementId = mergeTarget[module.id];
                          if (!replacementId) return;
                          await run(() =>
                            adminApi.mergeModule(module.id, replacementId, reason || "merge"),
                          );
                          void fetchModules();
                        }}
                      >
                        Merge
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </div>
    </AdminGuard>
  );
}
