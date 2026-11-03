/**
 * Catalog case detail — revisions, sources summary, materialize CTA.
 */
import { useEffect, useState, type CSSProperties } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { caseCatalogApi } from "@/lib/api";
import { failureReason } from "@/lib/loadError";

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
  const [loadError, setLoadError] = useState<unknown>(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    if (!slug) {
      setState("missing");
      return;
    }
    let current = true;
    setState("loading");
    setLoadError(null);
    caseCatalogApi
      .get(slug)
      .then((res) => {
        if (!current) return;
        setDetail(res.data as CatalogDetail);
        setState("ready");
      })
      .catch((err) => {
        if (!current) return;
        if (err?.response?.status === 404) {
          setState("missing");
        } else {
          setLoadError(err);
          setState("error");
        }
      });
    return () => {
      current = false;
    };
  }, [slug, attempt]);

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
      setError("Couldn't prepare this case for a new rig. Sign in if needed, then try again.");
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
      <section className="screen-state" aria-labelledby="case-error-title">
        <h1 id="case-error-title" className="empty-title">
          Couldn&apos;t load this case.
        </h1>
        <p className="status status-danger" role="alert">
          {failureReason(loadError)}
        </p>
        <div className="screen-state-actions">
          <button
            className="button button-primary"
            type="button"
            onClick={() => setAttempt((n) => n + 1)}
          >
            Retry
          </button>
          <Link className="button button-secondary" to="/cases">
            Back to cases
          </Link>
        </div>
      </section>
    );
  }

  const rev = detail.revisions[0];
  const placeable = canPlace(detail.format_family);
  const hpCapacity =
    rev && rev.capacity_value != null && (rev.capacity_unit || "").toLowerCase() === "hp"
      ? rev.capacity_value
      : null;

  return (
    <section aria-labelledby="case-detail-title">
      <header className="workspace-header">
        <div>
          <nav className="breadcrumb" aria-label="Breadcrumb">
            <Link to="/cases">Cases</Link>
            <span aria-hidden="true">/</span>
            <span>{detail.format_family}</span>
          </nav>
          <h1 id="case-detail-title">
            {detail.manufacturer} {detail.model}
          </h1>
          <p className="muted">
            Slug <code>{detail.slug}</code>, status {detail.production_status}
            {detail.powered === true ? ", powered" : detail.powered === false ? ", unpowered" : ""}
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
        <div className="panel case-detail-panel">
          <h2>Primary revision: {rev.revision_key}</h2>
          <p className="muted">Confidence: {rev.confidence}</p>
          <div className="case-detail-figure">
            {hpCapacity != null ? (
              <div
                className="capacity-rail case-detail-rail"
                data-wide={hpCapacity > 150 ? "true" : undefined}
                style={{ "--cap": hpCapacity } as CSSProperties}
                aria-hidden="true"
              >
                <div className="capacity-rail__track">
                  <div className="capacity-rail__fill">
                    <span className="capacity-rail__hp">{hpCapacity} HP</span>
                  </div>
                </div>
              </div>
            ) : null}
            <dl className="readout">
              <div>
                <dt>Capacity</dt>
                <dd>
                  {rev.capacity_value ?? "Not stated"} {rev.capacity_unit || ""}
                </dd>
              </div>
              {rev.row_count != null ? (
                <div>
                  <dt>Rows</dt>
                  <dd>{rev.row_count}</dd>
                </div>
              ) : null}
              <div>
                <dt>Depth</dt>
                <dd>
                  {rev.depth_min_mm != null && rev.depth_min_mm === rev.depth_max_mm
                    ? `${rev.depth_min_mm} mm`
                    : rev.depth_min_mm != null || rev.depth_max_mm != null
                      ? `${rev.depth_min_mm ?? "Not stated"} to ${rev.depth_max_mm ?? "Not stated"} mm`
                      : "Unspecified"}
                </dd>
              </div>
            </dl>
          </div>
          {rev.rows?.length ? (
            <>
              <h3>Rows</h3>
              <ul className="case-detail-list">
                {rev.rows.map((r) => (
                  <li key={r.row_index}>
                    Row {r.row_index}: {r.capacity_value ?? "Not stated"} {r.capacity_unit || ""} (
                    {r.format_family})
                  </li>
                ))}
              </ul>
            </>
          ) : null}
          {rev.power_systems?.length ? (
            <>
              <h3>Power</h3>
              <ul className="case-detail-list">
                {rev.power_systems.map((p) => (
                  <li key={p.name}>
                    {p.name}: +12 V {p.current_pos12_ma ?? "Not stated"} mA, −12 V{" "}
                    {p.current_neg12_ma ?? "Not stated"} mA, +5 V{" "}
                    {p.current_pos5_ma ?? "Not stated"} mA
                    {p.connector_count != null ? `, ${p.connector_count} headers` : ""}
                  </li>
                ))}
              </ul>
            </>
          ) : null}
          {rev.notes ? <p className="muted">{rev.notes}</p> : null}
        </div>
      ) : null}

      <div className="panel case-detail-panel">
        <h2>Provenance</h2>
        <p className="muted">
          {detail.sources?.length ?? 0} field-level source packets
          {detail.prices?.length ? `, ${detail.prices.length} price observation(s)` : ""}
        </p>
        {detail.sources?.length ? (
          <div className="case-detail-table">
            <table className="data-table">
              <thead>
                <tr>
                  <th scope="col">Field</th>
                  <th scope="col">Source</th>
                  <th scope="col">Confidence</th>
                  <th scope="col">Policy</th>
                </tr>
              </thead>
              <tbody>
                {detail.sources.slice(0, 12).map((s, i) => (
                  <tr key={`${s.field_path}-${i}`}>
                    <td>
                      <code>{s.field_path || "Not stated"}</code>
                    </td>
                    <td>{s.source_type}</td>
                    <td>{s.confidence}</td>
                    <td>
                      {s.policy
                        ? `${s.policy.access_basis}/${s.policy.evidence_status}/${s.policy.review_state}`
                        : ""}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
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
