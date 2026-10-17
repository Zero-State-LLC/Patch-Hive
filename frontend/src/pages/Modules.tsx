/**
 * Module gallery — browse lightweight module_catalog (research + curated)
 * with optional materialize into full-spec inventory for rack placement.
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import type { CSSProperties } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { moduleApi, rackApi } from "@/lib/api";
import type { CatalogModule, CatalogModuleStats, Rack } from "@/types/api";

type LoadState = "loading" | "ready" | "empty" | "error";
type SortKey = "brand" | "name" | "hp" | "category";
type HpFilter = "all" | "known" | "unknown";

const PAGE_SIZE = 48;

function parseHpFilter(raw: string | null): HpFilter {
  if (raw === "known" || raw === "true" || raw === "1") return "known";
  if (raw === "unknown" || raw === "false" || raw === "0") return "unknown";
  return "all";
}

function parseSort(raw: string | null): SortKey {
  if (raw === "name" || raw === "hp" || raw === "category" || raw === "brand") return raw;
  return "brand";
}

export default function ModulesPage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  const [modules, setModules] = useState<CatalogModule[]>([]);
  const [total, setTotal] = useState(0);
  const [stats, setStats] = useState<CatalogModuleStats | null>(null);
  const [brands, setBrands] = useState<string[]>([]);
  const [categories, setCategories] = useState<string[]>([]);
  const [state, setState] = useState<LoadState>("loading");
  const [error, setError] = useState("");
  const [query, setQuery] = useState(
    () => searchParams.get("q") || searchParams.get("search") || "",
  );
  const [brandFilter, setBrandFilter] = useState(() => searchParams.get("brand") || "all");
  const [typeFilter, setTypeFilter] = useState(
    () => searchParams.get("category") || searchParams.get("type") || "all",
  );
  const [hpFilter, setHpFilter] = useState<HpFilter>(() =>
    parseHpFilter(searchParams.get("hp") || searchParams.get("hp_known")),
  );
  const [sourceFilter, setSourceFilter] = useState(() => searchParams.get("source") || "all");
  const [availabilityFilter, setAvailabilityFilter] = useState(
    () => searchParams.get("status") || searchParams.get("availability") || "all",
  );
  const [sortKey, setSortKey] = useState<SortKey>(() => parseSort(searchParams.get("sort")));
  const [page, setPage] = useState(() => {
    const p = Number(searchParams.get("page") || "1");
    return Number.isFinite(p) && p > 1 ? p - 1 : 0;
  });
  const [busySlug, setBusySlug] = useState<string | null>(null);
  const [actionMsg, setActionMsg] = useState("");
  const [lastPrepared, setLastPrepared] = useState<{
    brand: string;
    name: string;
    moduleId: number;
  } | null>(null);
  const [existingRacks, setExistingRacks] = useState<Rack[]>([]);
  const [pickRackId, setPickRackId] = useState<number | null>(null);
  const [pickerOpen, setPickerOpen] = useState(false);

  // Keep URL in sync so filters are shareable / back-button friendly
  useEffect(() => {
    const next = new URLSearchParams();
    if (query.trim()) next.set("q", query.trim());
    if (brandFilter !== "all") next.set("brand", brandFilter);
    if (typeFilter !== "all") next.set("category", typeFilter);
    if (hpFilter === "known") next.set("hp", "known");
    if (hpFilter === "unknown") next.set("hp", "unknown");
    if (sourceFilter !== "all") next.set("source", sourceFilter);
    if (availabilityFilter !== "all") next.set("status", availabilityFilter);
    if (sortKey !== "brand") next.set("sort", sortKey);
    if (page > 0) next.set("page", String(page + 1));
    setSearchParams(next, { replace: true });
  }, [
    query,
    brandFilter,
    typeFilter,
    hpFilter,
    sourceFilter,
    availabilityFilter,
    sortKey,
    page,
    setSearchParams,
  ]);

  const load = useCallback(() => {
    setState("loading");
    setError("");
    setActionMsg("");
    const params: Record<string, string | number | boolean> = {
      skip: page * PAGE_SIZE,
      limit: PAGE_SIZE,
      sort_by: sortKey === "category" ? "category" : sortKey,
      sort_order: "asc",
    };
    if (query.trim()) params.search = query.trim();
    if (brandFilter !== "all") params.brand = brandFilter;
    if (typeFilter !== "all") params.category = typeFilter;
    if (hpFilter === "known") params.hp_known = true;
    if (hpFilter === "unknown") params.hp_known = false;
    if (sourceFilter !== "all") params.source = sourceFilter;
    if (availabilityFilter !== "all") params.is_available = availabilityFilter;

    Promise.all([
      moduleApi.catalog(params),
      moduleApi.catalogStats(),
      moduleApi.catalogBrands(),
      moduleApi.catalogCategories(),
    ])
      .then(([listRes, statsRes, brandsRes, catsRes]) => {
        const rows = listRes.data.modules ?? [];
        setModules(rows);
        setTotal(listRes.data.total ?? 0);
        setStats(statsRes.data);
        setBrands((brandsRes.data.brands ?? []).map((b) => b.name));
        setCategories((catsRes.data.categories ?? []).map((c) => c.name).filter(Boolean));
        setState(listRes.data.total === 0 ? "empty" : "ready");
      })
      .catch(() => {
        setModules([]);
        setTotal(0);
        setError("Unable to load module catalog. Check that the API is reachable and try again.");
        setState("error");
      });
  }, [page, sortKey, query, brandFilter, typeFilter, hpFilter, sourceFilter, availabilityFilter]);

  useEffect(() => {
    load();
  }, [load]);

  const clearFilters = () => {
    setQuery("");
    setBrandFilter("all");
    setTypeFilter("all");
    setHpFilter("all");
    setSourceFilter("all");
    setAvailabilityFilter("all");
    setSortKey("brand");
    setPage(0);
  };

  const filtersActive =
    query.trim() ||
    brandFilter !== "all" ||
    typeFilter !== "all" ||
    hpFilter !== "all" ||
    sourceFilter !== "all" ||
    availabilityFilter !== "all";

  const activeFilterChips = useMemo(() => {
    const chips: { key: string; label: string; clear: () => void }[] = [];
    if (query.trim()) {
      chips.push({
        key: "q",
        label: `Search: ${query.trim()}`,
        clear: () => {
          setQuery("");
          setPage(0);
        },
      });
    }
    if (brandFilter !== "all") {
      chips.push({
        key: "brand",
        label: `Brand: ${brandFilter}`,
        clear: () => {
          setBrandFilter("all");
          setPage(0);
        },
      });
    }
    if (typeFilter !== "all") {
      chips.push({
        key: "cat",
        label: `Category: ${typeFilter}`,
        clear: () => {
          setTypeFilter("all");
          setPage(0);
        },
      });
    }
    if (hpFilter !== "all") {
      chips.push({
        key: "hp",
        label: hpFilter === "known" ? "HP known" : "HP unknown",
        clear: () => {
          setHpFilter("all");
          setPage(0);
        },
      });
    }
    if (sourceFilter !== "all") {
      chips.push({
        key: "source",
        label: `Source: ${sourceFilter}`,
        clear: () => {
          setSourceFilter("all");
          setPage(0);
        },
      });
    }
    if (availabilityFilter !== "all") {
      chips.push({
        key: "status",
        label: `Status: ${availabilityFilter}`,
        clear: () => {
          setAvailabilityFilter("all");
          setPage(0);
        },
      });
    }
    return chips;
  }, [query, brandFilter, typeFilter, hpFilter, sourceFilter, availabilityFilter]);

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  const materializeRow = async (row: CatalogModule) => {
    if (row.hp == null) {
      setActionMsg(
        `${row.brand} ${row.name}: HP unknown — cannot place until manufacturer width is confirmed.`,
      );
      return null;
    }
    const res = await moduleApi.materializeCatalog(row.slug);
    const mid = res.data.module_id;
    setLastPrepared({ brand: res.data.module.brand, name: res.data.module.name, moduleId: mid });
    return {
      mid,
      status: res.data.status,
      brand: res.data.module.brand,
      name: res.data.module.name,
    };
  };

  /** Primary path: materialize → create-rig flow with module preselected. */
  const placeFromCatalog = async (row: CatalogModule) => {
    setBusySlug(row.slug);
    setActionMsg("");
    setLastPrepared(null);
    setPickerOpen(false);
    try {
      const prep = await materializeRow(row);
      if (!prep) return;
      setActionMsg(
        `${prep.brand} ${prep.name} ready (module #${prep.mid}, ${prep.status}). Opening rack builder…`,
      );
      navigate(`/racks/new?module_id=${prep.mid}`);
    } catch {
      setActionMsg(`${row.brand} ${row.name}: materialize failed (needs known HP or API error).`);
    } finally {
      setBusySlug(null);
    }
  };

  /** Secondary path: materialize → pick an existing rig for placement. */
  const prepareForExistingRig = async (row: CatalogModule) => {
    setBusySlug(row.slug);
    setActionMsg("");
    setLastPrepared(null);
    try {
      const prep = await materializeRow(row);
      if (!prep) return;
      const racksRes = await rackApi.list({ limit: 50 });
      const rows = racksRes.data.racks ?? [];
      setExistingRacks(rows);
      setPickRackId(rows[0]?.id ?? null);
      setPickerOpen(true);
      setActionMsg(
        `${prep.brand} ${prep.name} ready (module #${prep.mid}). Choose a rig to open placement.`,
      );
    } catch {
      setActionMsg(`${row.brand} ${row.name}: materialize or rig list failed.`);
      setPickerOpen(false);
    } finally {
      setBusySlug(null);
    }
  };

  const goToPickedRig = () => {
    if (lastPrepared == null || pickRackId == null) return;
    navigate(`/racks/${pickRackId}/edit?module_id=${lastPrepared.moduleId}`);
  };

  return (
    <section aria-labelledby="modules-title">
      <header className="workspace-header">
        <div>
          <p className="eyebrow">Catalog</p>
          <h1 id="modules-title">Module gallery</h1>
          <p className="muted">
            Browse the lightweight module catalog (research seed + curated). Full power/I/O specs
            load when you materialize a row with known HP for rack placement — unknown widths stay
            null (never invented).
          </p>
        </div>
        <div className="header-actions">
          <Link className="button button-primary" to="/racks/new">
            Place on new rig
          </Link>
          <button className="button button-secondary" type="button" onClick={load}>
            Refresh
          </button>
        </div>
      </header>

      {stats ? (
        <div
          className="panel"
          style={{ marginBottom: "var(--space-4)" }}
          aria-label="Catalog stats"
        >
          <p className="muted" style={{ margin: 0 }}>
            <strong>{stats.total_modules}</strong> modules · <strong>{stats.total_brands}</strong>{" "}
            brands · HP known <strong>{stats.hp_stats.known}</strong> ({stats.hp_stats.coverage_pct}
            %) · unknown <strong>{stats.hp_stats.unknown}</strong> · available{" "}
            <strong>{stats.availability.available}</strong>
            {stats.by_source
              ? ` · sources ${Object.entries(stats.by_source)
                  .map(([k, n]) => `${k || "unknown"}=${n}`)
                  .join(", ")}`
              : ""}
          </p>
          <div className="gate-chip-row" style={{ marginTop: "var(--space-3)" }}>
            <button
              type="button"
              className={`status-chip status-chip--interactive${hpFilter === "known" ? " status-chip--success" : ""}`}
              onClick={() => {
                setHpFilter("known");
                setPage(0);
              }}
            >
              Placeable (HP known)
            </button>
            <button
              type="button"
              className={`status-chip status-chip--interactive${hpFilter === "unknown" ? " status-chip--warning" : ""}`}
              onClick={() => {
                setHpFilter("unknown");
                setPage(0);
              }}
            >
              HP unknown
            </button>
            <button
              type="button"
              className={`status-chip status-chip--interactive${hpFilter === "all" ? " status-chip--neutral is-active" : ""}`}
              onClick={() => {
                setHpFilter("all");
                setPage(0);
              }}
            >
              All widths
            </button>
          </div>
        </div>
      ) : null}

      {actionMsg ? (
        <div
          className={`panel${lastPrepared ? " module-preselect-banner" : ""}`}
          role="status"
          style={{ marginBottom: "var(--space-4)" }}
        >
          <p className="status" style={{ margin: 0 }}>
            {actionMsg}
          </p>
          {lastPrepared && !pickerOpen ? (
            <p className="muted" style={{ margin: "var(--space-2) 0 0" }}>
              Next: pick a case → create rig → module #{lastPrepared.moduleId} is preselected for
              placement.
            </p>
          ) : null}
          {pickerOpen && lastPrepared ? (
            <div className="toolbar" style={{ marginTop: "var(--space-3)" }}>
              <label className="field" style={{ flex: "1 1 14rem" }}>
                Existing rig
                <select
                  value={pickRackId ?? ""}
                  aria-label="Select existing rig"
                  onChange={(e) => setPickRackId(e.target.value ? Number(e.target.value) : null)}
                >
                  {existingRacks.length === 0 ? (
                    <option value="">No rigs yet — create one</option>
                  ) : (
                    existingRacks.map((r) => (
                      <option key={r.id} value={r.id}>
                        #{r.id} · {r.name}
                        {r.case_id != null ? ` · case #${r.case_id}` : ""}
                      </option>
                    ))
                  )}
                </select>
              </label>
              <button
                type="button"
                className="button button-primary"
                disabled={pickRackId == null}
                onClick={goToPickedRig}
              >
                Open placement
              </button>
              <Link
                className="button button-secondary"
                to={`/racks/new?module_id=${lastPrepared.moduleId}`}
              >
                Or create new rig
              </Link>
            </div>
          ) : null}
        </div>
      ) : null}

      {state === "loading" ? (
        <p className="status" role="status">
          Loading catalog…
        </p>
      ) : null}

      {state === "error" ? (
        <div className="panel" role="alert">
          <p className="status status-danger">{error}</p>
          <button className="button button-primary" type="button" onClick={load}>
            Retry
          </button>
        </div>
      ) : null}

      {state === "empty" ? (
        <div className="panel">
          <p className="status status-warning">No modules in the catalog yet.</p>
          <p className="muted">
            Run synth catalog import or ModularGrid curated populate to seed discovery.
          </p>
        </div>
      ) : null}

      {state === "ready" ? (
        <>
          <div
            className="panel"
            aria-label="Module filters"
            style={{ marginBottom: "var(--space-4)" }}
          >
            <div className="toolbar">
              <label className="field" htmlFor="module-search" style={{ flex: "1 1 12rem" }}>
                Search modules
                <input
                  id="module-search"
                  type="search"
                  value={query}
                  placeholder="Brand, name…"
                  aria-label="Search modules"
                  onChange={(event) => {
                    setPage(0);
                    setQuery(event.target.value);
                  }}
                  autoComplete="off"
                />
              </label>
              <label className="inline-field" htmlFor="module-brand">
                Brand
                <select
                  id="module-brand"
                  value={brandFilter}
                  onChange={(event) => {
                    setPage(0);
                    setBrandFilter(event.target.value);
                  }}
                >
                  <option value="all">All brands</option>
                  {brands.map((brand) => (
                    <option key={brand} value={brand}>
                      {brand}
                    </option>
                  ))}
                </select>
              </label>
              <label className="inline-field" htmlFor="module-type">
                Category
                <select
                  id="module-type"
                  value={typeFilter}
                  onChange={(event) => {
                    setPage(0);
                    setTypeFilter(event.target.value);
                  }}
                >
                  <option value="all">All categories</option>
                  {categories.map((type) => (
                    <option key={type} value={type}>
                      {type}
                    </option>
                  ))}
                </select>
              </label>
              <label className="inline-field" htmlFor="module-hp">
                HP
                <select
                  id="module-hp"
                  value={hpFilter}
                  onChange={(event) => {
                    setPage(0);
                    setHpFilter(event.target.value as HpFilter);
                  }}
                >
                  <option value="all">All</option>
                  <option value="known">Known width</option>
                  <option value="unknown">Unknown width</option>
                </select>
              </label>
              <label className="inline-field" htmlFor="module-source">
                Source
                <select
                  id="module-source"
                  value={sourceFilter}
                  onChange={(event) => {
                    setPage(0);
                    setSourceFilter(event.target.value);
                  }}
                >
                  <option value="all">All sources</option>
                  {stats?.by_source
                    ? Object.keys(stats.by_source)
                        .filter(Boolean)
                        .sort()
                        .map((src) => (
                          <option key={src} value={src}>
                            {src}
                          </option>
                        ))
                    : null}
                  {!stats?.by_source ? (
                    <option value="SynthCatalogResearch">SynthCatalogResearch</option>
                  ) : null}
                </select>
              </label>
              <label className="inline-field" htmlFor="module-availability">
                Status
                <select
                  id="module-availability"
                  value={availabilityFilter}
                  onChange={(event) => {
                    setPage(0);
                    setAvailabilityFilter(event.target.value);
                  }}
                >
                  <option value="all">All status</option>
                  <option value="available">available</option>
                  <option value="discontinued">discontinued</option>
                  <option value="upcoming">upcoming</option>
                  <option value="duplicate">duplicate</option>
                  <option value="non_eurorack">non_eurorack</option>
                  <option value="desktop">desktop</option>
                  <option value="unresolved">unresolved</option>
                </select>
              </label>
              <label className="inline-field" htmlFor="module-sort">
                Sort
                <select
                  id="module-sort"
                  value={sortKey}
                  onChange={(event) => {
                    setPage(0);
                    setSortKey(event.target.value as SortKey);
                  }}
                >
                  <option value="brand">Brand</option>
                  <option value="name">Name</option>
                  <option value="category">Category</option>
                  <option value="hp">HP (width)</option>
                </select>
              </label>
              {filtersActive ? (
                <button className="button button-quiet" type="button" onClick={clearFilters}>
                  Clear filters
                </button>
              ) : null}
            </div>
            {activeFilterChips.length > 0 ? (
              <div className="filter-chip-row" aria-label="Active filters">
                {activeFilterChips.map((chip) => (
                  <button
                    key={chip.key}
                    type="button"
                    className="status-chip status-chip--interactive"
                    onClick={chip.clear}
                    title="Remove filter"
                  >
                    {chip.label} ×
                  </button>
                ))}
              </div>
            ) : null}
          </div>

          <p className="muted" role="status" style={{ marginBottom: "var(--space-4)" }}>
            Showing {modules.length} of {total} catalog modules
            {filtersActive ? " (filtered)" : ""} · page {page + 1}/{totalPages}
          </p>

          {modules.length === 0 ? (
            <div className="panel">
              <p className="status status-warning">No modules match these filters.</p>
              <button className="button button-secondary" type="button" onClick={clearFilters}>
                Clear filters
              </button>
            </div>
          ) : (
            <ul className="catalog-grid" aria-label="Module catalog results">
              {modules.map((module) => (
                <li key={module.slug}>
                  <article className="catalog-card" style={{ height: "100%" }}>
                    {(() => {
                      const hp = module.hp ?? 0;
                      const hpScale = Math.min(Math.max(hp / 42, 0.2), 1); // normalize to ~42HP max
                      return (
                        <div
                          className="module-mockup"
                          data-category={module.category || "UTIL"}
                          style={{ "--hp-scale": hpScale } as CSSProperties}
                          title={`${module.brand} — ${module.name} (${hp || "?"}HP)`}
                          aria-label={`Module: ${module.brand} ${module.name}, ${hp} HP, ${module.category || "UTIL"}`}
                        >
                          <div className="mockup-hp">
                            <div className="hp-num">{hp || "—"}</div>
                            <div className="hp-label">HP</div>
                            {hp > 0 && <div className="hp-bar" />}
                          </div>
                          <div className="mockup-face">
                            <div className="mockup-brand">{module.brand}</div>
                            <div className="mockup-name">{module.name}</div>
                            {module.registry_manufacturer_slug && (
                              <div className="reg-badge" title="Linked to Registry">
                                REG
                              </div>
                            )}
                            <div className="mockup-ports" aria-hidden="true" />
                          </div>
                        </div>
                      );
                    })()}
                    <p className="catalog-card-meta">{module.category ?? "UTIL"}</p>
                    <div className="gate-chip-row" aria-label="Module status">
                      {module.hp != null ? (
                        <span className="status-chip status-chip--success">placeable</span>
                      ) : (
                        <span className="status-chip status-chip--warning">HP unknown</span>
                      )}
                      {module.source ? (
                        <span className="status-chip status-chip--neutral">{module.source}</span>
                      ) : null}
                      {module.registry_manufacturer_slug ? (
                        <Link
                          to={`/products?query=${encodeURIComponent(module.registry_manufacturer_slug)}`}
                          className="status-chip status-chip--neutral hover:bg-zinc-700 no-underline"
                          title="View in Product Database (Registry)"
                          onClick={(e) => e.stopPropagation()}
                        >
                          reg:{module.registry_manufacturer_slug}
                          {module.registry_device_slug
                            ? `/${module.registry_device_slug.split("-").pop()}`
                            : ""}
                        </Link>
                      ) : null}
                      {module.is_available && module.is_available !== "available" ? (
                        <span className="status-chip status-chip--warning">
                          {module.is_available}
                        </span>
                      ) : null}
                    </div>
                    <div className="page-hero-actions">
                      <button
                        className="button button-primary"
                        type="button"
                        disabled={busySlug === module.slug || module.hp == null}
                        title={
                          module.hp == null
                            ? "Needs manufacturer-confirmed HP before placement"
                            : "Materialize full module record, then open rack builder with it preselected"
                        }
                        onClick={() => placeFromCatalog(module)}
                      >
                        {busySlug === module.slug
                          ? "Preparing…"
                          : module.hp == null
                            ? "Needs HP"
                            : "Prepare for rig"}
                      </button>
                      <button
                        className="button button-secondary"
                        type="button"
                        disabled={busySlug === module.slug || module.hp == null}
                        title="Materialize and choose an existing rig for placement"
                        onClick={() => void prepareForExistingRig(module)}
                      >
                        Add to existing
                      </button>
                      <Link className="button button-quiet" to="/racks">
                        Open rigs
                      </Link>
                    </div>
                  </article>
                </li>
              ))}
            </ul>
          )}

          {totalPages > 1 ? (
            <div className="toolbar" style={{ marginTop: "var(--space-4)" }}>
              <button
                className="button button-secondary"
                type="button"
                disabled={page <= 0}
                onClick={() => setPage((p) => Math.max(0, p - 1))}
              >
                Previous
              </button>
              <button
                className="button button-secondary"
                type="button"
                disabled={page + 1 >= totalPages}
                onClick={() => setPage((p) => p + 1)}
              >
                Next
              </button>
            </div>
          ) : null}
        </>
      ) : null}
    </section>
  );
}
