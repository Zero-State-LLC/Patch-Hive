import { useEffect, useState } from "react";
import { adminApi } from "@/lib/api";
import type { AdminGalleryRevision } from "@/types/admin";
import { AdminGuard } from "./AdminGuard";
import { AdminNav } from "./AdminNav";

export default function AdminGallery() {
  const [revisions, setRevisions] = useState<AdminGalleryRevision[]>([]);

  const fetchRevisions = async () => {
    const response = await adminApi.listGalleryRevisions();
    setRevisions(response.data.revisions);
  };

  useEffect(() => {
    void fetchRevisions();
  }, []);

  return (
    <AdminGuard>
      <div className="admin-shell">
        <header className="workspace-header">
          <div>
            <h1>Gallery revisions</h1>
            <p className="muted">Approve or confirm gallery inventory evidence.</p>
          </div>
          <button
            className="button button-secondary"
            type="button"
            onClick={() => void fetchRevisions()}
          >
            Refresh
          </button>
        </header>
        <AdminNav />
        {revisions.length ? (
          <div className="ops-table-wrap">
            <table className="data-table ops-table-stack">
              <thead>
                <tr>
                  <th>Module</th>
                  <th>Revision</th>
                  <th>Status</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {revisions.map((revision) => (
                  <tr key={revision.id}>
                    <td data-label="Module">{revision.module_key}</td>
                    <td data-label="Revision" className="muted ops-id">
                      {revision.revision_id}
                    </td>
                    <td data-label="Status">{revision.status}</td>
                    <td data-label="Actions">
                      <div className="page-hero-actions">
                        <button
                          type="button"
                          className="button button-primary"
                          onClick={async () => {
                            await adminApi.approveRevision(revision.id);
                            void fetchRevisions();
                          }}
                        >
                          Approve
                        </button>
                        <button
                          type="button"
                          className="button button-secondary"
                          onClick={async () => {
                            await adminApi.confirmRevision(revision.id);
                            void fetchRevisions();
                          }}
                        >
                          Confirm
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="screen-state">
            <p className="status status-warning">No gallery revisions loaded.</p>
          </div>
        )}
      </div>
    </AdminGuard>
  );
}
