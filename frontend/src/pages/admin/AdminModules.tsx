import { useEffect, useState } from "react";
import { adminApi, moduleApi } from "@/lib/api";
import type { Module } from "@/types/api";
import { AdminGuard } from "./AdminGuard";
import { AdminNav } from "./AdminNav";

const STATUS_OPTIONS = ["active", "deprecated", "tombstoned"];

export default function AdminModules() {
  const [modules, setModules] = useState<Module[]>([]);
  const [reason, setReason] = useState("");
  const [mergeTarget, setMergeTarget] = useState<Record<number, number>>({});

  const fetchModules = async () => {
    const response = await moduleApi.list({ limit: 50 });
    setModules(response.data.modules);
  };

  useEffect(() => {
    void fetchModules();
  }, []);

  return (
    <AdminGuard>
      <div className="admin-shell">
        <header className="workspace-header">
          <div>
            <p className="eyebrow">Ops</p>
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
        <div className="catalog-grid">
          {modules.map((module) => (
            <article key={module.id} className="catalog-card">
              <h2>
                {module.brand} — {module.name}
              </h2>
              <p className="catalog-card-meta">Status: {module.status || "active"}</p>
              <div className="toolbar">
                <label className="inline-field">
                  Status
                  <select
                    onChange={async (e) => {
                      await adminApi.updateModuleStatus(
                        module.id,
                        e.target.value,
                        reason || "status update",
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
                <label className="inline-field">
                  Replacement ID
                  <input
                    type="number"
                    placeholder="ID"
                    value={mergeTarget[module.id] || ""}
                    onChange={(e) =>
                      setMergeTarget((prev) => ({
                        ...prev,
                        [module.id]: Number(e.target.value),
                      }))
                    }
                    style={{ width: "7rem" }}
                  />
                </label>
                <button
                  type="button"
                  className="button button-secondary"
                  onClick={async () => {
                    const replacementId = mergeTarget[module.id];
                    if (!replacementId) return;
                    await adminApi.mergeModule(module.id, replacementId, reason || "merge");
                    void fetchModules();
                  }}
                >
                  Merge
                </button>
              </div>
            </article>
          ))}
        </div>
      </div>
    </AdminGuard>
  );
}
