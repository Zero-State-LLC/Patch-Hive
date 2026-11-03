/**
 * Patches list — browse generated patches with loading / empty / error parity.
 */
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ListSkeleton } from "@/components/Skeletons";
import { patchApi } from "@/lib/api";
import type { Patch } from "@/types/api";

type LoadState = "loading" | "ready" | "empty" | "error";

export default function PatchesPage() {
  const [patches, setPatches] = useState<Patch[]>([]);
  const [total, setTotal] = useState(0);
  const [state, setState] = useState<LoadState>("loading");
  const [error, setError] = useState("");
  const [category, setCategory] = useState("");

  const load = async () => {
    setState("loading");
    setError("");
    try {
      const response = await patchApi.list({
        limit: 100,
        category: category || undefined,
      });
      const rows = response.data.patches ?? [];
      setPatches(rows);
      setTotal(response.data.total ?? rows.length);
      setState(rows.length === 0 ? "empty" : "ready");
    } catch {
      setPatches([]);
      setTotal(0);
      setError("Unable to load patches. Generate a run from a rig, then refresh.");
      setState("error");
    }
  };

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- reload when category filter changes
  }, [category]);

  return (
    <section aria-labelledby="patches-title">
      <header className="workspace-header">
        <div>
          <h1 id="patches-title">Patches</h1>
          <p className="muted">
            Generated patches constrained to confirmed inventory. Exports remain the credit
            boundary.
          </p>
        </div>
        <div className="header-actions toolbar">
          <label className="inline-field" htmlFor="patch-category">
            Category
            <select
              id="patch-category"
              value={category}
              onChange={(event) => setCategory(event.target.value)}
            >
              <option value="">All</option>
              <option value="Voice">Voice</option>
              <option value="Modulation">Modulation</option>
              <option value="Clock-Rhythm">Clock-Rhythm</option>
              <option value="Generative">Generative</option>
              <option value="Utility">Utility</option>
              <option value="Texture-FX">Texture-FX</option>
            </select>
          </label>
          <button className="button button-secondary" type="button" onClick={() => void load()}>
            Refresh
          </button>
        </div>
      </header>

      {state === "loading" ? <ListSkeleton label="Loading patches…" rows={5} /> : null}

      {state === "error" ? (
        <div className="panel" role="alert">
          <p className="status status-danger">{error}</p>
          <div className="page-hero-actions">
            <button className="button button-primary" type="button" onClick={() => void load()}>
              Retry
            </button>
            <Link className="button button-quiet" to="/racks">
              Open rigs
            </Link>
          </div>
        </div>
      ) : null}

      {state === "empty" ? (
        <div className="panel">
          <p className="empty-title">No patches match this filter.</p>
          <p className="muted">
            Generate patches from a rig with confirmed modules, or clear the category filter.
          </p>
          <Link className="button button-primary" to="/racks">
            Go to rigs
          </Link>
        </div>
      ) : null}

      {state === "ready" ? (
        <>
          <p className="muted results-meta" role="status">
            Showing {patches.length} of {total} patches
          </p>
          <ul className="patch-rows">
            {patches.map((patch) => (
              <li key={patch.id} className="patch-row">
                <div className="patch-row__main">
                  <h2>{patch.name_override || patch.suggested_name || patch.name}</h2>
                  {patch.description ? (
                    <p className="patch-row__desc">{patch.description}</p>
                  ) : null}
                  <p className="catalog-card-meta">
                    Rack #{patch.rack_id}
                    {patch.run_id != null ? `, run #${patch.run_id}` : ""}, seed{" "}
                    {patch.generation_seed}, {patch.generation_version}
                  </p>
                </div>
                <dl className="patch-row__facts">
                  <div>
                    <dt>Category</dt>
                    <dd>{patch.category}</dd>
                  </div>
                  {patch.difficulty ? (
                    <div>
                      <dt>Difficulty</dt>
                      <dd>{patch.difficulty}</dd>
                    </div>
                  ) : null}
                  <div>
                    <dt>Cables</dt>
                    <dd className="patch-row__figure">{patch.connections?.length ?? 0}</dd>
                  </div>
                </dl>
                <Link
                  className="button button-quiet"
                  to={`/racks/${patch.rack_id}?tab=patches&patch=${patch.id}`}
                >
                  Open rig
                </Link>
              </li>
            ))}
          </ul>
        </>
      ) : null}
    </section>
  );
}
