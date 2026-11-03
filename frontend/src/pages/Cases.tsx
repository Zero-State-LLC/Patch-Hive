/**
 * Cases catalog — normalized case_catalog browse + materialize into Rack Builder.
 */
import { useEffect, useMemo, useState } from "react";
import type { CSSProperties } from "react";
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
  const rows =
    rev.row_count != null ? `, ${rev.row_count} row${rev.row_count === 1 ? "" : "s"}` : "";
  if (rev.capacity_value == null) return `Capacity unspecified${rows}`;
  return `${rev.capacity_value} ${unit}${rows}`;
}

function depthLabel(item: CatalogCaseListItem): string {
  const rev = item.primary_revision;
  if (!rev) return "Depth unspecified";
  if (rev.depth_min_mm != null && rev.depth_max_mm != null) {
    if (rev.depth_min_mm === rev.depth_max_mm) return `Depth ${rev.depth_min_mm} mm`;
    return `Depth ${rev.depth_min_mm} to ${rev.depth_max_mm} mm`;
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

/** Stated capacity in HP, drawn as the case's rail; other units are not drawn. */
function railCapacity(item: CatalogCaseListItem): number | null {
  const rev = item.primary_revision;
  if (!rev || rev.capacity_value == null) return null;
  return (rev.capacity_unit || "").toLowerCase() === "hp" ? rev.capacity_value : null;
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
        import.meta.env.DEV
          ? "Unable to load the normalized case catalog. Import seed-v1 or check that the API is reachable."
          : "Unable to load the case catalog. Try again in a moment.",
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
          <h1 id="cases-title">Cases</h1>
          <p className="muted">
            Modular cases from research seeds and manufacturer data. Missing power or depth stays
            missing. Eurorack cases can seed a new rig.
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
          <button className="button button-quiet" type="button" onClick={() => void load()}>
            Refresh
          </button>
        </div>
      </header>

      {stats ? (
        <div role="status" aria-label="Case catalog stats">
          <dl className="readout">
            <div>
              <dt>Cases</dt>
              <dd>{stats.case_count}</dd>
            </div>
            <div>
              <dt>Manufacturers</dt>
              <dd>{stats.manufacturer_count}</dd>
            </div>
            <div>
              <dt>With rail data</dt>
              <dd>{stats.with_power_rails}</dd>
            </div>
            <div>
              <dt>With depth</dt>
              <dd>{stats.with_depth}</dd>
            </div>
            <div>
              <dt>Source packets</dt>
              <dd>{stats.source_packet_count}</dd>
            </div>
          </dl>
        </div>
      ) : null}

      <div className="filter-bar" aria-label="Case filters">
        <div className="seg" role="group" aria-labelledby="case-format-label">
          <span className="seg-label" id="case-format-label">
            Placement
          </span>
          <div className="seg-options">
            <button
              type="button"
              aria-pressed={formatFamilyFilter === "eurorack"}
              className={`status-chip status-chip--interactive${formatFamilyFilter === "eurorack" ? " status-chip--success" : ""}`}
              onClick={() => setFormatFamilyFilter("eurorack")}
            >
              Eurorack (placeable)
            </button>
            <button
              type="button"
              aria-pressed={formatFamilyFilter === ""}
              className={`status-chip status-chip--interactive${formatFamilyFilter === "" ? " is-active" : ""}`}
              onClick={() => setFormatFamilyFilter("")}
            >
              All formats
            </button>
          </div>
        </div>
        <div className="seg" role="group" aria-labelledby="case-power-label">
          <span className="seg-label" id="case-power-label">
            Power supply
          </span>
          <div className="seg-options">
            <button
              type="button"
              aria-pressed={poweredFilter === "yes"}
              className={`status-chip status-chip--interactive${poweredFilter === "yes" ? " status-chip--success" : ""}`}
              onClick={() => setPoweredFilter("yes")}
            >
              Powered
            </button>
            <button
              type="button"
              aria-pressed={poweredFilter === "no"}
              className={`status-chip status-chip--interactive${poweredFilter === "no" ? " status-chip--warning" : ""}`}
              onClick={() => setPoweredFilter("no")}
            >
              Unpowered
            </button>
          </div>
        </div>
        <label className="field">
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
        <label className="inline-field case-min-capacity">
          Min capacity
          <input
            type="number"
            min={0}
            value={minCapacity}
            onChange={(e) => setMinCapacity(e.target.value)}
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

      {batchNote ? (
        <p className="notice status status-success" role="status">
          {batchNote}
        </p>
      ) : null}

      {actionError ? (
        <p className="status status-danger" role="alert">
          {actionError}
        </p>
      ) : null}

      {state === "loading" ? (
        <p className="results-meta" role="status">
          Loading catalog…
        </p>
      ) : null}

      {state === "error" ? (
        <div className="screen-state" role="alert">
          <p className="status status-danger">{error}</p>
          {import.meta.env.DEV ? (
            <p className="muted">
              Dry-run seed lives in <code>data/cases/seed-v1.json</code>. Load with the catalog
              populator against your API database when ready.
            </p>
          ) : null}
          <button className="button button-primary" type="button" onClick={() => void load()}>
            Retry
          </button>
        </div>
      ) : null}

      {state === "empty" ? (
        <div className="screen-state">
          <p className="status status-warning">No catalog cases match these filters.</p>
          <p className="muted">
            {import.meta.env.DEV ? (
              <>
                Import <code>data/cases/seed-v1.json</code> (not dry-run) or clear filters.
              </>
            ) : (
              "Clear filters to see more cases."
            )}
          </p>
        </div>
      ) : null}

      {state === "ready" ? (
        <>
          <p className="results-meta" role="status">
            Showing {cases.length} of {total} catalog cases
            {manufacturers.length ? `, ${manufacturers.length} manufacturers in view` : ""}
            {filtersActive ? " (filtered)" : ""}
          </p>
          <div className="catalog-grid" aria-label="Case catalog results">
            {cases.map((item) => {
              const placeable = canPlace(item);
              const busy = materializing === item.slug;
              const hpCapacity = railCapacity(item);
              return (
                <article key={item.slug} className="catalog-card">
                  {hpCapacity != null ? (
                    <div
                      className="capacity-rail"
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
                  <h2>
                    {item.manufacturer} {item.model}
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
                  {item.primary_revision?.confidence || item.production_status ? (
                    <p className="muted case-confidence">
                      {[
                        item.primary_revision?.confidence
                          ? `confidence ${item.primary_revision.confidence}`
                          : "",
                        item.production_status ?? "",
                      ]
                        .filter(Boolean)
                        .join(", ")}
                    </p>
                  ) : null}
                  <div className="page-hero-actions">
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
                    <Link
                      className="button button-secondary"
                      to={`/cases/${encodeURIComponent(item.slug)}`}
                    >
                      Details
                    </Link>
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
