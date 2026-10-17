import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  canonApi,
  evidenceApi,
  legacyPatchRef,
  patchApi,
  runApi,
  type InventoryRevisionSummary,
} from "@/lib/api";
import type { Patch, Run } from "@/types/api";

type WorkspaceTab = "overview" | "patches" | "exports" | "gallery";

const tabLabels: Record<WorkspaceTab, string> = {
  overview: "Overview",
  patches: "Patches",
  exports: "Exports",
  gallery: "Module gallery",
};

interface RigRevision {
  rig_revision_id: string;
  content_hash?: string | null;
  run_count: number;
  latest_run_id?: number | null;
  latest_run_at?: string | null;
  export_bridge_ready: boolean;
}

interface OverlayState {
  notes: string;
  favorite: boolean;
  tried: boolean;
}

export default function RigDetailPage() {
  const { rigId } = useParams();
  const rigIdNum = Number(rigId);
  const [runs, setRuns] = useState<Run[]>([]);
  const [revisions, setRevisions] = useState<RigRevision[]>([]);
  const [activeTab, setActiveTab] = useState<WorkspaceTab>("overview");
  const [activeRevisionId, setActiveRevisionId] = useState<string | null>(null);
  const [activeRunId, setActiveRunId] = useState<number | null>(null);
  const [patches, setPatches] = useState<Patch[]>([]);
  const [selectedPatchId, setSelectedPatchId] = useState<number | null>(null);
  const [overlay, setOverlay] = useState<OverlayState>({
    notes: "",
    favorite: false,
    tried: false,
  });
  const [overlayStatus, setOverlayStatus] = useState("");
  const [credits, setCredits] = useState(0);
  const [exportStatus, setExportStatus] = useState("");
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState(false);
  const [patchesLoading, setPatchesLoading] = useState(false);
  const [latestInventory, setLatestInventory] = useState<InventoryRevisionSummary | null>(null);
  const [inventoryError, setInventoryError] = useState("");
  const [generating, setGenerating] = useState(false);
  const [generateStatus, setGenerateStatus] = useState("");
  const [lastGenerateRunId, setLastGenerateRunId] = useState<number | null>(null);

  const hasRuns = runs.length > 0;
  const inventoryReady = Boolean(latestInventory?.ready_for_generation);
  const inventorySealed = Boolean(latestInventory?.inventory_revision_id);
  const tabs = useMemo<WorkspaceTab[]>(
    () => (hasRuns ? ["overview", "patches", "exports", "gallery"] : ["overview", "gallery"]),
    [hasRuns],
  );

  const runsForRevision = useMemo(() => {
    if (!activeRevisionId) return runs;
    return runs.filter((run) => run.rig_revision_id === activeRevisionId);
  }, [runs, activeRevisionId]);

  const activeRun = useMemo(
    () => runsForRevision.find((run) => run.id === activeRunId) ?? runsForRevision[0] ?? null,
    [runsForRevision, activeRunId],
  );

  useEffect(() => {
    if (!rigIdNum) return;
    setInventoryError("");
    evidenceApi
      .listInventory(rigIdNum)
      .then((res) => setLatestInventory(res.data.latest ?? null))
      .catch(() => {
        setLatestInventory(null);
        setInventoryError("Inventory receipt unavailable.");
      });
  }, [rigIdNum]);

  useEffect(() => {
    if (!rigIdNum) return;
    setLoading(true);
    // Load runs and revisions independently so a missing revisions route
    // cannot blank the whole workspace (tabs depend on hasRuns).
    const runsPromise = canonApi.listRuns(rigIdNum).then((response) => {
      const ordered = [...response.data.runs].sort(
        (a, b) => Date.parse(b.created_at) - Date.parse(a.created_at),
      );
      setRuns(ordered);
      return ordered;
    });
    const revsPromise = canonApi.listRevisions(rigIdNum).then((response) => {
      const revs = response.data.revisions ?? [];
      setRevisions(revs);
      return revs;
    });
    Promise.allSettled([runsPromise, revsPromise])
      .then((results) => {
        const ordered = results[0].status === "fulfilled" ? results[0].value : [];
        const revs = results[1].status === "fulfilled" ? results[1].value : [];
        if (results[0].status !== "fulfilled") setRuns([]);
        if (results[1].status !== "fulfilled") {
          // Derive revision options from run bridge fields when API absent.
          const derived: RigRevision[] = [];
          const seen = new Set<string>();
          for (const run of ordered) {
            if (seen.has(run.rig_revision_id)) continue;
            seen.add(run.rig_revision_id);
            derived.push({
              rig_revision_id: run.rig_revision_id,
              run_count: ordered.filter((r) => r.rig_revision_id === run.rig_revision_id).length,
              latest_run_id: run.id,
              latest_run_at: run.created_at,
              export_bridge_ready: run.export_bridge_ready,
            });
          }
          setRevisions(derived);
        }
        const firstRev = revs[0]?.rig_revision_id ?? ordered[0]?.rig_revision_id ?? null;
        setActiveRevisionId(firstRev);
        const firstRun =
          ordered.find((r) => r.rig_revision_id === firstRev)?.id ?? ordered[0]?.id ?? null;
        setActiveRunId(firstRun);
      })
      .finally(() => setLoading(false));
  }, [rigIdNum]);

  useEffect(() => {
    if (!activeRun?.id) {
      setPatches([]);
      setSelectedPatchId(null);
      return;
    }
    setPatchesLoading(true);
    runApi
      .patches(activeRun.id)
      .then((response) => {
        const rows = response.data.patches ?? [];
        setPatches(rows);
        setSelectedPatchId(rows[0]?.id ?? null);
      })
      .catch(() => {
        setPatches([]);
        setSelectedPatchId(null);
      })
      .finally(() => setPatchesLoading(false));
  }, [activeRun?.id]);

  useEffect(() => {
    if (selectedPatchId == null) {
      setOverlay({ notes: "", favorite: false, tried: false });
      return;
    }
    const ref = legacyPatchRef(selectedPatchId);
    canonApi
      .getOverlay(ref)
      .then((response) => {
        setOverlay({
          notes: response.data.notes ?? "",
          favorite: response.data.favorite,
          tried: response.data.tried,
        });
        setOverlayStatus("");
      })
      .catch(() => {
        // Unauthenticated or network — keep local draft only
        setOverlay({ notes: "", favorite: false, tried: false });
      });
  }, [selectedPatchId]);

  const refreshCredits = () => {
    canonApi
      .getBalance()
      .then((response) => setCredits(response.data.balance))
      .catch(() => setCredits(0));
  };

  useEffect(refreshCredits, []);

  const handleRevisionChange = (revisionId: string) => {
    setActiveRevisionId(revisionId);
    const nextRun = runs.find((r) => r.rig_revision_id === revisionId);
    setActiveRunId(nextRun?.id ?? null);
  };

  const saveOverlay = async () => {
    if (selectedPatchId == null) return;
    setOverlayStatus("Saving…");
    try {
      await canonApi.upsertOverlay(legacyPatchRef(selectedPatchId), {
        notes: overlay.notes,
        favorite: overlay.favorite,
        tried: overlay.tried,
      });
      setOverlayStatus("Personal overlay saved (does not mutate canonical patch).");
    } catch {
      setOverlayStatus("Sign in required to persist notes/favorite/tried on the server.");
    }
  };

  const reloadRunsAndSelect = async (preferRunId?: number | null) => {
    if (!rigIdNum) return;
    try {
      const response = await canonApi.listRuns(rigIdNum);
      const ordered = [...response.data.runs].sort(
        (a, b) => Date.parse(b.created_at) - Date.parse(a.created_at),
      );
      setRuns(ordered);
      const pick =
        (preferRunId != null ? ordered.find((r) => r.id === preferRunId) : null) ??
        ordered[0] ??
        null;
      if (pick) {
        setActiveRevisionId(pick.rig_revision_id);
        setActiveRunId(pick.id);
      }
    } catch {
      /* keep existing runs */
    }
  };

  const handleGenerate = async () => {
    if (!rigIdNum) return;
    setGenerateStatus("");
    setGenerating(true);
    try {
      const result = await patchApi.generate(rigIdNum, {});
      const body = result.data;
      const status = body.generation_status ?? "OK";
      const count = body.generated_count ?? body.patches?.length ?? 0;
      if (status === "NOT_COMPUTABLE" || count === 0) {
        setGenerateStatus(
          `Generation ${status}: no patches produced` +
            (body.inventory_gate_code ? ` (${body.inventory_gate_code})` : "") +
            ". Confirm inventory modules, then retry.",
        );
      } else {
        setGenerateStatus(
          `Generated ${count} patch${count === 1 ? "" : "es"}` +
            (body.run_id != null ? ` · run ${body.run_id}` : "") +
            (body.inventory_revision_id ? ` · inventory ${body.inventory_revision_id}` : "") +
            (body.rig_revision_id ? ` · ${body.rig_revision_id.slice(0, 16)}…` : "") +
            ".",
        );
        setLastGenerateRunId(body.run_id ?? null);
        await reloadRunsAndSelect(body.run_id ?? null);
        setActiveTab("patches");
      }
      // Refresh inventory receipt after generate (gate may seal a placement-based revision).
      try {
        const inv = await evidenceApi.listInventory(rigIdNum);
        setLatestInventory(inv.data.latest ?? null);
        setInventoryError("");
      } catch {
        /* keep prior inventory */
      }
    } catch (error: unknown) {
      const apiError = error as { response?: { data?: { detail?: string }; status?: number } };
      const detail = apiError.response?.data?.detail;
      setGenerateStatus(
        typeof detail === "string" ? detail : "Generation failed. Confirm inventory and retry.",
      );
    } finally {
      setGenerating(false);
    }
  };

  const handleExport = async () => {
    if (!activeRun) return;
    if (!activeRun.export_bridge_ready) {
      setExportStatus("Export bridge not ready for this run; reload the workspace and retry.");
      return;
    }
    setExportStatus("");
    setExporting(true);
    try {
      const idempotency_key = `patchbook-run-${activeRun.id}-${crypto.randomUUID()}`;
      const created = await canonApi.createExport({
        source_run_id: activeRun.source_run_id,
        source_rig_revision_id: activeRun.rig_revision_id,
        artifact_manifest_hash: activeRun.artifact_manifest_hash,
        formats: ["pdf", "json"],
        license: "personal",
        idempotency_key,
      });
      setExportStatus(
        `Canonical export ${created.data.export_id} ${created.data.status}. Credits debited on the /api/canon ledger only.`,
      );
      refreshCredits();
    } catch (error: unknown) {
      const apiError = error as { response?: { data?: { detail?: string }; status?: number } };
      const detail = apiError.response?.data?.detail;
      if (apiError.response?.status === 402) {
        setExportStatus("INSUFFICIENT_CREDITS — no debit recorded on the canonical ledger.");
      } else {
        setExportStatus(detail || "Export failed; no successful canonical debit recorded.");
      }
    } finally {
      setExporting(false);
    }
  };

  return (
    <section aria-labelledby="rig-title">
      <header className="workspace-header">
        <div>
          <p className="eyebrow">Canonical rig workspace</p>
          <h1 id="rig-title">Rig {rigId}</h1>
          <p className="muted">
            Pick an immutable revision, inspect its runs, and keep personal notes as a mutable
            overlay.
          </p>
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
          {revisions.length > 0 ? (
            <div className="field">
              <label htmlFor="revision-selector">Rig revision</label>
              <select
                id="revision-selector"
                value={activeRevisionId ?? ""}
                onChange={(event) => handleRevisionChange(event.target.value)}
              >
                {revisions.map((rev, index) => (
                  <option key={rev.rig_revision_id} value={rev.rig_revision_id}>
                    {index === 0 ? "Latest · " : ""}
                    {rev.rig_revision_id.slice(0, 20)}… · {rev.run_count} run
                    {rev.run_count === 1 ? "" : "s"}
                  </option>
                ))}
              </select>
            </div>
          ) : null}
          {runsForRevision.length > 0 ? (
            <div className="field">
              <label htmlFor="run-selector">Source run (within revision)</label>
              <select
                id="run-selector"
                value={activeRun?.id ?? ""}
                onChange={(event) => setActiveRunId(Number(event.target.value))}
              >
                {runsForRevision.map((run, index) => (
                  <option key={run.id} value={run.id}>
                    {index === 0 ? "Latest · " : ""}Run {run.id} ·{" "}
                    {new Date(run.created_at).toLocaleDateString()}
                  </option>
                ))}
              </select>
            </div>
          ) : null}
        </div>
      </header>

      <div className="tab-list" role="tablist" aria-label="Rig workspace">
        {tabs.map((tab) => (
          <button
            className="tab"
            id={`tab-${tab}`}
            key={tab}
            type="button"
            role="tab"
            aria-selected={activeTab === tab}
            aria-controls={`panel-${tab}`}
            onClick={() => setActiveTab(tab)}
          >
            {tabLabels[tab]}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="panel" role="status">
          Loading rig history…
        </div>
      ) : null}

      {generateStatus ? (
        <div
          className="panel"
          role="status"
          aria-label="Generation receipt"
          style={{ marginBottom: "1rem" }}
        >
          <p
            className={`status ${
              generateStatus.includes("NOT_COMPUTABLE") || generateStatus.includes("failed")
                ? "status-warning"
                : "status-success"
            }`}
          >
            {generateStatus}
          </p>
        </div>
      ) : null}

      {!loading && activeTab === "overview" ? (
        <div className="panel" id="panel-overview" role="tabpanel" aria-labelledby="tab-overview">
          <h2>{hasRuns ? "Rig ready" : "Build the source of truth"}</h2>
          <p className="muted">
            {hasRuns
              ? `${revisions.length} revision${revisions.length === 1 ? "" : "s"} · ${runs.length} generation run${runs.length === 1 ? "" : "s"}.`
              : "Add modules manually or review photo evidence before generating."}
          </p>
          {activeRevisionId ? (
            <p className="muted">
              Active revision: <code>{activeRevisionId}</code>
              {activeRun ? (
                <>
                  {" "}
                  · run <code>{activeRun.id}</code>
                </>
              ) : null}
            </p>
          ) : null}

          <ol
            className="panel"
            style={{ marginTop: "1rem", marginBottom: "1rem", paddingLeft: "1.25rem" }}
            aria-label="Inventory to generation loop"
          >
            <li style={{ marginBottom: "0.5rem" }}>
              <strong>1 · Confirm inventory</strong>
              <span className="muted">
                {" "}
                — photo evidence or manual placements (never auto-confirm)
              </span>
            </li>
            <li style={{ marginBottom: "0.5rem" }}>
              <strong>2 · Generate patches</strong>
              <span className="muted">
                {" "}
                — constrained to confirmed modules; empty inventory → NOT_COMPUTABLE
              </span>
            </li>
            <li>
              <strong>3 · Review &amp; export</strong>
              <span className="muted"> — patches tab; exports debit only via /api/canon</span>
            </li>
          </ol>

          <div
            className="panel"
            style={{ marginTop: "1rem", marginBottom: "1rem" }}
            aria-label="Confirmed inventory receipt"
          >
            <h3>Confirmed inventory</h3>
            {inventoryError ? (
              <p className="status status-warning" role="status">
                {inventoryError}
              </p>
            ) : null}
            {latestInventory ? (
              <>
                <p
                  className={`status status-${inventoryReady ? "success" : "warning"}`}
                  role="status"
                >
                  Inventory revision: <code>{latestInventory.inventory_revision_id}</code>
                  {inventoryReady ? " · ready for generation" : " · not ready for generation"}
                </p>
                <p className="muted">
                  {latestInventory.confirmed_count} confirmed module
                  {latestInventory.confirmed_count === 1 ? "" : "s"}
                  {latestInventory.unresolved_count
                    ? ` · ${latestInventory.unresolved_count} unresolved candidate(s)`
                    : ""}
                  {latestInventory.created_at
                    ? ` · sealed ${new Date(latestInventory.created_at).toLocaleString()}`
                    : ""}
                </p>
              </>
            ) : !inventoryError ? (
              <p className="muted" role="status">
                No sealed inventory revision yet. Confirm photo or manual candidates first.
              </p>
            ) : null}
          </div>

          <div
            className="panel"
            style={{ marginBottom: "1rem" }}
            aria-label="Generate patches from inventory"
          >
            <h3>Generate patches</h3>
            <p className="muted">
              {inventoryReady
                ? "Sealed inventory is ready. Generation uses confirmed modules only."
                : inventorySealed
                  ? "Inventory is sealed but not ready for generation — resolve candidates or place modules, then retry."
                  : "No sealed inventory yet. You can still open evidence confirmation; generation fails closed if no confirmed modules exist on the rig."}
            </p>
            <div style={{ display: "flex", flexWrap: "wrap", gap: "0.5rem", alignItems: "center" }}>
              <button
                className="button button-primary"
                type="button"
                onClick={() => void handleGenerate()}
                disabled={!rigIdNum || generating}
                aria-describedby="generate-help"
              >
                {generating
                  ? "Generating…"
                  : inventoryReady
                    ? "Generate patches"
                    : "Generate patches (may be blocked)"}
              </button>
              <Link
                className={inventoryReady ? "button button-secondary" : "button button-primary"}
                to={`/racks/${rigId}/edit`}
              >
                {inventorySealed
                  ? "Update inventory evidence"
                  : "Confirm inventory (photo / manual)"}
              </Link>
              {hasRuns ? (
                <button
                  className="button button-quiet"
                  type="button"
                  onClick={() => setActiveTab("patches")}
                >
                  View patch library
                </button>
              ) : null}
            </div>
            <p id="generate-help" className="muted" style={{ marginTop: "0.5rem" }}>
              {inventoryReady
                ? "Primary path: inventory ready → generate → review patches → export when credits allow."
                : "Complete inventory confirmation for a clear green path. Generation never invents modules."}
            </p>
            {lastGenerateRunId != null ? (
              <p className="muted" style={{ marginTop: "0.5rem" }}>
                Latest generation run: <code>{lastGenerateRunId}</code> · open Patches tab to
                review.
              </p>
            ) : null}
          </div>
        </div>
      ) : null}

      {!loading && activeTab === "patches" && hasRuns ? (
        <div className="panel" id="panel-patches" role="tabpanel" aria-labelledby="tab-patches">
          <p className="eyebrow">Run {activeRun?.id ?? "—"}</p>
          <h2>Patch library</h2>
          <p className="muted">
            Canonical patches are immutable. Favorite / tried / notes are personal overlays.
          </p>
          {patchesLoading ? <p role="status">Loading patches…</p> : null}
          {!patchesLoading && patches.length === 0 ? (
            <p className="status status-warning">No patches for this run.</p>
          ) : null}
          <div style={{ display: "grid", gap: "1rem", gridTemplateColumns: "1fr 1fr" }}>
            <ul aria-label="Patches in run" style={{ listStyle: "none", padding: 0, margin: 0 }}>
              {patches.map((patch) => (
                <li key={patch.id}>
                  <button
                    type="button"
                    className={`button ${selectedPatchId === patch.id ? "button-primary" : "button-quiet"}`}
                    style={{ width: "100%", textAlign: "left", marginBottom: "0.5rem" }}
                    onClick={() => setSelectedPatchId(patch.id)}
                  >
                    {patch.name_override || patch.suggested_name || patch.name}
                    <span className="muted" style={{ display: "block", fontSize: "0.8rem" }}>
                      {patch.category} · {patch.connections?.length ?? 0} cables
                    </span>
                  </button>
                </li>
              ))}
            </ul>
            {selectedPatchId != null ? (
              <div className="panel" aria-label="Personal patch overlay">
                <h3>Personal overlay</h3>
                <p className="muted">
                  Ref <code>{legacyPatchRef(selectedPatchId)}</code>
                </p>
                <label className="field">
                  Notes
                  <textarea
                    value={overlay.notes}
                    onChange={(event) => setOverlay((o) => ({ ...o, notes: event.target.value }))}
                    rows={4}
                    style={{ width: "100%" }}
                  />
                </label>
                <label style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
                  <input
                    type="checkbox"
                    checked={overlay.favorite}
                    onChange={(event) =>
                      setOverlay((o) => ({ ...o, favorite: event.target.checked }))
                    }
                  />
                  Favorite
                </label>
                <label style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
                  <input
                    type="checkbox"
                    checked={overlay.tried}
                    onChange={(event) => setOverlay((o) => ({ ...o, tried: event.target.checked }))}
                  />
                  Tried
                </label>
                <button
                  className="button button-secondary"
                  type="button"
                  onClick={() => void saveOverlay()}
                >
                  Save overlay
                </button>
                {overlayStatus ? (
                  <p role="status" className="status">
                    {overlayStatus}
                  </p>
                ) : null}
              </div>
            ) : null}
          </div>
        </div>
      ) : null}

      {!loading && activeTab === "exports" && hasRuns ? (
        <div className="panel" id="panel-exports" role="tabpanel" aria-labelledby="tab-exports">
          <p className="eyebrow">Canonical monetization boundary</p>
          <h2>Exports</h2>
          <p>
            Available credits: <strong>{credits}</strong>
          </p>
          <p className="muted">
            Debits post only via <code>/api/canon/exports</code>. Bound to revision{" "}
            <code>{activeRun?.rig_revision_id}</code>.
          </p>
          <div style={{ display: "flex", flexWrap: "wrap", gap: "0.5rem" }}>
            <button
              className="button button-primary"
              type="button"
              onClick={handleExport}
              disabled={credits <= 0 || exporting || !activeRun}
            >
              {exporting ? "Requesting…" : "Export PDF patch book"}
            </button>
            {activeRun?.export_bridge_ready ? (
              <a
                className="button button-secondary"
                href={`/rigs/${rigIdNum}/patchbook-studio?source_run_id=${encodeURIComponent(activeRun.source_run_id)}&source_rig_revision_id=${encodeURIComponent(activeRun.rig_revision_id)}&artifact_manifest_hash=${encodeURIComponent(activeRun.artifact_manifest_hash)}`}
              >
                Open Style Studio
              </a>
            ) : null}
          </div>
          {credits <= 0 ? (
            <p className="status status-warning">Credits are required only for exports.</p>
          ) : null}
          {exportStatus ? (
            <p role="status" className="status">
              {exportStatus}
            </p>
          ) : null}
        </div>
      ) : null}

      {!loading && activeTab === "gallery" ? (
        <div className="panel" id="panel-gallery" role="tabpanel" aria-labelledby="tab-gallery">
          <p className="eyebrow">Evidence and revisions</p>
          <h2>Module gallery</h2>
          <p className="muted">
            Confirmed gallery evidence is separated from inferred, disputed, and missing
            specifications.
          </p>
          <Link className="button button-secondary" to={`/racks/${rigId}/edit`}>
            Open photo / inventory confirmation
          </Link>
        </div>
      ) : null}
    </section>
  );
}
