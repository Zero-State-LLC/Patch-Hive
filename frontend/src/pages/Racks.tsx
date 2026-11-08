import { useEffect, useMemo, useRef, useState } from "react";
import type { CSSProperties } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { canonApi, exportApi, patchApi, rackApi, runApi } from "@/lib/api";
import { filenameFromDisposition, saveBlob } from "@/lib/download";
import { useAuthStore, useReaderKey } from "@/lib/store";
import { useMountedRef } from "@/lib/useMountedRef";
import PatchRail from "@/components/PatchRail";
import RigRail from "@/components/RigRail";
import Tabs from "@/components/Tabs";
import ShowMore from "@/components/ShowMore";
import { ListSkeleton, RailSkeleton } from "@/components/Skeletons";
import type { CompatibilityResponse, Patch, Rack, Run } from "@/types/api";
import { rigDetailToRack, rigSummaryToRack } from "@/lib/canonRigAdapter";
import { formatDate, runLabel } from "@/lib/format";
import { patchName } from "@/lib/patchName";
import { panelId, tabId } from "@/lib/tabs";
import {
  difficultyFromConnections,
  filterPatches,
  patchCategories,
  weirdnessFromConnections,
} from "./racksPageUtils";

type TabKey = "overview" | "patches" | "exports" | "modules";

function isTabKey(value: string | null): value is TabKey {
  return value === "overview" || value === "patches" || value === "exports" || value === "modules";
}

/** A positive integer from a URL segment or query value, or null. */
function idFrom(value: string | null | undefined): number | null {
  return value && /^[1-9]\d*$/.test(value) ? Number(value) : null;
}

const RIG_PAGE_SIZE = 50;

const tabs: { key: TabKey; label: string }[] = [
  { key: "overview", label: "Overview" },
  { key: "patches", label: "Patches" },
  { key: "exports", label: "Exports" },
  { key: "modules", label: "Module gallery" },
];

function gateTone(status?: string | null): "success" | "warning" | "danger" | "neutral" {
  if (!status) return "neutral";
  const s = status.toLowerCase();
  if (s === "verified" || s === "ok" || s === "pass") return "success";
  if (s === "incomplete" || s === "warning" || s === "unknown") return "warning";
  if (s === "conflict" || s === "fail" || s === "error") return "danger";
  return "neutral";
}

export default function RacksPage() {
  return <Racks key={useReaderKey()} />;
}

function Racks() {
  const mounted = useMountedRef();
  const [racks, setRacks] = useState<Rack[]>([]);
  const [rackTotal, setRackTotal] = useState(0);
  const [loadingMoreRigs, setLoadingMoreRigs] = useState(false);
  const [moreRigsError, setMoreRigsError] = useState<unknown>(null);
  // Users own their racks: only the owner can generate patches for one.
  const currentUserId = useAuthStore((st) => st.user?.id ?? null);
  const [pdfDownloading, setPdfDownloading] = useState(false);
  const [pdfError, setPdfError] = useState<string | null>(null);
  // The selected rig, tab and patch live in the URL (/racks/:rigId?tab=&patch=), so a view
  // can be linked to, reloaded and reached with the back button.
  const navigate = useNavigate();
  const { rigId } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const selectedRackId = idFrom(rigId);
  const tabParam = searchParams.get("tab");
  const requestedTab: TabKey = isTabKey(tabParam) ? tabParam : "overview";
  const selectedPatchId = idFrom(searchParams.get("patch"));
  const selectRig = (id: number, options?: { replace?: boolean }) =>
    navigate({ pathname: `/racks/${id}` }, options);
  const setActiveTab = (tab: TabKey) =>
    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        if (tab === "overview") next.delete("tab");
        else next.set("tab", tab);
        if (tab !== "patches") next.delete("patch");
        return next;
      },
      { replace: true },
    );
  const setSelectedPatchId = (id: number) =>
    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        next.set("patch", String(id));
        return next;
      },
      { replace: true },
    );
  const [rackDetail, setRackDetail] = useState<Rack | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);
  const detailRequest = useRef(0);
  // The same guard for a rig's runs and a run's patches: a slow answer for a rig or run chosen
  // earlier never replaces the one chosen after it.
  const runsRequest = useRef(0);
  const patchesRequest = useRef(0);
  const [runs, setRuns] = useState<Run[]>([]);
  const [selectedRunId, setSelectedRunId] = useState<number | null>(null);
  const [patches, setPatches] = useState<Patch[]>([]);
  const [loading, setLoading] = useState(false);
  const [listLoading, setListLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filters, setFilters] = useState({
    category: "All",
    difficulty: "All",
    weirdness: "Any",
  });
  const [compat, setCompat] = useState<{
    bridge_status: string;
    message: string;
    catalog_slug?: string | null;
    compatibility?: CompatibilityResponse | null;
  } | null>(null);
  const [compatLoading, setCompatLoading] = useState(false);

  // Spec 008 F5: list rows come from GET /api/canon/rigs (no placements); the
  // selected rig's placements come from GET /api/canon/rigs/{rig_id}.
  const selectedRack = useMemo(
    () => (rackDetail && rackDetail.id === selectedRackId ? rackDetail : null),
    [rackDetail, selectedRackId],
  );

  const inventoryPower = useMemo(() => {
    if (!selectedRack) {
      return { known: 0, unknown: 0, draw12: 0, drawN12: 0, draw5: 0 };
    }
    let known = 0;
    let unknown = 0;
    let draw12 = 0;
    let drawN12 = 0;
    let draw5 = 0;
    for (const rm of selectedRack.modules) {
      const mod = rm.module;
      if (!mod || mod.power_12v_ma == null) {
        unknown += 1;
        continue;
      }
      known += 1;
      draw12 += mod.power_12v_ma || 0;
      drawN12 += mod.power_neg12v_ma || 0;
      draw5 += mod.power_5v_ma || 0;
    }
    return { known, unknown, draw12, drawN12, draw5 };
  }, [selectedRack]);

  const hasRuns = runs.length > 0;
  // Patches and Exports need a run; a link to them on a rig without one opens the Overview.
  const activeTab: TabKey =
    (requestedTab === "patches" || requestedTab === "exports") && !hasRuns
      ? "overview"
      : requestedTab;

  const loadRacks = async () => {
    setError(null);
    setListLoading(true);
    try {
      const response = await canonApi.listRigs({ limit: RIG_PAGE_SIZE });
      // Past here the page may move to the reader's first rig, which the next reader can't open.
      if (!mounted.current) return;
      const rows = response.data.rigs.map(rigSummaryToRack);
      setRacks(rows);
      setRackTotal(response.data.total ?? rows.length);
      setMoreRigsError(null);
      if (rows.length && selectedRackId === null) {
        selectRig(rows[0].id, { replace: true });
      } else if (selectedRackId !== null) {
        void loadRackDetail(selectedRackId);
      }
    } catch {
      setRacks([]);
      setError("Unable to load rigs. Please try again.");
    } finally {
      setListLoading(false);
    }
  };

  const loadMoreRacks = async () => {
    setLoadingMoreRigs(true);
    setMoreRigsError(null);
    try {
      const response = await canonApi.listRigs({ skip: racks.length, limit: RIG_PAGE_SIZE });
      const rows = response.data.rigs.map(rigSummaryToRack);
      // A rig created meanwhile shifts the pages, so one already shown is not added twice.
      setRacks((shown) => [
        ...shown,
        ...rows.filter((row) => !shown.some((rig) => rig.id === row.id)),
      ]);
      if (response.data.total != null) setRackTotal(response.data.total);
    } catch (err: unknown) {
      setMoreRigsError(err);
    } finally {
      setLoadingMoreRigs(false);
    }
  };

  const loadRackDetail = async (rackId: number) => {
    // Only the latest request may update state, so a slow earlier response
    // cannot replace the detail of the rig selected after it.
    const request = ++detailRequest.current;
    setDetailError(null);
    try {
      const response = await canonApi.getRig(rackId);
      if (request !== detailRequest.current) return;
      setRackDetail(rigDetailToRack(response.data));
    } catch {
      if (request !== detailRequest.current) return;
      setRackDetail(null);
      // Rendered in the workspace itself (independent of selectedRack) with a
      // retry that re-requests this rig directly.
      setDetailError("Unable to load rig details. Please try again.");
    }
  };

  const loadRuns = async (rackId: number) => {
    const request = ++runsRequest.current;
    try {
      const response = await canonApi.listRuns(rackId);
      if (request !== runsRequest.current) return response.data.runs;
      setRuns(response.data.runs);
      if (response.data.runs.length) {
        setSelectedRunId(response.data.runs[0].id);
      } else {
        setSelectedRunId(null);
      }
      return response.data.runs;
    } catch {
      if (request !== runsRequest.current) return [];
      setRuns([]);
      setSelectedRunId(null);
      return [];
    }
  };

  const loadCompat = async (rackId: number) => {
    setCompatLoading(true);
    try {
      const res = await rackApi.compatibility(rackId);
      setCompat(res.data);
    } catch {
      setCompat(null);
    } finally {
      setCompatLoading(false);
    }
  };

  const loadPatches = async (runId: number) => {
    const request = ++patchesRequest.current;
    try {
      const response = await runApi.patches(runId);
      if (request === patchesRequest.current) setPatches(response.data.patches);
    } catch {
      if (request === patchesRequest.current) setPatches([]);
    }
  };

  const handleRackPdf = async (rackId: number) => {
    setPdfDownloading(true);
    setPdfError(null);
    try {
      const res = await exportApi.downloadRackPdf(rackId);
      // A file saved after sign-out would hand the last reader's PDF to whoever is here now.
      if (!mounted.current) return;
      saveBlob(
        res.data,
        filenameFromDisposition(res.headers["content-disposition"], `rack_${rackId}.pdf`),
      );
    } catch {
      setPdfError(
        "Could not download the PDF. Only the rig's owner (or a public rig) can export it.",
      );
    } finally {
      setPdfDownloading(false);
    }
  };

  const handleGenerate = async () => {
    if (!selectedRack) return;
    setLoading(true);
    setError(null);
    try {
      await patchApi.generate(selectedRack.id, {});
      const latestRuns = await loadRuns(selectedRack.id);
      if (latestRuns[0]?.id) {
        await loadPatches(latestRuns[0].id);
      }
      if (mounted.current) setActiveTab("patches");
    } catch {
      setError("Patch generation failed. Please retry.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadRacks();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (selectedRackId !== null) {
      void loadRackDetail(selectedRackId);
      void loadRuns(selectedRackId);
      void loadCompat(selectedRackId);
    } else {
      setCompat(null);
    }
  }, [selectedRackId]);

  useEffect(() => {
    if (selectedRunId !== null) {
      void loadPatches(selectedRunId);
    } else {
      setPatches([]);
    }
  }, [selectedRunId]);

  const categories = useMemo(() => patchCategories(patches), [patches]);
  const filteredPatches = useMemo(() => filterPatches(patches, filters), [patches, filters]);
  const selectedPatch =
    filteredPatches.find((p) => p.id === selectedPatchId) ?? filteredPatches[0] ?? null;

  return (
    <div className="split-workspace">
      <aside className="split-aside" aria-label="Rig list">
        <div className="split-aside-head">
          <h1>Rigs</h1>
          <Link className="button button-primary" to="/racks/new">
            New
          </Link>
        </div>
        <p className="muted" style={{ margin: 0, fontSize: "0.9rem" }}>
          Rig-centric workspace. Each rig carries runs and patch libraries.
        </p>
        <div className="side-list">
          {listLoading ? <ListSkeleton label="Loading rigs…" /> : null}
          {!listLoading && error && racks.length === 0 ? (
            <div className="panel" role="alert">
              <p className="status status-danger">{error}</p>
              <button
                className="button button-secondary"
                type="button"
                onClick={() => void loadRacks()}
              >
                Retry
              </button>
            </div>
          ) : null}
          {!listLoading
            ? racks.map((rack) => (
                <button
                  key={rack.id}
                  type="button"
                  className={`side-item${rack.id === selectedRackId ? " is-selected" : ""}`}
                  aria-current={rack.id === selectedRackId ? "true" : undefined}
                  onClick={() => selectRig(rack.id)}
                >
                  <span className="side-item-title">{rack.name}</span>
                  {rack.name_suggested && rack.name_suggested !== rack.name ? (
                    <span className="side-item-meta">Suggested: {rack.name_suggested}</span>
                  ) : null}
                </button>
              ))
            : null}
          {!listLoading ? (
            <ShowMore
              shown={racks.length}
              total={rackTotal}
              noun="rigs"
              loading={loadingMoreRigs}
              error={moreRigsError}
              onMore={() => void loadMoreRacks()}
            />
          ) : null}
          {!listLoading && racks.length === 0 && !error ? (
            <div className="panel">
              <p className="status status-warning">No rigs yet.</p>
              <Link className="button button-primary" to="/racks/new">
                Create your first rig
              </Link>
            </div>
          ) : null}
        </div>
      </aside>

      <section aria-label="Selected rig workspace">
        {selectedRack ? (
          <>
            <header className="workspace-header">
              <div>
                <h2>{selectedRack.name}</h2>
                <p className="muted">{selectedRack.description || "No rig notes yet."}</p>
              </div>
              <div className="header-actions">
                <Link className="button button-secondary" to={`/rigs/${selectedRack.id}`}>
                  Revisions and runs
                </Link>
              </div>
            </header>

            <Tabs
              label="Rig sections"
              idPrefix="rig-"
              tabs={tabs.map((tab) => ({
                ...tab,
                disabled: (tab.key === "patches" || tab.key === "exports") && !hasRuns,
              }))}
              active={activeTab}
              onChange={setActiveTab}
            />

            {error ? (
              <div className="panel" role="alert" style={{ marginBottom: "var(--space-4)" }}>
                <p className="status status-danger">{error}</p>
              </div>
            ) : null}

            {activeTab === "overview" ? (
              <div
                className="rack-tabpanel"
                role="tabpanel"
                id={panelId("rig-", "overview")}
                aria-labelledby={tabId("rig-", "overview")}
                tabIndex={0}
              >
                {selectedRack.modules.length === 0 ? (
                  <div className="panel placement-cta" role="region" aria-label="Place modules">
                    <h3>This rig has no modules yet</h3>
                    <p className="muted">
                      Place catalog modules by row and start HP, or photograph the Rig and confirm
                      what PatchHive reads.
                    </p>
                    <div className="page-hero-actions">
                      <Link className="button button-primary" to={`/racks/${selectedRack.id}/edit`}>
                        Place modules
                      </Link>
                      <Link
                        className="button button-secondary"
                        to={`/rigs/${selectedRack.id}/photo`}
                      >
                        Photograph this Rig
                      </Link>
                    </div>
                  </div>
                ) : null}

                <div className="panel">
                  <h3>Rig inventory</h3>
                  <dl className="readout">
                    <div>
                      <dt>Modules</dt>
                      <dd>{selectedRack.modules.length}</dd>
                    </div>
                    <div>
                      <dt>Runs</dt>
                      <dd>{runs.length}</dd>
                    </div>
                    <div className="readout-wide">
                      <dt>Latest run</dt>
                      <dd>{runs[0] ? formatDate(runs[0].created_at) : "None yet"}</dd>
                    </div>
                  </dl>
                  {selectedRack.case ? (
                    <p className="muted">
                      Case: {selectedRack.case.brand} {selectedRack.case.name}
                      {selectedRack.case.catalog_slug
                        ? `, catalog ${selectedRack.case.catalog_slug}`
                        : ", not linked to normalized catalog"}
                      {selectedRack.case.total_hp != null
                        ? `, ${selectedRack.case.total_hp}HP`
                        : ""}
                    </p>
                  ) : null}
                  <RigRail rack={selectedRack} />
                  {selectedRack.modules.length > 0 ? (
                    <div
                      className="power-rail-panel"
                      style={{ marginTop: "var(--space-3)" }}
                      aria-label="Inventory power summary"
                    >
                      <p className="muted" style={{ margin: 0, fontSize: "0.9rem" }}>
                        Power known on <strong>{inventoryPower.known}</strong>/
                        {selectedRack.modules.length} modules
                        {inventoryPower.unknown
                          ? `, ${inventoryPower.unknown} unknown (not assumed)`
                          : ""}
                      </p>
                      {selectedRack.case ? (
                        <div className="power-rail-meters" aria-label="Inventory power rails">
                          {(
                            [
                              {
                                rail: "+12V",
                                draw: inventoryPower.draw12,
                                cap: selectedRack.case.power_12v_ma,
                              },
                              {
                                rail: "−12V",
                                draw: inventoryPower.drawN12,
                                cap: selectedRack.case.power_neg12v_ma,
                              },
                              {
                                rail: "+5V",
                                draw: inventoryPower.draw5,
                                cap: selectedRack.case.power_5v_ma,
                              },
                            ] as const
                          ).map((r) => {
                            const tone =
                              r.cap == null
                                ? "neutral"
                                : r.draw > r.cap
                                  ? "danger"
                                  : r.cap > 0 && r.draw / r.cap >= 0.85
                                    ? "warning"
                                    : "success";
                            const fill =
                              r.cap == null || r.cap <= 0 ? 0 : Math.min(1, r.draw / r.cap);
                            return (
                              <div key={r.rail} className="power-rail-meters__row">
                                <span className={`status-chip status-chip--${tone}`}>
                                  {r.rail} {r.cap == null ? `${r.draw}mA` : `${r.draw}/${r.cap}mA`}
                                </span>
                                <div
                                  className="usage-bar"
                                  role="meter"
                                  aria-valuemin={0}
                                  aria-valuemax={r.cap ?? 0}
                                  aria-valuenow={r.draw}
                                  aria-label={`${r.rail} inventory draw`}
                                >
                                  <div
                                    className={`usage-bar__fill usage-bar__fill--${tone}`}
                                    style={{ "--fill": fill } as CSSProperties}
                                  />
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      ) : null}
                    </div>
                  ) : null}
                  {selectedRack.modules.length > 0 ? (
                    <div className="page-hero-actions" style={{ marginTop: "var(--space-3)" }}>
                      <Link
                        className="button button-secondary"
                        to={`/racks/${selectedRack.id}/edit`}
                      >
                        Edit placements
                      </Link>
                    </div>
                  ) : null}
                </div>

                <div className="panel" aria-live="polite">
                  <h3>Case fit report</h3>
                  {compatLoading ? (
                    <p className="muted">Loading compatibility…</p>
                  ) : compat ? (
                    <>
                      <p>
                        Bridge: <strong>{compat.bridge_status}</strong>
                        {compat.catalog_slug ? ` (${compat.catalog_slug})` : ""}
                      </p>
                      <p className="muted">{compat.message}</p>
                      {compat.compatibility ? (
                        <>
                          <div className="gate-chip-row" aria-label="Dual-gate summary">
                            <span
                              className={`status-chip status-chip--${gateTone(compat.compatibility.overall_status)}`}
                            >
                              overall: {compat.compatibility.overall_status}
                            </span>
                            <span
                              className={`status-chip status-chip--${gateTone(compat.compatibility.physical_fit.status)}`}
                            >
                              physical: {compat.compatibility.physical_fit.status}
                            </span>
                            <span
                              className={`status-chip status-chip--${gateTone(compat.compatibility.connector_availability.status)}`}
                            >
                              connectors: {compat.compatibility.connector_availability.status}
                            </span>
                            <span
                              className={`status-chip status-chip--${gateTone(compat.compatibility.format_check.status)}`}
                            >
                              format: {compat.compatibility.format_check.status}
                            </span>
                            {compat.compatibility.power_headroom?.map((r) => (
                              <span
                                key={r.rail}
                                className={`status-chip status-chip--${gateTone(r.status)}`}
                                title={
                                  r.headroom_ma != null && !r.unknown_draw_count
                                    ? `headroom ${r.headroom_ma}mA`
                                    : r.message
                                }
                              >
                                {r.rail}: {r.status}
                              </span>
                            ))}
                          </div>
                          {compat.compatibility.overall_status === "incomplete" ? (
                            <p className="muted" style={{ fontSize: "0.9rem" }}>
                              Soft gaps only: missing power, depth or case rails stay missing, never
                              invented.
                            </p>
                          ) : null}
                          {compat.compatibility.overall_status === "conflict" ? (
                            <p className="status status-danger" style={{ fontSize: "0.9rem" }}>
                              Hard fail: overflow, connectors, or a rail over budget.
                            </p>
                          ) : null}
                          {compat.compatibility.warnings?.length ? (
                            <p className="status status-warning" style={{ fontSize: "0.9rem" }}>
                              {compat.compatibility.warnings.length} soft warning
                              {compat.compatibility.warnings.length === 1 ? "" : "s"}
                              {compat.compatibility.warnings[0]?.code
                                ? `, e.g. ${compat.compatibility.warnings[0].code}`
                                : ""}
                            </p>
                          ) : null}
                          <details style={{ marginTop: "var(--space-2)" }}>
                            <summary className="muted" style={{ cursor: "pointer" }}>
                              Full dual-gate detail
                            </summary>
                            <ul>
                              <li>
                                Format: {compat.compatibility.format_check.status}
                                {compat.compatibility.format_check.message
                                  ? `: ${compat.compatibility.format_check.message}`
                                  : ""}
                              </li>
                              <li>Physical fit: {compat.compatibility.physical_fit.status}</li>
                              <li>
                                Connectors: {compat.compatibility.connector_availability.status}
                                {compat.compatibility.connector_availability.message
                                  ? `: ${compat.compatibility.connector_availability.message}`
                                  : ""}
                              </li>
                              <li>+5V: {compat.compatibility.pos5_compatibility.status}</li>
                              {compat.compatibility.power_headroom?.map((r) => (
                                <li key={r.rail}>
                                  {r.rail}: {r.status}
                                  {r.unknown_draw_count
                                    ? `. ${r.message}`
                                    : r.headroom_ma != null
                                      ? `, headroom ${r.headroom_ma}mA`
                                      : ""}
                                </li>
                              ))}
                            </ul>
                          </details>
                        </>
                      ) : null}
                    </>
                  ) : (
                    <p className="muted">Compatibility unavailable for this rig.</p>
                  )}
                </div>

                <div className="panel">
                  <div className="page-hero-actions">
                    <button
                      type="button"
                      className="button button-primary"
                      onClick={() => void handleGenerate()}
                      disabled={
                        loading ||
                        selectedRack.modules.length === 0 ||
                        currentUserId !== selectedRack.user_id
                      }
                      title={
                        currentUserId !== selectedRack.user_id
                          ? "Only the rig's owner can generate patches"
                          : selectedRack.modules.length === 0
                            ? "Place at least one module before generating"
                            : undefined
                      }
                    >
                      {loading ? "Generating…" : "Generate patch library"}
                    </button>
                    <Link className="button button-secondary" to={`/racks/${selectedRack.id}/edit`}>
                      Place modules
                    </Link>
                    <Link className="button button-secondary" to="/racks/new">
                      Create rig
                    </Link>
                    <button type="button" className="button button-quiet" disabled>
                      Upload rig (soon)
                    </button>
                  </div>
                  <p className="muted" style={{ marginBottom: 0, marginTop: "var(--space-3)" }}>
                    Generate once. Patches and exports open as tabs after a run exists. Placement
                    uses catalog compatibility when the case is materialized.
                  </p>
                </div>
              </div>
            ) : null}

            {activeTab === "patches" ? (
              <div
                className="rack-patches"
                role="tabpanel"
                id={panelId("rig-", "patches")}
                aria-labelledby={tabId("rig-", "patches")}
                tabIndex={0}
              >
                <div className="toolbar" aria-label="Patch filters">
                  <label className="inline-field">
                    Category
                    <select
                      value={filters.category}
                      onChange={(event) =>
                        setFilters((prev) => ({ ...prev, category: event.target.value }))
                      }
                    >
                      <option>All</option>
                      {categories.map((category) => (
                        <option key={category}>{category}</option>
                      ))}
                    </select>
                  </label>
                  <label className="inline-field">
                    Difficulty
                    <select
                      value={filters.difficulty}
                      onChange={(event) =>
                        setFilters((prev) => ({ ...prev, difficulty: event.target.value }))
                      }
                    >
                      <option>All</option>
                      <option>Beginner</option>
                      <option>Intermediate</option>
                      <option>Advanced</option>
                    </select>
                  </label>
                  <label className="inline-field">
                    Weirdness
                    <select
                      value={filters.weirdness}
                      onChange={(event) =>
                        setFilters((prev) => ({ ...prev, weirdness: event.target.value }))
                      }
                    >
                      <option>Any</option>
                      <option>Low</option>
                      <option>Medium</option>
                      <option>High</option>
                    </select>
                  </label>
                  <label className="inline-field">
                    Run
                    <select
                      value={selectedRunId ?? ""}
                      onChange={(event) => setSelectedRunId(Number(event.target.value))}
                      disabled={!hasRuns}
                    >
                      {runs.map((run) => (
                        <option key={run.id} value={run.id}>
                          {runLabel(run)}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>

                {filteredPatches.length === 0 ? (
                  <div className="screen-state">
                    <p className="empty-title">No patches yet. Generate a run.</p>
                  </div>
                ) : (
                  <div className="split-workspace">
                    <ul className="side-list rack-patch-list" aria-label="Patches in this run">
                      {filteredPatches.map((patch) => (
                        <li key={patch.id}>
                          <button
                            type="button"
                            className={`side-item${selectedPatch?.id === patch.id ? " is-selected" : ""}`}
                            aria-current={selectedPatch?.id === patch.id ? "true" : undefined}
                            onClick={() => setSelectedPatchId(patch.id)}
                          >
                            <span className="side-item-title">{patchName(patch)}</span>
                            <span className="side-item-meta">
                              {patch.category}, {difficultyFromConnections(patch)}, weirdness{" "}
                              {weirdnessFromConnections(patch)}
                            </span>
                          </button>
                        </li>
                      ))}
                    </ul>
                    {selectedPatch ? (
                      <section className="rack-patch-detail" aria-labelledby="rack-patch-title">
                        <h3 id="rack-patch-title">{patchName(selectedPatch)}</h3>
                        <p>{selectedPatch.description || "No description yet."}</p>
                        <Link
                          className="button button-quiet"
                          to={`/rigs/${selectedRack.id}/patches/${selectedPatch.id}`}
                        >
                          Open patch
                        </Link>
                        <PatchRail rack={selectedRack} patch={selectedPatch} />
                      </section>
                    ) : null}
                  </div>
                )}
              </div>
            ) : null}

            {activeTab === "exports" ? (
              <div
                className="panel"
                role="tabpanel"
                id={panelId("rig-", "exports")}
                aria-labelledby={tabId("rig-", "exports")}
                tabIndex={0}
              >
                <h3>PatchBook exports</h3>
                <p className="muted">
                  Export actions trigger credit checks at download time. Credits debit only at the
                  canonical boundary.
                </p>
                <div className="page-hero-actions">
                  <button
                    type="button"
                    className="button button-primary"
                    onClick={() => void handleRackPdf(selectedRack.id)}
                    disabled={pdfDownloading}
                  >
                    {pdfDownloading ? "Preparing PDF…" : "Export Patch Book PDF"}
                  </button>
                  <button type="button" className="button button-quiet" disabled>
                    Export selected patches
                  </button>
                  <button type="button" className="button button-quiet" disabled>
                    Export SVG zip
                  </button>
                </div>
                {pdfError ? (
                  <p className="status status-danger" role="alert">
                    {pdfError}
                  </p>
                ) : null}
              </div>
            ) : null}

            {activeTab === "modules" ? (
              <div
                className="catalog-grid"
                role="tabpanel"
                id={panelId("rig-", "modules")}
                aria-labelledby={tabId("rig-", "modules")}
                tabIndex={0}
              >
                {selectedRack.modules.map((module) => (
                  <article key={module.id} className="catalog-card">
                    <h4>{module.module?.name || "Unknown module"}</h4>
                    <p className="catalog-card-meta">
                      {module.module?.brand || "Unknown brand"},{" "}
                      {module.module?.module_type || "type unknown"}, {module.module?.hp ?? "?"}HP
                      {module.module?.depth_mm != null
                        ? `, depth ${module.module.depth_mm}mm`
                        : ", depth unspecified"}
                    </p>
                    <p className="muted" style={{ margin: 0, fontSize: "0.85rem" }}>
                      Row {module.row_index}, start HP {module.start_hp}
                      {module.module?.power_12v_ma != null
                        ? `, +12 ${module.module.power_12v_ma}mA`
                        : ""}
                    </p>
                  </article>
                ))}
                {selectedRack.modules.length === 0 ? (
                  <div className="panel">
                    <p className="status status-warning">No modules loaded for this rig.</p>
                    <Link className="button button-secondary" to={`/racks/${selectedRack.id}/edit`}>
                      Place modules
                    </Link>
                  </div>
                ) : (
                  <div className="panel">
                    <Link className="button button-secondary" to={`/racks/${selectedRack.id}/edit`}>
                      Edit placements
                    </Link>
                  </div>
                )}
              </div>
            ) : null}
          </>
        ) : selectedRackId !== null && detailError ? (
          <div className="panel" role="alert">
            <p className="status status-danger">{detailError}</p>
            <button
              className="button button-secondary"
              type="button"
              onClick={() => void loadRackDetail(selectedRackId)}
            >
              Retry
            </button>
          </div>
        ) : selectedRackId !== null || listLoading ? (
          <div className="panel" aria-busy="true">
            <RailSkeleton label="Loading rig details…" />
          </div>
        ) : (
          <div className="panel">
            <h2 style={{ marginTop: 0 }}>Select a rig to begin</h2>
            <p className="muted">
              Choose a rig from the list, or create a new one to confirm inventory.
            </p>
            <Link className="button button-primary" to="/racks/new">
              New rig
            </Link>
          </div>
        )}
      </section>
    </div>
  );
}
