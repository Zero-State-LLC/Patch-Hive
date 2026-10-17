import { useEffect, useState } from "react";
import { adminApi } from "@/lib/api";
import type { AdminRun } from "@/types/admin";
import { AdminGuard } from "./AdminGuard";
import { AdminNav } from "./AdminNav";

export default function AdminRuns() {
  const [runs, setRuns] = useState<AdminRun[]>([]);
  const [rerunRigId, setRerunRigId] = useState("");

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
            <p className="eyebrow">Ops</p>
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
              await adminApi.rerunRig(Number(rerunRigId));
              setRerunRigId("");
              void fetchRuns();
            }}
          >
            Rerun
          </button>
        </div>
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
