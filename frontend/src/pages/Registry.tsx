/**
 * Public Product Database Explorer (PDB)
 * Manufacturer directory + search + detail — PatchHive workspace chrome.
 */
import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { registryApi } from "@/lib/api";
import type { DeviceModel, Manufacturer, RegistryCoverage } from "@/types/api";

interface SelectedMan extends Manufacturer {
  models?: DeviceModel[];
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
  const [searchResults, setSearchResults] = useState<DeviceModel[]>([]);

  useEffect(() => {
    Promise.all([registryApi.listManufacturers({ limit: 200 }), registryApi.getCoverage()])
      .then(([mans, cov]) => {
        setManufacturers(mans.data.items.slice(0, 200));
        setCoverage(cov.data);
      })
      .catch(() => undefined)
      .finally(() => setLoading(false));
  }, []);

  const manLabel = (m: Manufacturer) => m.name || m.slug;

  const filtered = manufacturers.filter((m) => {
    const label = manLabel(m).toLowerCase();
    return (
      !query ||
      label.includes(query.toLowerCase()) ||
      m.slug?.toLowerCase().includes(query.toLowerCase())
    );
  });

  const onSearch = async (q: string) => {
    if (!q) {
      setSearchResults([]);
      return;
    }
    try {
      const res = await registryApi.search(q, 8);
      setSearchResults(res.data.results || []);
    } catch {
      setSearchResults([]);
    }
  };

  const selectMan = async (m: Manufacturer) => {
    try {
      const [detail, models] = await Promise.all([
        registryApi.getManufacturer(m.slug),
        registryApi.listModelsForManufacturer(m.slug),
      ]);
      setSelected({ ...detail.data, models: models.data.models });
    } catch {
      setSelected({ ...m, models: [] });
    }
  };

  if (loading) {
    return (
      <div className="panel">
        <p className="status">Loading Product Database…</p>
      </div>
    );
  }

  return (
    <div className="registry-page">
      <header className="workspace-header">
        <div>
          <p className="eyebrow">Catalog</p>
          <h1>Product Database</h1>
          <p className="muted">
            Live registry · {coverage?.total_manufacturers || manufacturers.length} manufacturers ·{" "}
            {coverage?.total_models || 0} models
          </p>
        </div>
        <label className="field" style={{ minWidth: "min(18rem, 100%)" }}>
          <span className="visually-hidden">Search manufacturers or models</span>
          <input
            className="input"
            placeholder="Search manufacturers or models…"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              void onSearch(e.target.value);
            }}
          />
        </label>
      </header>

      {searchResults.length > 0 ? (
        <div className="panel" style={{ marginBottom: "var(--space-5)" }}>
          <p className="eyebrow">Model search</p>
          <ul className="registry-search-list">
            {searchResults.map((r, i) => (
              <li key={`${r.brand}-${r.name}-${i}`}>
                <span>
                  {r.brand} — {r.name}
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
            <span className="muted" style={{ fontSize: "0.8rem" }}>
              {filtered.length}/{manufacturers.length}
            </span>
          </div>
          <div className="side-list">
            {filtered.length === 0 ? (
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
            <p className="muted">Select a manufacturer to inspect registry detail.</p>
          ) : (
            <>
              <p className="eyebrow">Manufacturer</p>
              <h2 style={{ marginTop: 0 }}>{manLabel(selected)}</h2>
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
              <p className="eyebrow" style={{ marginTop: "var(--space-5)" }}>
                Models (sample)
              </p>
              {(selected.models || []).length === 0 ? (
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
