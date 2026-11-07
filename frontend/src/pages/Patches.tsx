/**
 * Patches list — browse generated patches with loading / empty / error parity.
 */
import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import LoadFailure from "@/components/LoadFailure";
import ShowMore from "@/components/ShowMore";
import { ListSkeleton } from "@/components/Skeletons";
import { patchApi } from "@/lib/api";
import { patchName } from "@/lib/patchName";
import { useReaderKey } from "@/lib/store";
import type { Patch } from "@/types/api";

type LoadState = "loading" | "ready" | "empty" | "error";

const PAGE_SIZE = 100;

export default function PatchesPage() {
  return <Patches key={useReaderKey()} />;
}

function Patches() {
  const [patches, setPatches] = useState<Patch[]>([]);
  const [total, setTotal] = useState(0);
  const [state, setState] = useState<LoadState>("loading");
  const [error, setError] = useState<unknown>(null);
  const [category, setCategory] = useState("");
  const [loadingMore, setLoadingMore] = useState(false);
  const [moreError, setMoreError] = useState<unknown>(null);
  // Only the latest request may update the list, so a slow answer for an earlier filter
  // cannot replace the one chosen after it.
  const request = useRef(0);

  const load = async () => {
    const mine = ++request.current;
    setState("loading");
    setError(null);
    setMoreError(null);
    try {
      const response = await patchApi.list({
        limit: PAGE_SIZE,
        category: category || undefined,
      });
      if (mine !== request.current) return;
      const rows = response.data.patches ?? [];
      setPatches(rows);
      setTotal(response.data.total ?? rows.length);
      setState(rows.length === 0 ? "empty" : "ready");
    } catch (err: unknown) {
      if (mine !== request.current) return;
      setPatches([]);
      setTotal(0);
      setError(err);
      setState("error");
    }
  };

  const loadMore = async () => {
    const mine = request.current;
    setLoadingMore(true);
    setMoreError(null);
    try {
      const response = await patchApi.list({
        skip: patches.length,
        limit: PAGE_SIZE,
        category: category || undefined,
      });
      if (mine !== request.current) return;
      setPatches((shown) => [...shown, ...(response.data.patches ?? [])]);
      if (response.data.total != null) setTotal(response.data.total);
    } catch (err: unknown) {
      if (mine === request.current) setMoreError(err);
    } finally {
      setLoadingMore(false);
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
        <LoadFailure what="Patches" error={error} onRetry={() => void load()} />
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
                  <h2>
                    <Link to={`/rigs/${patch.rack_id}/patches/${patch.id}`}>
                      {patchName(patch)}
                    </Link>
                  </h2>
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
          <ShowMore
            shown={patches.length}
            total={total}
            noun="patches"
            loading={loadingMore}
            error={moreError}
            onMore={() => void loadMore()}
          />
        </>
      ) : null}
    </section>
  );
}
