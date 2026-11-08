import { useEffect, useState } from "react";
import LoadFailure from "@/components/LoadFailure";
import { ListSkeleton } from "@/components/Skeletons";
import { adminApi } from "@/lib/api";
import type { AdminRun } from "@/types/admin";
import { AdminGuard } from "./AdminGuard";
import { AdminNav } from "./AdminNav";

export default function AdminRuns() {
  const [runs, setRuns] = useState<AdminRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<unknown>(null);
  const [rerunRigId, setRerunRigId] = useState("");
  const [rerunError, setRerunError] = useState("");
  const [rerunning, setRerunning] = useState(false);

  const fetchRuns = async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const response = await adminApi.listRuns();
      setRuns(response.data.runs);
    } catch (err: unknown) {
      setRuns([]);
      setLoadError(err);
    } finally {
      setLoading(false);
    }
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
            disabled={loading}
          >
            Refresh
          </button>
        </header>
        <AdminNav />
        <div className="toolbar ops-toolbar">
          <label className="field ops-grow">
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
            disabled={rerunning}
            onClick={async () => {
              if (!rerunRigId) return;
              setRerunError("");
              setRerunning(true);
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
              } finally {
                setRerunning(false);
              }
              void fetchRuns();
            }}
          >
            {rerunning ? "Rerunning…" : "Rerun"}
          </button>
        </div>
        {rerunError ? (
          <p className="status status-danger" role="alert">
            {rerunError}
          </p>
        ) : null}
        {loading && !runs.length ? (
          <ListSkeleton label="Loading runs…" rows={3} />
        ) : loadError ? (
          <LoadFailure what="The run list" error={loadError} onRetry={() => void fetchRuns()} />
        ) : runs.length ? (
          <div className="ops-table-wrap">
            <table className="data-table ops-table-stack">
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
                    <td data-label="Run">#{run.id}</td>
                    <td data-label="Rack">{run.rack_id}</td>
                    <td data-label="Status">{run.status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="screen-state">
            <p className="status status-warning">No runs loaded.</p>
          </div>
        )}
      </div>
    </AdminGuard>
  );
}
