import { useState } from "react";
import { adminApi } from "@/lib/api";
import { AdminGuard } from "./AdminGuard";
import { AdminNav } from "./AdminNav";

export default function AdminExports() {
  const [exportId, setExportId] = useState("");
  const [cacheRunId, setCacheRunId] = useState("");
  const [cacheExportType, setCacheExportType] = useState("");
  const [reason, setReason] = useState("");
  const [message, setMessage] = useState("");

  return (
    <AdminGuard>
      <div className="admin-shell">
        <header className="workspace-header">
          <div>
            <p className="eyebrow">Ops</p>
            <h1>Exports</h1>
            <p className="muted">
              Unlock, revoke, and invalidate export caches with audit reasons.
            </p>
          </div>
        </header>
        <AdminNav />
        {message ? (
          <p className="status status-success" role="status">
            {message}
          </p>
        ) : null}
        <div className="panel">
          <p className="eyebrow">Access</p>
          <h2 style={{ marginTop: 0 }}>Unlock / revoke</h2>
          <div className="toolbar">
            <label className="field" style={{ flex: "1 1 12rem" }}>
              Audit reason
              <input
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                placeholder="Required for mutations"
              />
            </label>
            <label className="field" style={{ flex: "1 1 10rem" }}>
              Export ID
              <input
                value={exportId}
                onChange={(e) => setExportId(e.target.value)}
                placeholder="Numeric ID"
              />
            </label>
            <button
              type="button"
              className="button button-primary"
              onClick={async () => {
                if (!exportId) return;
                await adminApi.unlockExport(Number(exportId), reason || "unlock");
                setMessage(`Unlocked export ${exportId}`);
              }}
            >
              Unlock
            </button>
            <button
              type="button"
              className="button button-secondary"
              onClick={async () => {
                if (!exportId) return;
                await adminApi.revokeExport(Number(exportId), reason || "revoke");
                setMessage(`Revoked export ${exportId}`);
              }}
            >
              Revoke
            </button>
          </div>
        </div>
        <div className="panel">
          <p className="eyebrow">Cache</p>
          <h2 style={{ marginTop: 0 }}>Invalidate</h2>
          <div className="toolbar">
            <label className="field" style={{ flex: "1 1 8rem" }}>
              Run ID
              <input
                value={cacheRunId}
                onChange={(e) => setCacheRunId(e.target.value)}
                placeholder="Optional"
              />
            </label>
            <label className="field" style={{ flex: "1 1 10rem" }}>
              Export type
              <input
                value={cacheExportType}
                onChange={(e) => setCacheExportType(e.target.value)}
                placeholder="Optional"
              />
            </label>
            <button
              type="button"
              className="button button-secondary"
              onClick={async () => {
                await adminApi.invalidateCache({
                  run_id: cacheRunId ? Number(cacheRunId) : undefined,
                  export_type: cacheExportType || undefined,
                  reason: reason || "cache invalidate",
                });
                setMessage("Cache invalidation requested");
              }}
            >
              Invalidate
            </button>
          </div>
        </div>
      </div>
    </AdminGuard>
  );
}
