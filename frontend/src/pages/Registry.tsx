/**
 * Public Product Database Explorer (PDB)
 * Manufacturer directory + search + detail — PatchHive workspace chrome.
 */
import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import LoadFailure from "@/components/LoadFailure";
import { ListSkeleton, ReadoutSkeleton } from "@/components/Skeletons";
import { registryApi } from "@/lib/api";
import { isCancelled } from "@/lib/loadError";
import { useAuthStore } from "@/lib/store";
import { useDebouncedValue } from "@/lib/useDebouncedValue";
import type { DeviceModel, Manufacturer, RegistryCoverage } from "@/types/api";

interface SelectedMan extends Manufacturer {
  models?: DeviceModel[];
  /** Why its detail or models didn't load, if they didn't. */
  failure?: unknown;
}

export default function RegistryPage() {
  const [manufacturers, setManufacturers] = useState<Manufacturer[]>([]);
  const [coverage, setCoverage] = useState<RegistryCoverage | null>(null);
  const [searchParams] = useSearchParams();
  const [query, setQuery] = useState(
    () => searchParams.get("query") || searchParams.get("q") || "",
  );
  const [selected, setSelected] = useState<SelectedMan | null>(null);
  const [loading, setLoading] = useState(true);
  const [listError, setListError] = useState<unknown>(null);
  const [attempt, setAttempt] = useState(0);
  const [searchResults, setSearchResults] = useState<DeviceModel[]>([]);
  const [searchError, setSearchError] = useState<unknown>(null);
  const [searchAttempt, setSearchAttempt] = useState(0);
  const searchTerm = useDebouncedValue(query.trim());

  // What the registry returns depends on whether the reader is signed in (owner decision 39).
  // A change of reader drops what the last one got while rendering, so none of it reaches the
  // screen, and the effects below ask again. A token renewal is not a change of reader.
  const signedIn = useAuthStore((st) => st.isAuthenticated());
  const [reader, setReader] = useState(signedIn);
  if (reader !== signedIn) {
    setReader(signedIn);
    setManufacturers([]);
    setCoverage(null);
    setSelected(null);
    setLoading(true);
    setListError(null);
    setSearchResults([]);
    setSearchError(null);
  }

  useEffect(() => {
    let current = true;
    setLoading(true);
    setListError(null);
    Promise.all([registryApi.listManufacturers({ limit: 200 }), registryApi.getCoverage()])
      .then(([mans, cov]) => {
        if (!current) return;
        setManufacturers(mans.data.items.slice(0, 200));
        setCoverage(cov.data);
      })
      .catch((err: unknown) => {
        if (current) setListError(err);
      })
      .finally(() => {
        if (current) setLoading(false);
      });
    return () => {
      current = false;
    };
  }, [attempt, signedIn]);

  // Model search asks once the typing pauses, and a newer search cancels the one before it.
  useEffect(() => {
    setSearchError(null);
    if (!searchTerm) {
      setSearchResults([]);
      return;
    }
    const controller = new AbortController();
    registryApi
      .search(searchTerm, 8, { signal: controller.signal })
      .then((res) => {
        if (!controller.signal.aborted) setSearchResults(res.data.results || []);
      })
      .catch((err: unknown) => {
        if (controller.signal.aborted || isCancelled(err)) return;
        setSearchResults([]);
        setSearchError(err);
      });
    return () => controller.abort();
  }, [searchTerm, searchAttempt, signedIn]);

  const manLabel = (m: Manufacturer) => m.name || m.slug;

  const filtered = manufacturers.filter((m) => {
    const label = manLabel(m).toLowerCase();
    return (
      !query ||
      label.includes(query.toLowerCase()) ||
      m.slug?.toLowerCase().includes(query.toLowerCase())
    );
  });

  // The manufacturer asked for last. Only its answer may land, and a change of reader asks again.
  const latestSelect = useRef<{ manufacturer: Manufacturer } | null>(null);

  const selectMan = async (m: Manufacturer) => {
    const request = { manufacturer: m };
    latestSelect.current = request;
    try {
      const [detail, models] = await Promise.all([
        registryApi.getManufacturer(m.slug),
        registryApi.listModelsForManufacturer(m.slug),
      ]);
      if (latestSelect.current === request) {
        setSelected({ ...detail.data, models: models.data.models });
      }
    } catch (err: unknown) {
      if (latestSelect.current === request) {
        setSelected({ ...m, models: [], failure: err });
      }
    }
  };

  useEffect(() => {
    if (latestSelect.current) void selectMan(latestSelect.current.manufacturer);
  }, [signedIn]);

  return (
    <div className="registry-page">
      <header className="workspace-header">
        <div>
          <h1>Product Database</h1>
          <p className="muted">Live registry of manufacturers and the models they make.</p>
        </div>
        <label className="field registry-search">
          <span className="visually-hidden">Search manufacturers or models</span>
          <input
            className="input"
            placeholder="Search manufacturers or models…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </label>
      </header>

      {searchError ? (
        <LoadFailure
          what="Model search"
          error={searchError}
          onRetry={() => setSearchAttempt((n) => n + 1)}
        />
      ) : null}

      {searchResults.length > 0 ? (
        <div className="panel">
          <h2>Model search</h2>
          <ul className="registry-search-list">
            {searchResults.map((r, i) => (
              <li key={`${r.brand}-${r.name}-${i}`}>
                <span>
                  {r.brand} {r.name}
                </span>
                {r.hp != null ? <code>{r.hp} HP</code> : null}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      <div className="split-workspace registry-split">
        <aside className="split-aside" aria-label="Manufacturers">
          <div className="split-aside-head">
            <h2>Manufacturers</h2>
            {loading || listError ? null : (
              <span className="muted registry-count">
                {filtered.length} of {coverage?.total_manufacturers || manufacturers.length}
              </span>
            )}
          </div>
          <div className="side-list">
            {loading ? (
              <ListSkeleton label="Loading Product Database…" rows={8} />
            ) : listError ? (
              <LoadFailure
                what="The manufacturer list"
                error={listError}
                onRetry={() => setAttempt((n) => n + 1)}
              />
            ) : filtered.length === 0 ? (
              <p className="muted">No matches.</p>
            ) : (
              filtered.map((m) => (
                <button
                  key={m.slug || m.id}
                  type="button"
                  className={`side-item${selected?.slug === m.slug ? " is-selected" : ""}`}
                  onClick={() => void selectMan(m)}
                  aria-current={selected?.slug === m.slug ? "true" : undefined}
                >
                  <span className="side-item-title">{manLabel(m)}</span>
                  <span className="side-item-meta">{m.slug}</span>
                </button>
              ))
            )}
          </div>
        </aside>

        <section className="panel" aria-live="polite">
          {!selected ? (
            <div className="registry-empty">
              <dl className="readout">
                <div>
                  <dt>Manufacturers</dt>
                  <dd>
                    {loading ? (
                      <ReadoutSkeleton />
                    ) : listError ? (
                      "Not loaded"
                    ) : (
                      coverage?.total_manufacturers || manufacturers.length
                    )}
                  </dd>
                </div>
                <div>
                  <dt>Models</dt>
                  <dd>
                    {loading ? (
                      <ReadoutSkeleton />
                    ) : listError ? (
                      "Not loaded"
                    ) : (
                      coverage?.total_models || 0
                    )}
                  </dd>
                </div>
              </dl>
              <p className="muted">Select a manufacturer to inspect registry detail.</p>
            </div>
          ) : (
            <>
              <h2>{manLabel(selected)}</h2>
              <p className="catalog-card-meta">{selected.slug}</p>
              <dl className="registry-detail">
                <div>
                  <dt>Status</dt>
                  <dd>
                    <code>{selected.status || "active"}</code>
                  </dd>
                </div>
                {selected.website ? (
                  <div>
                    <dt>Website</dt>
                    <dd>
                      <a href={selected.website} target="_blank" rel="noreferrer">
                        {selected.website}
                      </a>
                    </dd>
                  </div>
                ) : null}
              </dl>
              <h3>Models (sample)</h3>
              {selected.failure ? (
                <LoadFailure
                  what={`${manLabel(selected)}'s models`}
                  error={selected.failure}
                  onRetry={() => void selectMan(selected)}
                />
              ) : (selected.models || []).length === 0 ? (
                <p className="muted">No models loaded for this manufacturer yet.</p>
              ) : (
                <ul className="registry-model-list">
                  {(selected.models || []).slice(0, 8).map((mod, i) => (
                    <li key={`${mod.name}-${i}`}>
                      <span>{mod.name}</span>
                      {mod.hp != null ? <code>{mod.hp} HP</code> : null}
                    </li>
                  ))}
                </ul>
              )}
            </>
          )}
        </section>
      </div>
    </div>
  );
}
