/**
 * Module gallery — browse lightweight module_catalog (research + curated)
 * with optional materialize into full-spec inventory for rack placement.
 */
import { useEffect, useMemo, useRef, useState } from "react";
import type { CSSProperties } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import LoadFailure from "@/components/LoadFailure";
import { canonApi, moduleApi } from "@/lib/api";
import { rigSummaryToRack } from "@/lib/canonRigAdapter";
import { isCancelled } from "@/lib/loadError";
import { useAuthStore } from "@/lib/store";
import { useDebouncedValue } from "@/lib/useDebouncedValue";
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
  const [error, setError] = useState<unknown>(null);
  // Retry and Refresh bump this to ask again with the same filters.
  const [attempt, setAttempt] = useState(0);
  const reload = () => setAttempt((n) => n + 1);
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

  // What the catalog returns depends on whether the reader is signed in (owner decision 39).
  // A change of reader drops what the last one got while rendering, so none of it reaches the
  // screen, and the effects below ask again. A token renewal is not a change of reader.
  const signedIn = useAuthStore((st) => st.isAuthenticated());
  const [reader, setReader] = useState(signedIn);
  if (reader !== signedIn) {
    setReader(signedIn);
    setModules([]);
    setTotal(0);
    setStats(null);
    setBrands([]);
    setCategories([]);
    setPage(0);
    setState("loading");
    setError(null);
    setActionMsg("");
    setLastPrepared(null);
    setExistingRacks([]);
    setPickRackId(null);
    setPickerOpen(false);
  }

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

  // The search asks once the typing pauses; the other filters ask at once.
  const searchTerm = useDebouncedValue(query.trim());

  // Stats, brands and categories don't change with the filters: fetched once per reader, and
  // again on Retry only if they didn't arrive. The ref holds the reader they were loaded for.
  const metaLoaded = useRef<boolean | null>(null);
  useEffect(() => {
    if (metaLoaded.current === signedIn) return;
    let current = true;
    void Promise.allSettled([
      moduleApi.catalogStats(),
      moduleApi.catalogBrands(),
      moduleApi.catalogCategories(),
    ]).then(([statsRes, brandsRes, catsRes]) => {
      if (!current) return;
      if (statsRes.status === "fulfilled") setStats(statsRes.value.data);
      if (brandsRes.status === "fulfilled") {
        setBrands((brandsRes.value.data.brands ?? []).map((b) => b.name));
      }
      if (catsRes.status === "fulfilled") {
        setCategories((catsRes.value.data.categories ?? []).map((c) => c.name).filter(Boolean));
      }
      const loaded = [statsRes, brandsRes, catsRes].every((r) => r.status === "fulfilled");
      metaLoaded.current = loaded ? signedIn : null;
    });
    return () => {
      current = false;
    };
  }, [attempt, signedIn]);

  // The list: a change of filter cancels the request before it, so a slow earlier answer can
  // never replace the one asked for last.
  useEffect(() => {
    const controller = new AbortController();
    setState("loading");
    setError(null);
    setActionMsg("");
    const params: Record<string, string | number | boolean> = {
      skip: page * PAGE_SIZE,
      limit: PAGE_SIZE,
      sort_by: sortKey === "category" ? "category" : sortKey,
      sort_order: "asc",
    };
    if (searchTerm) params.search = searchTerm;
    if (brandFilter !== "all") params.brand = brandFilter;
    if (typeFilter !== "all") params.category = typeFilter;
    if (hpFilter === "known") params.hp_known = true;
    if (hpFilter === "unknown") params.hp_known = false;
    if (sourceFilter !== "all") params.source = sourceFilter;
    if (availabilityFilter !== "all") params.is_available = availabilityFilter;

    moduleApi
      .catalog(params, { signal: controller.signal })
      .then((listRes) => {
        if (controller.signal.aborted) return;
        const rows = listRes.data.modules ?? [];
        setModules(rows);
        setTotal(listRes.data.total ?? 0);
        setState(listRes.data.total === 0 ? "empty" : "ready");
      })
      .catch((err: unknown) => {
        if (controller.signal.aborted || isCancelled(err)) return;
        setModules([]);
        setTotal(0);
        setError(err);
        setState("error");
      });
    return () => controller.abort();
  }, [
    page,
    sortKey,
    searchTerm,
    brandFilter,
    typeFilter,
    hpFilter,
    sourceFilter,
    availabilityFilter,
    attempt,
    signedIn,
  ]);

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
        `${row.brand} ${row.name}: HP unknown, so it cannot be placed until the manufacturer width is confirmed.`,
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
      setActionMsg(
        `${row.brand} ${row.name} couldn't be prepared for a rig. It needs a known width, or the server refused.`,
      );
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
      // Spec 008 F5: picker reads the canonical inventory list (rig_id = rack id).
      const rigsRes = await canonApi.listRigs({ limit: 50 });
      const rows = (rigsRes.data.rigs ?? []).map(rigSummaryToRack);
      setExistingRacks(rows);
      setPickRackId(rows[0]?.id ?? null);
      setPickerOpen(true);
      setActionMsg(
        `${prep.brand} ${prep.name} ready (module #${prep.mid}). Choose a rig to open placement.`,
      );
    } catch {
      setActionMsg(`${row.brand} ${row.name} couldn't be prepared, or your rigs couldn't load.`);
      setPickerOpen(false);
    } finally {
      setBusySlug(null);
    }
  };

  const goToPickedRig = () => {
    if (lastPrepared == null || pickRackId == null) return;
    navigate(`/racks/${pickRackId}/edit?module_id=${lastPrepared.moduleId}`);
  };

  const showList = state === "ready" || (state === "loading" && modules.length > 0);

  return (
    <section aria-labelledby="modules-title">
      <header className="workspace-header">
        <div>
          <h1 id="modules-title">Module gallery</h1>
          <p className="muted">
            Every module drawn to its width. Unknown widths stay unknown, never invented.
          </p>
        </div>
        <div className="header-actions">
          <Link className="button button-primary" to="/racks/new">
            Place on new rig
          </Link>
          <button className="button button-quiet" type="button" onClick={reload}>
            Refresh
          </button>
        </div>
      </header>

      {stats ? (
        <dl className="readout" aria-label="Catalog stats">
          <div>
            <dt>Modules</dt>
            <dd>{stats.total_modules}</dd>
          </div>
          <div>
            <dt>Brands</dt>
            <dd>{stats.total_brands}</dd>
          </div>
          <div>
            <dt>HP known</dt>
            <dd>
              {stats.hp_stats.known}
              <small>{stats.hp_stats.coverage_pct}%</small>
            </dd>
          </div>
          <div>
            <dt>HP unknown</dt>
            <dd>{stats.hp_stats.unknown}</dd>
          </div>
          <div>
            <dt>Available</dt>
            <dd>{stats.availability.available}</dd>
          </div>
          {stats.by_source ? (
            <div className="readout-wide">
              <dt>Sources</dt>
              <dd>
                {Object.entries(stats.by_source)
                  .map(([k, n]) => `${k || "Not stated"} ${n}`)
                  .join(", ")}
              </dd>
            </div>
          ) : null}
        </dl>
      ) : null}

      <div className="catalog-layout">
        <aside className="filter-rail" aria-label="Module filters">
          <div className="seg" role="group" aria-labelledby="module-width-label">
            <span className="seg-label" id="module-width-label">
              Width
            </span>
            <div className="seg-options">
              <button
                type="button"
                aria-pressed={hpFilter === "known"}
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
                aria-pressed={hpFilter === "unknown"}
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
                aria-pressed={hpFilter === "all"}
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
          <label className="field" htmlFor="module-search">
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
        </aside>

        <div className="catalog-results" aria-busy={state === "loading"}>
          {actionMsg ? (
            <div className={lastPrepared ? "module-preselect-banner" : "notice"} role="status">
              <p className="status">{actionMsg}</p>
              {lastPrepared && !pickerOpen ? (
                <p className="muted">
                  Next: pick a case, create the rig, and module #{lastPrepared.moduleId} is
                  preselected for placement.
                </p>
              ) : null}
              {pickerOpen && lastPrepared ? (
                <div className="toolbar">
                  <label className="field">
                    Existing rig
                    <select
                      value={pickRackId ?? ""}
                      aria-label="Select existing rig"
                      onChange={(e) =>
                        setPickRackId(e.target.value ? Number(e.target.value) : null)
                      }
                    >
                      {existingRacks.length === 0 ? (
                        <option value="">No rigs yet, create one</option>
                      ) : (
                        existingRacks.map((r) => (
                          <option key={r.id} value={r.id}>
                            #{r.id} {r.name}
                            {r.case_id != null ? ` (case #${r.case_id})` : ""}
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
            <p className="results-meta" role="status">
              Loading catalog…
            </p>
          ) : null}

          {state === "loading" && modules.length === 0 ? (
            <ul className="module-skeleton" aria-hidden="true">
              {[8, 14, 4, 20, 10, 6].map((w, i) => (
                <li key={i}>
                  <span className="skeleton" style={{ "--w": w } as CSSProperties} />
                  <span className="skeleton" />
                </li>
              ))}
            </ul>
          ) : null}

          {state === "error" ? (
            <LoadFailure what="The module catalog" error={error} onRetry={reload} />
          ) : null}

          {state === "empty" && filtersActive ? (
            <div className="screen-state">
              <p className="status status-warning">No modules match these filters.</p>
              <button className="button button-secondary" type="button" onClick={clearFilters}>
                Clear filters
              </button>
            </div>
          ) : null}

          {state === "empty" && !filtersActive ? (
            <div className="screen-state">
              <p className="status status-warning">No modules in the catalog yet.</p>
              <p className="muted">
                The catalog hasn't been loaded on this environment.
              </p>
            </div>
          ) : null}

          {showList ? (
            <>
              {state === "ready" ? (
                <p className="results-meta" role="status">
                  Showing {modules.length} of {total} catalog modules
                  {filtersActive ? " (filtered)" : ""}, page {page + 1} of {totalPages}
                </p>
              ) : null}

              {modules.length === 0 ? (
                <div className="screen-state">
                  <p className="status status-warning">No modules match these filters.</p>
                  <button className="button button-secondary" type="button" onClick={clearFilters}>
                    Clear filters
                  </button>
                </div>
              ) : (
                <ul className="module-list" aria-label="Module catalog results">
                  {modules.map((module, index) => {
                    const hp = module.hp ?? 0;
                    return (
                      <li
                        key={module.slug}
                        className="module-row"
                        style={{ "--i": index } as CSSProperties}
                      >
                        <div
                          className="module-mockup"
                          data-category={module.category || "UTIL"}
                          data-hp={hp > 0 ? "known" : "unknown"}
                          data-wide={hp > 48 ? "true" : undefined}
                          style={(hp > 0 ? { "--hp": hp } : {}) as CSSProperties}
                          title={`${module.brand} ${module.name} (${hp || "?"}HP)`}
                          aria-label={`Module: ${module.brand} ${module.name}, ${hp} HP, ${module.category || "UTIL"}`}
                        >
                          <div className="mockup-plate" aria-hidden="true">
                            <span className="mockup-ports" />
                          </div>
                          <div className="mockup-face">
                            <div className="mockup-brand">{module.brand}</div>
                            <div className="mockup-name">{module.name}</div>
                          </div>
                        </div>
                        <div className="gate-chip-row module-row__chips" aria-label="Module status">
                          {module.hp != null ? (
                            <span className="status-chip status-chip--success">placeable</span>
                          ) : (
                            <span className="status-chip status-chip--warning">HP unknown</span>
                          )}
                          {module.evidence_status === "CATALOG_OBSERVED" ? (
                            <span
                              className="status-chip status-chip--warning"
                              title="Discovery lead from a community catalog. Not verified against the manufacturer."
                            >
                              Unverified lead
                            </span>
                          ) : null}
                          {module.source ? (
                            <span className="status-chip status-chip--neutral">
                              {module.source}
                            </span>
                          ) : null}
                          {module.registry_manufacturer_slug ? (
                            <Link
                              to={`/products?query=${encodeURIComponent(module.registry_manufacturer_slug)}`}
                              className="status-chip status-chip--neutral"
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
                        <p className="catalog-card-meta">{module.category ?? "UTIL"}</p>
                        <p className="module-row__hp">
                          <span className="hp-num">{hp || "?"}</span>
                          <span className="hp-label">HP</span>
                        </p>
                        <div className="module-row__actions">
                          <button
                            className="button button-primary"
                            type="button"
                            disabled={busySlug === module.slug || module.hp == null}
                            title={
                              module.hp == null
                                ? "Needs manufacturer-confirmed HP before placement"
                                : "Load the full module record, then open the builder with it chosen"
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
                            className="button button-quiet"
                            type="button"
                            disabled={busySlug === module.slug || module.hp == null}
                            title="Load the full module record, then choose one of your rigs"
                            onClick={() => void prepareForExistingRig(module)}
                          >
                            Add to existing
                          </button>
                          <Link className="button button-quiet" to="/racks">
                            Open rigs
                          </Link>
                        </div>
                      </li>
                    );
                  })}
                </ul>
              )}

              {totalPages > 1 && state === "ready" ? (
                <nav className="pager" aria-label="Catalog pages">
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
                </nav>
              ) : null}
            </>
          ) : null}
        </div>
      </div>
    </section>
  );
}
