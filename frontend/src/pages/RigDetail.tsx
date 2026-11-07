import { useEffect, useMemo, useState } from "react";
import type { CSSProperties } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import Hash from "@/components/Hash";
import LoadFailure from "@/components/LoadFailure";
import PatchOverlay from "@/components/PatchOverlay";
import PatchRail from "@/components/PatchRail";
import RigRail from "@/components/RigRail";
import Tabs from "@/components/Tabs";
import { ChainSkeleton, ListSkeleton } from "@/components/Skeletons";
import ModulesToPlace from "@/components/builder/ModulesToPlace";
import {
  canonApi,
  evidenceApi,
  patchApi,
  runApi,
  type InventoryRevisionSummary,
  type ModuleToPlace,
} from "@/lib/api";
import { rigDetailToRack } from "@/lib/canonRigAdapter";
import {
  allowanceCount,
  allowanceReset,
  allowanceUsage,
  allowanceUsedUp,
  exportRefusal,
} from "@/lib/commerce";
import { formatDateTime, runLabel, shortHash } from "@/lib/format";
import { describeEmptyGeneration } from "@/lib/generateOutcome";
import { patchName } from "@/lib/patchName";
import { useAuthStore } from "@/lib/store";
import type { CommerceAllowance, Patch, Rack, Run } from "@/types/api";

type WorkspaceTab = "overview" | "patches" | "exports" | "gallery";

function isWorkspaceTab(value: string | null): value is WorkspaceTab {
  return value === "overview" || value === "patches" || value === "exports" || value === "gallery";
}

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

export default function RigDetailPage() {
  const { rigId } = useParams();
  const rigIdNum = Number(rigId);
  const [rig, setRig] = useState<Rack | null>(null);
  const [rigFailed, setRigFailed] = useState(false);

  // The rig itself: its name for the title and its placements for the rail.
  useEffect(() => {
    if (!rigIdNum) return;
    let current = true;
    setRig(null);
    setRigFailed(false);
    canonApi
      .getRig(rigIdNum)
      .then((response) => {
        if (current) setRig(rigDetailToRack(response.data));
      })
      .catch(() => {
        if (current) setRigFailed(true);
      });
    return () => {
      current = false;
    };
  }, [rigIdNum]);
  const [runs, setRuns] = useState<Run[]>([]);
  const [revisions, setRevisions] = useState<RigRevision[]>([]);
  const [activeRevisionId, setActiveRevisionId] = useState<string | null>(null);
  const [activeRunId, setActiveRunId] = useState<number | null>(null);
  const [patches, setPatches] = useState<Patch[]>([]);
  // Null until the balance arrives, so a balance that didn't load never reads as 0 credits.
  const [credits, setCredits] = useState<number | null>(null);
  const [creditsError, setCreditsError] = useState<unknown>(null);
  const [allowance, setAllowance] = useState<CommerceAllowance | null>(null);
  const [runsError, setRunsError] = useState<unknown>(null);
  const [runsAttempt, setRunsAttempt] = useState(0);
  const [patchesError, setPatchesError] = useState<unknown>(null);
  const [patchesAttempt, setPatchesAttempt] = useState(0);
  const [exportStatus, setExportStatus] = useState("");
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState(false);
  const [patchesLoading, setPatchesLoading] = useState(false);
  const [latestInventory, setLatestInventory] = useState<InventoryRevisionSummary | null>(null);
  const [modulesToPlace, setModulesToPlace] = useState<ModuleToPlace[]>([]);
  const [inventoryError, setInventoryError] = useState("");
  const [generating, setGenerating] = useState(false);
  // Generating writes to the rig, which belongs to its owner (the server enforces it).
  const signedIn = useAuthStore((st) => st.isAuthenticated());
  const [generateStatus, setGenerateStatus] = useState("");
  const [generateTone, setGenerateTone] = useState<"success" | "warning">("success");
  const [lastGenerateRunId, setLastGenerateRunId] = useState<number | null>(null);

  const hasRuns = runs.length > 0;
  const inventoryReady = Boolean(latestInventory?.ready_for_generation);
  const inventorySealed = Boolean(latestInventory?.inventory_revision_id);
  const tabs = useMemo<WorkspaceTab[]>(
    () => (hasRuns ? ["overview", "patches", "exports", "gallery"] : ["overview", "gallery"]),
    [hasRuns],
  );

  // The tab and the selected patch live in the URL (?tab=&patch=), so a patch page's
  // breadcrumb, a reload or the back button returns to the same view.
  const [searchParams, setSearchParams] = useSearchParams();
  const tabParam = searchParams.get("tab");
  const requestedTab: WorkspaceTab = isWorkspaceTab(tabParam) ? tabParam : "overview";
  const activeTab: WorkspaceTab = tabs.includes(requestedTab) ? requestedTab : "overview";
  const patchParam = searchParams.get("patch");
  const selectedPatch =
    patches.find((patch) => String(patch.id) === patchParam) ?? patches[0] ?? null;
  const selectedPatchId = selectedPatch?.id ?? null;
  const setActiveTab = (tab: WorkspaceTab) =>
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
    let current = true;
    setInventoryError("");
    evidenceApi
      .listInventory(rigIdNum)
      .then((res) => {
        if (!current) return;
        setLatestInventory(res.data.latest ?? null);
        setModulesToPlace(res.data.modules_to_place ?? []);
      })
      .catch(() => {
        if (!current) return;
        setLatestInventory(null);
        setModulesToPlace([]);
        setInventoryError("Inventory receipt unavailable.");
      });
    return () => {
      current = false;
    };
  }, [rigIdNum]);

  useEffect(() => {
    if (!rigIdNum) return;
    let current = true;
    setLoading(true);
    setRunsError(null);
    // Load runs and revisions independently so a missing revisions route
    // cannot blank the whole workspace (tabs depend on hasRuns).
    const runsPromise = canonApi
      .listRuns(rigIdNum)
      .then((response) =>
        [...response.data.runs].sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at)),
      );
    const revsPromise = canonApi
      .listRevisions(rigIdNum)
      .then((response) => response.data.revisions ?? []);
    Promise.allSettled([runsPromise, revsPromise])
      .then((results) => {
        if (!current) return;
        const ordered = results[0].status === "fulfilled" ? results[0].value : [];
        const revs = results[1].status === "fulfilled" ? results[1].value : [];
        setRuns(ordered);
        // Runs that didn't load are a failure to show, not a rig with no runs yet.
        setRunsError(results[0].status === "rejected" ? results[0].reason : null);
        if (results[1].status === "fulfilled") {
          setRevisions(revs);
        } else {
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
      .finally(() => {
        if (current) setLoading(false);
      });
    return () => {
      current = false;
    };
  }, [rigIdNum, runsAttempt]);

  useEffect(() => {
    setPatchesError(null);
    if (!activeRun?.id) {
      setPatches([]);
      return;
    }
    let current = true;
    setPatchesLoading(true);
    runApi
      .patches(activeRun.id)
      .then((response) => {
        if (current) setPatches(response.data.patches ?? []);
      })
      .catch((err: unknown) => {
        if (!current) return;
        setPatches([]);
        setPatchesError(err);
      })
      .finally(() => {
        if (current) setPatchesLoading(false);
      });
    return () => {
      current = false;
    };
  }, [activeRun?.id, patchesAttempt]);

  // Credits belong to an account, so a signed-out visitor is asked to sign in instead.
  const refreshCredits = () => {
    if (!signedIn) return;
    setCreditsError(null);
    canonApi
      .getBalance()
      .then((response) => setCredits(response.data.balance))
      .catch((err: unknown) => {
        setCredits(null);
        setCreditsError(err);
      });
    // A period allowance pays for exports instead of credits. The API checks again at export, so
    // if this read fails the page goes by the balance alone.
    canonApi
      .getCommerce()
      .then((response) => setAllowance(response.data.allowance))
      .catch(() => setAllowance(null));
  };

  useEffect(refreshCredits, [signedIn]);

  const handleRevisionChange = (revisionId: string) => {
    setActiveRevisionId(revisionId);
    const nextRun = runs.find((r) => r.rig_revision_id === revisionId);
    setActiveRunId(nextRun?.id ?? null);
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
      const count = body.generated_count ?? body.patches?.length ?? 0;
      const emptyMessage = describeEmptyGeneration(body);
      if (emptyMessage) {
        setGenerateTone("warning");
        setGenerateStatus(emptyMessage);
      } else {
        setGenerateTone("success");
        setGenerateStatus(
          `Generated ${count} patch${count === 1 ? "" : "es"}` +
            (body.run_id != null ? `, run ${body.run_id}` : "") +
            (body.inventory_revision_id
              ? `, inventory ${shortHash(body.inventory_revision_id)}`
              : "") +
            (body.rig_revision_id ? `, revision ${shortHash(body.rig_revision_id)}` : "") +
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
        setModulesToPlace(inv.data.modules_to_place ?? []);
        setInventoryError("");
      } catch {
        /* keep prior inventory */
      }
    } catch (error: unknown) {
      const apiError = error as { response?: { data?: { detail?: string }; status?: number } };
      const detail = apiError.response?.data?.detail;
      setGenerateTone("warning");
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
        `Export ${shortHash(created.data.export_id)} requested (${created.data.status}). ${
          created.data.credit_cost === 0
            ? "It counts toward this period's exports, and no credits come off your balance."
            : "Its credits come off your balance; nothing else is charged."
        }`,
      );
      refreshCredits();
    } catch (error: unknown) {
      setExportStatus(exportRefusal(error));
    } finally {
      setExporting(false);
    }
  };

  const canSpend = allowance ? !allowanceUsedUp(allowance) : credits != null && credits > 0;

  // The patch path: how far this rig has come from inventory to book.
  const reached = hasRuns ? 2 : inventoryReady ? 1 : 0;
  const stages = [
    {
      title: "Confirm inventory",
      state: inventoryReady
        ? "Sealed and ready"
        : modulesToPlace.length
          ? `Confirmed, ${modulesToPlace.length} still to place`
          : inventorySealed
            ? "Sealed, candidates open"
            : "Not sealed yet",
      detail: "Photo evidence or manual placements, never auto-confirmed.",
    },
    {
      title: "Generate patches",
      state: runsError
        ? "Runs didn't load"
        : hasRuns
          ? `${runs.length} run${runs.length === 1 ? "" : "s"}`
          : "No runs yet",
      detail: "Uses modules placed on the rig only. With none placed, nothing can be generated.",
    },
    {
      title: "Review and export",
      state: !hasRuns
        ? "After the first run"
        : !signedIn
          ? "Sign in to export"
          : allowance
            ? allowanceUsage(allowance)
            : credits == null
              ? creditsError
                ? "Balance didn't load"
                : "Checking your balance"
              : `${credits} credit${credits === 1 ? "" : "s"} available`,
      detail: "Review the patches, then export. Only exports cost credits.",
    },
  ];

  return (
    <section aria-labelledby="rig-title">
      <header className="workspace-header">
        <div>
          <nav className="breadcrumb" aria-label="Breadcrumb">
            <Link to={`/racks/${rigIdNum}`}>Rigs</Link>
          </nav>
          <h1 id="rig-title">
            {rig ? (
              rig.name
            ) : rigFailed ? (
              "Rig workspace"
            ) : (
              <>
                <span className="visually-hidden">Rig workspace</span>
                <span className="skeleton rig-title-skeleton" aria-hidden="true" />
              </>
            )}
          </h1>
          {rigFailed ? (
            <p className="status status-warning" role="status">
              Couldn&apos;t load this rig&apos;s details. Its runs are below.
            </p>
          ) : null}
          <p className="muted">Pick a revision, review its runs, keep notes on its patches.</p>
        </div>
        {revisions.length > 0 || runsForRevision.length > 0 ? (
          <div className="toolbar rig-source">
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
                      Revision {shortHash(rev.rig_revision_id)}
                      {index === 0 ? " (latest)" : ""}, {rev.run_count} run
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
                      {runLabel(run)}
                      {index === 0 ? " (latest)" : ""}
                    </option>
                  ))}
                </select>
              </div>
            ) : null}
          </div>
        ) : null}
      </header>

      <Tabs
        label="Rig workspace"
        tabs={tabs.map((tab) => ({ key: tab, label: tabLabels[tab] }))}
        active={activeTab}
        onChange={setActiveTab}
      />

      {loading ? <ChainSkeleton label="Loading rig history…" /> : null}

      {generateStatus ? (
        <div className="notice rig-receipt" role="status" aria-label="Generation receipt">
          <p className={`status status-${generateTone}`}>{generateStatus}</p>
        </div>
      ) : null}

      {!loading && activeTab === "overview" ? (
        <div
          className="rig-tabpanel"
          id="panel-overview"
          role="tabpanel"
          aria-labelledby="tab-overview"
        >
          <div className="rig-tabpanel__head">
            <h2>{hasRuns ? "Rig ready" : "Build the source of truth"}</h2>
            <p className="muted">
              {runsError
                ? "Its revisions and runs are unknown until they load."
                : hasRuns
                  ? `${revisions.length} revision${revisions.length === 1 ? "" : "s"}, ${runs.length} generation run${runs.length === 1 ? "" : "s"}.`
                  : "Add modules manually or review photo evidence before generating."}
            </p>
            {activeRevisionId ? (
              <p className="muted">
                Active revision <Hash value={activeRevisionId} />
                {activeRun ? `, run ${activeRun.id}` : null}
              </p>
            ) : null}
          </div>

          {runsError ? (
            <LoadFailure
              what="This rig's runs"
              error={runsError}
              onRetry={() => setRunsAttempt((n) => n + 1)}
            />
          ) : null}

          <ol
            className="signal-chain"
            aria-label="Inventory to generation loop"
            style={{ "--reach": reached / 2 } as CSSProperties}
          >
            {stages.map((stage, index) => (
              <li
                key={stage.title}
                className="signal-chain__stage"
                data-state={index < reached ? "done" : index === reached ? "current" : "todo"}
                aria-current={index === reached ? "step" : undefined}
              >
                <span className="signal-chain__jack" aria-hidden="true" />
                <strong className="signal-chain__title">{stage.title}</strong>
                <span className="signal-chain__state">{stage.state}</span>
                <span className="signal-chain__detail">{stage.detail}</span>
              </li>
            ))}
          </ol>

          {rig ? (
            <section className="rig-placed" aria-labelledby="rig-placed-title">
              <h3 id="rig-placed-title">On the rail</h3>
              {rig.case?.hp_per_row?.length ? (
                <RigRail rack={rig} />
              ) : (
                <p className="muted">
                  This rig&apos;s case doesn&apos;t state its row sizes yet, so its rail can&apos;t
                  be drawn. <Link to={`/racks/${rigIdNum}/edit`}>Place modules</Link>
                </p>
              )}
            </section>
          ) : null}

          <div className="rig-detail-grid">
            <div className="panel" aria-label="Confirmed inventory receipt">
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
                    Inventory revision: <Hash value={latestInventory.inventory_revision_id} />
                    {inventoryReady ? ", ready for generation" : ", not ready for generation"}
                  </p>
                  <p className="muted">
                    {latestInventory.confirmed_count} confirmed module
                    {latestInventory.confirmed_count === 1 ? "" : "s"}
                    {latestInventory.unresolved_count
                      ? `, ${latestInventory.unresolved_count} unresolved candidate(s)`
                      : ""}
                    {latestInventory.created_at
                      ? `, sealed ${formatDateTime(latestInventory.created_at)}`
                      : ""}
                  </p>
                </>
              ) : !inventoryError ? (
                <p className="muted" role="status">
                  No sealed inventory revision yet. Confirm photo or manual candidates first.
                </p>
              ) : null}
              <ModulesToPlace modules={modulesToPlace} rackId={rigIdNum || null} />
            </div>

            <div className="panel" aria-label="Generate patches from inventory">
              <h3>Generate patches</h3>
              <p id="generate-help" className="muted">
                {inventoryReady
                  ? "Sealed inventory is ready. Generation uses modules placed on the rig only."
                  : inventorySealed
                    ? "Inventory is sealed but not ready for generation: resolve candidates or place modules, then retry."
                    : "No sealed inventory yet. You can still open evidence confirmation; generation fails closed if no modules are placed on the rig."}
              </p>
              <div className="page-hero-actions">
                <button
                  className={inventoryReady ? "button button-primary" : "button button-secondary"}
                  type="button"
                  onClick={() => void handleGenerate()}
                  disabled={!rigIdNum || generating || !signedIn}
                  title={signedIn ? undefined : "Sign in to generate patches for your rig"}
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
              {lastGenerateRunId != null ? (
                <p className="muted">
                  Latest generation: run {lastGenerateRunId}. Open the Patches tab to review it.
                </p>
              ) : null}
            </div>
          </div>
        </div>
      ) : null}

      {!loading && activeTab === "patches" && hasRuns ? (
        <div
          className="rig-tabpanel"
          id="panel-patches"
          role="tabpanel"
          aria-labelledby="tab-patches"
        >
          <div className="rig-tabpanel__head">
            <h2>Patch library</h2>
            <p className="muted">{activeRun ? runLabel(activeRun) : "No run selected"}</p>
            <p className="muted">
              Generated patches don&apos;t change. Your notes, favorites and tried marks are yours
              alone.
            </p>
          </div>
          {patchesLoading ? <ListSkeleton label="Loading patches…" rows={3} /> : null}
          {patchesError ? (
            <LoadFailure
              what="This run's patches"
              error={patchesError}
              onRetry={() => setPatchesAttempt((n) => n + 1)}
            />
          ) : null}
          {!patchesLoading && !patchesError && patches.length === 0 ? (
            <p className="status status-warning">No patches for this run.</p>
          ) : null}
          <div className="split-workspace">
            <ul className="side-list rig-patch-list" aria-label="Patches in run">
              {patches.map((patch) => (
                <li key={patch.id}>
                  <button
                    type="button"
                    className={`side-item${selectedPatchId === patch.id ? " is-selected" : ""}`}
                    aria-current={selectedPatchId === patch.id ? "true" : undefined}
                    onClick={() => setSelectedPatchId(patch.id)}
                  >
                    <span className="side-item-title">{patchName(patch)}</span>
                    <span className="side-item-meta">
                      {patch.category}, {patch.connections?.length ?? 0} cables
                    </span>
                  </button>
                </li>
              ))}
            </ul>
            {selectedPatch ? (
              <section className="rig-patch-detail" aria-labelledby="rig-patch-title">
                <div className="rig-patch-detail__head">
                  <h3 id="rig-patch-title">{patchName(selectedPatch)}</h3>
                  <Link
                    className="button button-quiet"
                    to={`/rigs/${rigIdNum}/patches/${selectedPatch.id}`}
                  >
                    Open patch
                  </Link>
                </div>
                {rig ? <PatchRail rack={rig} patch={selectedPatch} /> : null}
                <PatchOverlay patchId={selectedPatch.id} />
              </section>
            ) : null}
          </div>
        </div>
      ) : null}

      {!loading && activeTab === "exports" && hasRuns ? (
        <div
          className="rig-tabpanel"
          id="panel-exports"
          role="tabpanel"
          aria-labelledby="tab-exports"
        >
          <div className="rig-tabpanel__head">
            <h2>Exports</h2>
            <p className="muted">
              Each export is a patch book of this run, tied to revision{" "}
              {activeRun ? <Hash value={activeRun.rig_revision_id} /> : "none"}.
            </p>
          </div>
          {signedIn ? (
            <dl className="readout">
              <div>
                <dt>Available credits</dt>
                <dd>{credits ?? "Not loaded"}</dd>
              </div>
              {allowance ? (
                <div>
                  <dt>Exports this period</dt>
                  <dd>{allowanceCount(allowance)}</dd>
                </div>
              ) : null}
            </dl>
          ) : null}
          {creditsError ? (
            <LoadFailure what="Your credit balance" error={creditsError} onRetry={refreshCredits} />
          ) : null}
          <div className="rig-export-actions">
            <div className="page-hero-actions">
              <button
                className="button button-primary"
                type="button"
                onClick={handleExport}
                disabled={!canSpend || exporting || !activeRun}
              >
                {exporting ? "Requesting…" : "Export PDF patch book"}
              </button>
              {activeRun?.export_bridge_ready ? (
                <Link
                  className="button button-secondary"
                  to={`/rigs/${rigIdNum}/patchbook-studio?source_run_id=${encodeURIComponent(activeRun.source_run_id)}&source_rig_revision_id=${encodeURIComponent(activeRun.rig_revision_id)}&artifact_manifest_hash=${encodeURIComponent(activeRun.artifact_manifest_hash)}`}
                >
                  Open Style Studio
                </Link>
              ) : null}
            </div>
            {!signedIn ? (
              <p className="status status-warning">Sign in to export. Only exports cost credits.</p>
            ) : allowance && allowanceUsedUp(allowance) ? (
              <p className="status status-warning">{allowanceReset(allowance)}</p>
            ) : !allowance && credits != null && credits <= 0 ? (
              <p className="status status-warning">Credits are required only for exports.</p>
            ) : null}
          </div>
          {exportStatus ? (
            <p role="status" className="status">
              {exportStatus}
            </p>
          ) : null}
        </div>
      ) : null}

      {!loading && activeTab === "gallery" ? (
        <div
          className="rig-tabpanel"
          id="panel-gallery"
          role="tabpanel"
          aria-labelledby="tab-gallery"
        >
          <div className="rig-tabpanel__head">
            <h2>Module gallery</h2>
            <p className="muted">
              Confirmed gallery evidence is separated from inferred, disputed, and missing
              specifications.
            </p>
          </div>
          <div className="page-hero-actions">
            <Link className="button button-secondary" to={`/racks/${rigId}/edit`}>
              Open photo / inventory confirmation
            </Link>
          </div>
        </div>
      ) : null}
    </section>
  );
}
