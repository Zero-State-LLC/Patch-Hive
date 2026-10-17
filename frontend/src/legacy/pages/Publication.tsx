import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { publishingApi } from "@/legacy/apiClients";
import type { PublicPublicationResponse } from "@/types/api";

export default function PublicationPage() {
  const { slug } = useParams();
  const [publication, setPublication] = useState<PublicPublicationResponse | null>(null);
  const [reportReason, setReportReason] = useState("");
  const [reportDetails, setReportDetails] = useState("");
  const [reportStatus, setReportStatus] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchPublication = async () => {
      if (!slug) return;
      setLoading(true);
      try {
        const response = await publishingApi.getPublication(slug);
        setPublication(response.data);
      } catch {
        setError("Publication not found.");
      } finally {
        setLoading(false);
      }
    };

    fetchPublication();
  }, [slug]);

  const submitReport = async () => {
    if (!slug || !reportReason) {
      setReportStatus("Add a reason to submit a report.");
      return;
    }
    try {
      await publishingApi.reportPublication(slug, {
        reason: reportReason,
        details: reportDetails || undefined,
      });
      setReportStatus("Report submitted.");
      setReportReason("");
      setReportDetails("");
    } catch {
      setReportStatus("Unable to submit report.");
    }
  };

  if (loading) {
    return <p>Loading publication...</p>;
  }

  if (error || !publication) {
    return <p>{error}</p>;
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "2rem" }}>
      <header
        style={{
          display: "flex",
          gap: "1.5rem",
          alignItems: "center",
          flexWrap: "wrap",
        }}
      >
        {publication.cover_image_url && (
          <img
            src={publication.cover_image_url}
            alt={publication.title}
            style={{ width: "200px", borderRadius: "8px", border: "1px solid #222" }}
          />
        )}
        <div>
          <h2 style={{ marginTop: 0 }}>{publication.title}</h2>
          <p style={{ color: "#aaa" }}>{publication.description}</p>
          <p style={{ color: "#666" }}>Published by {publication.publisher_display}</p>
          <span
            style={{
              background: "#222",
              color: "#00ff88",
              padding: "0.2rem 0.6rem",
              borderRadius: "999px",
              fontSize: "0.85rem",
            }}
          >
            {publication.license}
          </span>
        </div>
      </header>

      <section
        style={{
          background: "#111",
          border: "1px solid #222",
          borderRadius: "8px",
          padding: "1.5rem",
        }}
      >
        <h3 style={{ marginTop: 0 }}>Provenance</h3>
        <ul style={{ listStyle: "none", padding: 0, margin: 0, color: "#ccc" }}>
          <li>Run ID: {publication.provenance.run_id}</li>
          <li>Generated: {publication.provenance.generated_at}</li>
          <li>Patch count: {publication.provenance.patch_count ?? "N/A"}</li>
          <li>Manifest hash: {publication.provenance.manifest_hash}</li>
        </ul>
      </section>

      <section
        style={{
          background: "#111",
          border: "1px solid #222",
          borderRadius: "8px",
          padding: "1.5rem",
        }}
      >
        <h3 style={{ marginTop: 0 }}>Downloads</h3>
        {publication.allow_download && publication.download_urls ? (
          <div style={{ display: "flex", gap: "1rem", flexWrap: "wrap" }}>
            <a
              href={publication.download_urls.pdf_url}
              style={{ color: "#00ff88", textDecoration: "none" }}
            >
              PDF
            </a>
            <a
              href={publication.download_urls.svg_url}
              style={{ color: "#00ff88", textDecoration: "none" }}
            >
              SVG
            </a>
            <a
              href={publication.download_urls.zip_url}
              style={{ color: "#00ff88", textDecoration: "none" }}
            >
              ZIP
            </a>
          </div>
        ) : (
          <p style={{ color: "#aaa" }}>Downloads are disabled for this publication.</p>
        )}
      </section>

      <section
        style={{
          background: "#111",
          border: "1px solid #222",
          borderRadius: "8px",
          padding: "1.5rem",
        }}
      >
        <h3 style={{ marginTop: 0 }}>Report</h3>
        <label style={{ display: "block", color: "#ccc" }}>
          Reason
          <input
            value={reportReason}
            onChange={(event) => setReportReason(event.target.value)}
            style={{
              width: "100%",
              marginTop: "0.4rem",
              background: "#0d0d0d",
              color: "#fff",
              border: "1px solid #333",
              borderRadius: "4px",
              padding: "0.4rem",
            }}
          />
        </label>
        <label style={{ display: "block", color: "#ccc", marginTop: "0.6rem" }}>
          Details
          <textarea
            value={reportDetails}
            onChange={(event) => setReportDetails(event.target.value)}
            rows={3}
            style={{
              width: "100%",
              marginTop: "0.4rem",
              background: "#0d0d0d",
              color: "#ccc",
              border: "1px solid #333",
              borderRadius: "4px",
              padding: "0.4rem",
            }}
          />
        </label>
        <button
          onClick={submitReport}
          style={{
            marginTop: "0.8rem",
            background: "#222",
            color: "#fff",
            border: "1px solid #333",
            padding: "0.5rem 1rem",
            borderRadius: "6px",
            cursor: "pointer",
          }}
        >
          Report
        </button>
        {reportStatus && <p style={{ color: "#aaa", marginTop: "0.6rem" }}>{reportStatus}</p>}
      </section>
    </div>
  );
}
