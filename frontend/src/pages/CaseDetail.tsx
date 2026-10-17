/**
 * Catalog case detail — revisions, sources summary, materialize CTA.
 */
import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { caseCatalogApi } from "@/lib/api";

type LoadState = "loading" | "ready" | "error" | "missing";

interface CatalogDetail {
  slug: string;
  manufacturer: string;
  model: string;
  format_family: string;
  production_status: string;
  powered?: boolean | null;
  official_url?: string | null;
  revisions: {
    revision_key: string;
    revision_label?: string | null;
    row_count?: number | null;
    capacity_value?: number | null;
    capacity_unit?: string | null;
    depth_min_mm?: number | null;
    depth_max_mm?: number | null;
    confidence: string;
    notes?: string | null;
    rows: {
      row_index: number;
      format_family: string;
      capacity_value?: number | null;
      capacity_unit?: string | null;
    }[];
    power_systems: {
      name: string;
      current_pos12_ma?: number | null;
      current_neg12_ma?: number | null;
      current_pos5_ma?: number | null;
      connector_count?: number | null;
      notes?: string | null;
    }[];
    features: { feature_key: string; feature_value?: string | null }[];
  }[];
  sources: {
    field_path?: string | null;
    source_type: string;
    confidence: string;
    policy?: { access_basis?: string; evidence_status?: string; review_state?: string } | null;
  }[];
  prices: { amount: string; currency: string; price_type: string; source_name: string }[];
}

function canPlace(family: string): boolean {
  return family === "eurorack" || family === "intellijel_1u";
}

export default function CaseDetailPage() {
  const { slug = "" } = useParams<{ slug: string }>();
  const navigate = useNavigate();
  const [state, setState] = useState<LoadState>("loading");
  const [detail, setDetail] = useState<CatalogDetail | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!slug) {
      setState("missing");
      return;
    }
    setState("loading");
    caseCatalogApi
      .get(slug)
      .then((res) => {
        setDetail(res.data as CatalogDetail);
        setState("ready");
      })
      .catch((err) => {
        const status = err?.response?.status;
        if (status === 404) setState("missing");
        else {
          setError("Unable to load catalog case.");
          setState("error");
        }
      });
  }, [slug]);

  const materializeAndOpen = async () => {
    if (!detail || !canPlace(detail.format_family)) return;
    setBusy(true);
    setError("");
    try {
      const res = await caseCatalogApi.materialize(detail.slug);
      navigate(
        `/racks/new?case_id=${res.data.case.id}&catalog_slug=${encodeURIComponent(detail.slug)}`,
      );
    } catch {
      setError("Materialize failed. Ensure you are signed in if required, and try again.");
    } finally {
      setBusy(false);
    }
  };

  if (state === "loading") {
    return (
      <section>
        <p className="status" role="status">
          Loading case…
        </p>
      </section>
    );
  }

  if (state === "missing") {
    return (
      <section className="panel">
        <h1>Case not found</h1>
        <p className="muted">No catalog case with slug “{slug}”.</p>
        <Link className="button button-primary" to="/cases">
          Back to cases
        </Link>
      </section>
    );
  }

  if (state === "error" || !detail) {
    return (
      <section className="panel" role="alert">
        <p className="status status-danger">{error || "Error"}</p>
        <Link className="button button-secondary" to="/cases">
          Back to cases
        </Link>
      </section>
    );
  }

  const rev = detail.revisions[0];
  const placeable = canPlace(detail.format_family);

  return (
    <section aria-labelledby="case-detail-title">
      <header className="workspace-header">
        <div>
          <p className="eyebrow">
            <Link to="/cases">Cases</Link> · {detail.format_family}
          </p>
          <h1 id="case-detail-title">
            {detail.manufacturer} — {detail.model}
          </h1>
          <p className="muted">
            Slug <code>{detail.slug}</code> · status {detail.production_status}
            {detail.powered === true
              ? " · powered"
              : detail.powered === false
                ? " · unpowered"
                : ""}
          </p>
        </div>
        <div className="header-actions">
          {placeable ? (
            <button
              type="button"
              className="button button-primary"
              disabled={busy}
              onClick={() => void materializeAndOpen()}
            >
              {busy ? "Preparing…" : "Use on new rig"}
            </button>
          ) : (
            <span className="status status-warning">Catalog only (non-Eurorack placement)</span>
          )}
          <Link className="button button-secondary" to="/cases">
            All cases
          </Link>
        </div>
      </header>

      {error ? (
        <p className="status status-danger" role="alert">
          {error}
        </p>
      ) : null}

      {rev ? (
        <div className="panel" style={{ marginBottom: "var(--space-4)" }}>
          <h2 style={{ marginTop: 0 }}>Primary revision · {rev.revision_key}</h2>
          <p className="muted">Confidence: {rev.confidence}</p>
          <div className="stat-row">
            <div className="stat-block">
              <p className="muted" style={{ margin: 0 }}>
                Capacity
              </p>
              <h3 style={{ fontSize: "1rem" }}>
                {rev.capacity_value ?? "—"} {rev.capacity_unit || ""}
                {rev.row_count != null ? ` · ${rev.row_count} row(s)` : ""}
              </h3>
            </div>
            <div className="stat-block">
              <p className="muted" style={{ margin: 0 }}>
                Depth
              </p>
              <h3 style={{ fontSize: "1rem" }}>
                {rev.depth_min_mm != null || rev.depth_max_mm != null
                  ? `${rev.depth_min_mm ?? "—"}–${rev.depth_max_mm ?? "—"} mm`
                  : "Unspecified"}
              </h3>
            </div>
          </div>
          {rev.rows?.length ? (
            <>
              <h3>Rows</h3>
              <ul>
                {rev.rows.map((r) => (
                  <li key={r.row_index}>
                    Row {r.row_index}: {r.capacity_value ?? "—"} {r.capacity_unit || ""} (
                    {r.format_family})
                  </li>
                ))}
              </ul>
            </>
          ) : null}
          {rev.power_systems?.length ? (
            <>
              <h3>Power</h3>
              <ul>
                {rev.power_systems.map((p) => (
                  <li key={p.name}>
                    {p.name}: +12 {p.current_pos12_ma ?? "—"}mA · −12 {p.current_neg12_ma ?? "—"}mA
                    · +5 {p.current_pos5_ma ?? "—"}mA
                    {p.connector_count != null ? ` · ${p.connector_count} headers` : ""}
                  </li>
                ))}
              </ul>
            </>
          ) : null}
          {rev.notes ? <p className="muted">{rev.notes}</p> : null}
        </div>
      ) : null}

      <div className="panel" style={{ marginBottom: "var(--space-4)" }}>
        <h2 style={{ marginTop: 0 }}>Provenance</h2>
        <p className="muted">
          {detail.sources?.length ?? 0} field-level source packets
          {detail.prices?.length ? ` · ${detail.prices.length} price observation(s)` : ""}
        </p>
        {detail.sources?.length ? (
          <ul>
            {detail.sources.slice(0, 12).map((s, i) => (
              <li key={`${s.field_path}-${i}`}>
                <code>{s.field_path || "—"}</code> · {s.source_type} · {s.confidence}
                {s.policy
                  ? ` · ${s.policy.access_basis}/${s.policy.evidence_status}/${s.policy.review_state}`
                  : ""}
              </li>
            ))}
          </ul>
        ) : (
          <p className="muted">No sources attached.</p>
        )}
        {detail.sources && detail.sources.length > 12 ? (
          <p className="muted">…and {detail.sources.length - 12} more</p>
        ) : null}
      </div>

      {detail.official_url ? (
        <p>
          <a href={detail.official_url} rel="noreferrer" target="_blank">
            Official URL
          </a>
        </p>
      ) : null}
    </section>
  );
}
