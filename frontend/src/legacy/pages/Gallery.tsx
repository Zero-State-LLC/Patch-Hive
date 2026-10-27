import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { publishingApi } from "@/legacy/apiClients";
import type { PublicationCard } from "@/types/api";

export default function GalleryPage() {
  const [publications, setPublications] = useState<PublicationCard[]>([]);
  const [exportType, setExportType] = useState<string>("");
  const [loading, setLoading] = useState(true);

  const fetchGallery = async () => {
    setLoading(true);
    const response = await publishingApi.listGallery({ export_type: exportType || undefined });
    setPublications(response.data.publications);
    setLoading(false);
  };

  useEffect(() => {
    fetchGallery();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [exportType]);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
      <header style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <h2 style={{ margin: 0 }}>Gallery</h2>
          <p style={{ color: "var(--text-muted)" }}>Public publications, sorted by recency.</p>
        </div>
        <label style={{ color: "var(--text-secondary)" }}>
          Export type
          <select
            value={exportType}
            onChange={(event) => setExportType(event.target.value)}
            style={{
              marginLeft: "0.5rem",
              background: "var(--surface-inset)",
              color: "var(--text-primary)",
              border: "1px solid var(--border)",
              borderRadius: "4px",
              padding: "0.3rem 0.6rem",
            }}
          >
            <option value="">All</option>
            <option value="patch">Patch</option>
            <option value="rack">Rack</option>
          </select>
        </label>
      </header>

      {loading && <p>Loading gallery...</p>}
      {!loading && publications.length === 0 && (
        <p style={{ color: "var(--text-muted)" }}>No public publications yet.</p>
      )}

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))",
          gap: "1rem",
        }}
      >
        {publications.map((publication) => (
          <Link
            to={`/p/${publication.slug}`}
            key={publication.slug}
            style={{
              background: "var(--surface-panel)",
              border: "1px solid var(--surface-raised)",
              borderRadius: "8px",
              padding: "1rem",
              color: "var(--text-primary)",
              textDecoration: "none",
            }}
          >
            <h3 style={{ marginTop: 0 }}>{publication.title}</h3>
            <p style={{ color: "var(--text-muted)" }}>{publication.description}</p>
            <p style={{ color: "var(--text-muted)", fontSize: "0.85rem" }}>
              {publication.export_type.toUpperCase()} export
            </p>
          </Link>
        ))}
      </div>
    </div>
  );
}
