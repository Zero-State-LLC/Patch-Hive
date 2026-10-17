/**
 * Cases catalog — normalized case_catalog browse + materialize into Rack Builder.
 */
import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { caseCatalogApi } from "@/lib/api";
import type { CatalogCaseListItem, CatalogStatsResponse } from "@/types/api";

type LoadState = "loading" | "ready" | "empty" | "error";
type PoweredFilter = "all" | "yes" | "no";

const FORMAT_OPTIONS: { value: string; label: string }[] = [
  { value: "", label: "All formats" },
  { value: "eurorack", label: "Eurorack" },
  { value: "intellijel_1u", label: "Intellijel 1U" },
  { value: "buchla_200", label: "Buchla 200" },
  { value: "serge_4u", label: "Serge 4U" },
  { value: "mu_5u", label: "MU / 5U" },
  { value: "frac", label: "Frac" },
  { value: "other", label: "Other" },
];

function capacityLabel(item: CatalogCaseListItem): string {
  const rev = item.primary_revision;
  if (!rev) return "Capacity unspecified";
  const unit = (rev.capacity_unit || "units").replace(/_/g, " ");
  const value = rev.capacity_value != null ? rev.capacity_value : "—";
  const rows =
    rev.row_count != null ? ` · ${rev.row_count} row${rev.row_count === 1 ? "" : "s"}` : "";
  return `${value} ${unit}${rows}`;
}

function depthLabel(item: CatalogCaseListItem): string {
  const rev = item.primary_revision;
  if (!rev) return "Depth unspecified";
  if (rev.depth_min_mm != null && rev.depth_max_mm != null) {
    if (rev.depth_min_mm === rev.depth_max_mm) return `Depth ${rev.depth_min_mm} mm`;
    return `Depth ${rev.depth_min_mm}–${rev.depth_max_mm} mm`;
  }
  if (rev.depth_min_mm != null) return `Depth ≥ ${rev.depth_min_mm} mm`;
  if (rev.depth_max_mm != null) return `Depth ≤ ${rev.depth_max_mm} mm`;
  return "Depth unspecified";
}

function powerLabel(item: CatalogCaseListItem): string {
  if (item.powered === false) return "Unpowered";
  if (item.powered === true) return "Powered (rails on revision / materialize)";
  return "Power unspecified";
}

function canPlace(item: CatalogCaseListItem): boolean {
  return item.format_family === "eurorack" || item.format_family === "intellijel_1u";
}

function formatDisplay(family: string): string {
  return FORMAT_OPTIONS.find((o) => o.value === family)?.label || family;
}

function parsePowered(raw: string | null): PoweredFilter {
  if (raw === "yes" || raw === "true" || raw === "1") return "yes";
  if (raw === "no" || raw === "false" || raw === "0") return "no";
  return "all";
}

export default function CasesPage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const [cases, setCases] = useState<CatalogCaseListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [stats, setStats] = useState<CatalogStatsResponse | null>(null);
  const [state, setState] = useState<LoadState>("loading");
  const [error, setError] = useState("");
  const [q, setQ] = useState(() => searchParams.get("q") || searchParams.get("search") || "");
  const [formatFamilyFilter, setFormatFamilyFilter] = useState(
    () => searchParams.get("format") ?? "eurorack",
  );
  const [poweredFilter, setPoweredFilter] = useState<PoweredFilter>(() =>
    parsePowered(searchParams.get("powered")),
  );
  const [minCapacity, setMinCapacity] = useState(() => searchParams.get("min_capacity") || "");
  const [materializing, setMaterializing] = useState<string | null>(null);
  const [actionError, setActionError] = useState("");
  const [batchNote, setBatchNote] = useState("");
  const [batchBusy, setBatchBusy] = useState(false);

  useEffect(() => {
    const next = new URLSearchParams();
    if (q.trim()) next.set("q", q.trim());
    if (formatFamilyFilter) next.set("format", formatFamilyFilter);
    if (poweredFilter === "yes") next.set("powered", "yes");
    if (poweredFilter === "no") next.set("powered", "no");
    if (minCapacity.trim()) next.set("min_capacity", minCapacity.trim());
    setSearchParams(next, { replace: true });
  }, [q, formatFamilyFilter, poweredFilter, minCapacity, setSearchParams]);

  const load = async () => {
    setState("loading");
    setError("");
    try {
      const [listRes, statsRes] = await Promise.all([
        caseCatalogApi.list({
          limit: 200,
          q: q.trim() || undefined,
          format_family: formatFamilyFilter || undefined,
          powered: poweredFilter === "all" ? undefined : poweredFilter === "yes" ? true : false,
          min_capacity: minCapacity ? Number(minCapacity) : undefined,
        }),
        caseCatalogApi.stats().catch(() => null),
      ]);
      const rows = listRes.data.cases ?? [];
      setCases(rows);
      setTotal(listRes.data.total ?? rows.length);
      setStats(statsRes?.data ?? null);
      setState(rows.length === 0 ? "empty" : "ready");
    } catch {
      setCases([]);
      setTotal(0);
      setStats(null);
      setError(
        "Unable to load the normalized case catalog. Import seed-v1 or check that the API is reachable.",
      );
      setState("error");
    }
  };

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- reload on filter change
  }, [formatFamilyFilter, poweredFilter]);

  const manufacturers = useMemo(() => {
    const set = new Set(cases.map((c) => c.manufacturer));
    return Array.from(set).sort();
  }, [cases]);

  const filtersActive =
    q.trim() || formatFamilyFilter !== "eurorack" || poweredFilter !== "all" || minCapacity.trim();

  const clearFilters = () => {
    setQ("");
    setFormatFamilyFilter("eurorack");
    setPoweredFilter("all");
    setMinCapacity("");
  };

  const materializeAllEurorack = async () => {
    setBatchBusy(true);
    setBatchNote("");
    setActionError("");
    try {
      const res = await caseCatalogApi.materializeBatch({ format_family: "eurorack" });
      const b = res.data;
      setBatchNote(
        `Eurorack materialize: scanned ${b.scanned}, created ${b.created}, updated ${b.updated}, failed ${b.failed}.`,
      );
    } catch {
      setActionError(
        "Bulk materialize failed. Ensure the catalog seed is loaded in this environment.",
      );
    } finally {
      setBatchBusy(false);
    }
  };

  const materializeAndOpenRig = async (item: CatalogCaseListItem) => {
    if (!canPlace(item)) return;
    setMaterializing(item.slug);
    setActionError("");
    try {
      const res = await caseCatalogApi.materialize(item.slug);
      const caseId = res.data.case.id;
      navigate(`/racks/new?case_id=${caseId}&catalog_slug=${encodeURIComponent(item.slug)}`);
    } catch {
      setActionError(
        `Could not materialize “${item.manufacturer} ${item.model}” for Rack Builder. Try again.`,
      );
    } finally {
      setMaterializing(null);
    }
  };

  return (
    <section aria-labelledby="cases-title">
      <header className="workspace-header">
        <div>
          <p className="eyebrow">Catalog</p>
          <h1 id="cases-title">Cases</h1>
          <p className="muted">
            Normalized modular case catalog (research seed + manufacturer expansions). Missing power
            or depth stays missing — never invented. Eurorack (and Intellijel 1U rows) can
            materialize into a placement case for new rigs.
          </p>
        </div>
        <div className="header-actions">
          <Link className="button button-primary" to="/racks/new">
            New rig
          </Link>
          <button
            className="button button-secondary"
            type="button"
            disabled={batchBusy}
            onClick={() => void materializeAllEurorack()}
          >
            {batchBusy ? "Materializing…" : "Materialize Eurorack for rigs"}
          </button>
          <button className="button button-secondary" type="button" onClick={() => void load()}>
            Refresh
          </button>
        </div>
      </header>

      {batchNote ? (
        <p className="status status-success" role="status">
          {batchNote}
        </p>
      ) : null}

      {stats ? (
        <div
          className="panel"
          style={{ marginBottom: "var(--space-4)" }}
          aria-label="Case catalog stats"
        >
          <p className="muted" style={{ margin: 0 }} role="status">
            Catalog: {stats.case_count} cases · {stats.manufacturer_count} manufacturers ·{" "}
            {stats.with_power_rails} with rail data · {stats.with_depth} with depth ·{" "}
            {stats.source_packet_count} source packets
          </p>
          <div className="gate-chip-row" style={{ marginTop: "var(--space-3)" }}>
            <button
              type="button"
              className={`status-chip status-chip--interactive${formatFamilyFilter === "eurorack" ? " status-chip--success" : ""}`}
              onClick={() => setFormatFamilyFilter("eurorack")}
            >
              Eurorack (placeable)
            </button>
            <button
              type="button"
              className={`status-chip status-chip--interactive${formatFamilyFilter === "" ? " is-active" : ""}`}
              onClick={() => setFormatFamilyFilter("")}
            >
              All formats
            </button>
            <button
              type="button"
              className={`status-chip status-chip--interactive${poweredFilter === "yes" ? " status-chip--success" : ""}`}
              onClick={() => setPoweredFilter("yes")}
            >
              Powered
            </button>
            <button
              type="button"
              className={`status-chip status-chip--interactive${poweredFilter === "no" ? " status-chip--warning" : ""}`}
              onClick={() => setPoweredFilter("no")}
            >
              Unpowered
            </button>
          </div>
        </div>
      ) : null}

      <div className="panel" style={{ marginBottom: "var(--space-4)" }} aria-label="Case filters">
        <div className="toolbar">
          <label className="field" style={{ flex: "1 1 12rem" }}>
            Search cases
            <input
              type="search"
              value={q}
              placeholder="Manufacturer, model, or slug…"
              aria-label="Search cases"
              onChange={(e) => setQ(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") void load();
              }}
            />
          </label>
          <label className="inline-field">
            Format
            <select
              value={formatFamilyFilter}
              onChange={(e) => setFormatFamilyFilter(e.target.value)}
            >
              {FORMAT_OPTIONS.map((opt) => (
                <option key={opt.label} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </label>
          <label className="inline-field">
            Powered
            <select
              value={poweredFilter}
              onChange={(e) => setPoweredFilter(e.target.value as PoweredFilter)}
            >
              <option value="all">Any</option>
              <option value="yes">Powered</option>
              <option value="no">Unpowered</option>
            </select>
          </label>
          <label className="inline-field">
            Min capacity
            <input
              type="number"
              min={0}
              value={minCapacity}
              onChange={(e) => setMinCapacity(e.target.value)}
              style={{ width: "6rem" }}
            />
          </label>
          <button className="button button-secondary" type="button" onClick={() => void load()}>
            Apply
          </button>
          {filtersActive ? (
            <button
              className="button button-quiet"
              type="button"
              onClick={() => {
                clearFilters();
              }}
            >
              Clear filters
            </button>
          ) : null}
        </div>
      </div>

      {actionError ? (
        <p className="status status-danger" role="alert">
          {actionError}
        </p>
      ) : null}

      {state === "loading" ? (
        <p className="status" role="status">
          Loading catalog…
        </p>
      ) : null}

      {state === "error" ? (
        <div className="panel" role="alert">
          <p className="status status-danger">{error}</p>
          <p className="muted">
            Dry-run seed lives in <code>data/cases/seed-v1.json</code>. Load with the catalog
            populator against your API database when ready.
          </p>
          <button className="button button-primary" type="button" onClick={() => void load()}>
            Retry
          </button>
        </div>
      ) : null}

      {state === "empty" ? (
        <div className="panel">
          <p className="status status-warning">No catalog cases match these filters.</p>
          <p className="muted">
            Import <code>data/cases/seed-v1.json</code> (not dry-run) or clear filters.
          </p>
        </div>
      ) : null}

      {state === "ready" ? (
        <>
          <p className="muted" role="status" style={{ marginBottom: "var(--space-4)" }}>
            Showing {cases.length} of {total} catalog cases
            {manufacturers.length ? ` · ${manufacturers.length} manufacturers in view` : ""}
            {filtersActive ? " (filtered)" : ""}
          </p>
          <div className="catalog-grid" aria-label="Case catalog results">
            {cases.map((item) => {
              const placeable = canPlace(item);
              const busy = materializing === item.slug;
              return (
                <article key={item.slug} className="catalog-card">
                  <h2>
                    {item.manufacturer} — {item.model}
                  </h2>
                  <p className="catalog-card-meta">{capacityLabel(item)}</p>
                  <p className="catalog-card-meta">{depthLabel(item)}</p>
                  <p className="catalog-card-meta">{powerLabel(item)}</p>
                  <div className="gate-chip-row" aria-label="Case status">
                    {placeable ? (
                      <span className="status-chip status-chip--success">placeable</span>
                    ) : (
                      <span className="status-chip status-chip--warning">catalog only</span>
                    )}
                    {item.powered === true ? (
                      <span className="status-chip status-chip--success">powered</span>
                    ) : item.powered === false ? (
                      <span className="status-chip status-chip--warning">unpowered</span>
                    ) : (
                      <span className="status-chip status-chip--neutral">power unknown</span>
                    )}
                    <span className="status-chip status-chip--neutral">
                      {formatDisplay(item.format_family)}
                    </span>
                  </div>
                  <p className="muted" style={{ margin: 0, fontSize: "0.85rem" }}>
                    {item.primary_revision?.confidence
                      ? `confidence ${item.primary_revision.confidence}`
                      : ""}
                    {item.production_status
                      ? `${item.primary_revision?.confidence ? " · " : ""}${item.production_status}`
                      : ""}
                  </p>
                  <div className="page-hero-actions">
                    <Link
                      className="button button-secondary"
                      to={`/cases/${encodeURIComponent(item.slug)}`}
                    >
                      Details
                    </Link>
                    {placeable ? (
                      <button
                        className="button button-primary"
                        type="button"
                        disabled={busy}
                        onClick={() => void materializeAndOpenRig(item)}
                      >
                        {busy ? "Preparing…" : "Use on new rig"}
                      </button>
                    ) : (
                      <span className="status status-warning">
                        Catalog only (non-Eurorack placement)
                      </span>
                    )}
                    <Link className="button button-quiet" to="/racks">
                      Open rigs
                    </Link>
                  </div>
                </article>
              );
            })}
          </div>
        </>
      ) : null}
    </section>
  );
}
