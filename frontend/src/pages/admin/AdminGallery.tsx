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
            <p className="eyebrow">Ops</p>
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
        <div className="catalog-grid">
          {revisions.map((revision) => (
            <article key={revision.id} className="catalog-card">
              <h2>{revision.module_key}</h2>
              <p className="catalog-card-meta">{revision.revision_id}</p>
              <p className="muted" style={{ margin: 0 }}>
                Status: {revision.status}
              </p>
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
            </article>
          ))}
        </div>
        {revisions.length === 0 ? (
          <div className="panel">
            <p className="status status-warning">No gallery revisions loaded.</p>
          </div>
        ) : null}
      </div>
    </AdminGuard>
  );
}
