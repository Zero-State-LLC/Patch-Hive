import { useEffect, useState } from "react";
import { adminApi } from "@/lib/api";
import type { AdminRun } from "@/types/admin";
import { AdminGuard } from "./AdminGuard";
import { AdminNav } from "./AdminNav";

export default function AdminRuns() {
  const [runs, setRuns] = useState<AdminRun[]>([]);
  const [rerunRigId, setRerunRigId] = useState("");
  const [rerunError, setRerunError] = useState("");

  const fetchRuns = async () => {
    const response = await adminApi.listRuns();
    setRuns(response.data.runs);
  };

  useEffect(() => {
    void fetchRuns();
  }, []);

  return (
    <AdminGuard>
      <div className="admin-shell">
        <header className="workspace-header">
          <div>
            <h1>Runs</h1>
            <p className="muted">Generation runs bound to rig revisions and seeds.</p>
          </div>
          <button
            className="button button-secondary"
            type="button"
            onClick={() => void fetchRuns()}
          >
            Refresh
          </button>
        </header>
        <AdminNav />
        <div className="panel toolbar">
          <label className="field" style={{ flex: "1 1 12rem" }}>
            Rig ID to re-run
            <input
              value={rerunRigId}
              onChange={(e) => setRerunRigId(e.target.value)}
              placeholder="Numeric rig ID"
            />
          </label>
          <button
            type="button"
            className="button button-primary"
            onClick={async () => {
              if (!rerunRigId) return;
              setRerunError("");
              try {
                await adminApi.rerunRig(Number(rerunRigId));
                setRerunRigId("");
              } catch (err: unknown) {
                const detail = (err as { response?: { data?: { detail?: unknown } } }).response
                  ?.data?.detail;
                const code =
                  typeof detail === "string"
                    ? detail
                    : ((detail as { inventory_gate_code?: string; code?: string } | undefined)
                        ?.inventory_gate_code ?? (detail as { code?: string } | undefined)?.code);
                setRerunError(code ? `Rerun refused: ${code}` : "Rerun failed");
              }
              void fetchRuns();
            }}
          >
            Rerun
          </button>
        </div>
        {rerunError ? (
          <p className="status status-danger" role="alert">
            {rerunError}
          </p>
        ) : null}
        {runs.length ? (
          <div style={{ overflowX: "auto" }} className="panel">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Run</th>
                  <th>Rack</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {runs.map((run) => (
                  <tr key={run.id}>
                    <td>#{run.id}</td>
                    <td>{run.rack_id}</td>
                    <td>{run.status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="panel">
            <p className="status status-warning">No runs loaded.</p>
          </div>
        )}
      </div>
    </AdminGuard>
  );
}
