/**
 * Patch detail — one patch on its rig's rail, with the cable table and the user's own notes.
 * Lives under its rig (/rigs/:rigId/patches/:patchId); a link with the wrong rig is corrected.
 */
import { useEffect, useState } from "react";
import { Link, Navigate, useParams } from "react-router-dom";
import PatchOverlay from "@/components/PatchOverlay";
import PatchRail from "@/components/PatchRail";
import { RailSkeleton } from "@/components/Skeletons";
import { canonApi, patchApi } from "@/lib/api";
import { rigDetailToRack } from "@/lib/canonRigAdapter";
import { failureReason } from "@/lib/loadError";
import { patchName } from "@/lib/patchName";
import type { Patch, Rack } from "@/types/api";
import { difficultyFromConnections } from "./racksPageUtils";

type LoadState = "loading" | "ready" | "missing" | "error";

export default function PatchDetailPage() {
  const { rigId, patchId } = useParams();
  const rigIdNum = Number(rigId);
  const patchIdNum = Number(patchId);
  const [state, setState] = useState<LoadState>("loading");
  const [patch, setPatch] = useState<Patch | null>(null);
  const [rig, setRig] = useState<Rack | null>(null);
  const [attempt, setAttempt] = useState(0);
  const [failure, setFailure] = useState<unknown>(null);

  useEffect(() => {
    if (!patchIdNum || !rigIdNum) {
      setState("missing");
      return;
    }
    let current = true;
    setState("loading");
    setPatch(null);
    void Promise.allSettled([patchApi.get(patchIdNum), canonApi.getRig(rigIdNum)]).then(
      ([patchResult, rigResult]) => {
        if (!current) return;
        if (patchResult.status === "rejected") {
          const status = (patchResult.reason as { response?: { status?: number } })?.response
            ?.status;
          setState(status === 404 ? "missing" : "error");
          setFailure(patchResult.reason);
          return;
        }
        setPatch(patchResult.value.data);
        setRig(rigResult.status === "fulfilled" ? rigDetailToRack(rigResult.value.data) : null);
        setState("ready");
      },
    );
    return () => {
      current = false;
    };
  }, [patchIdNum, rigIdNum, attempt]);

  if (state === "loading") {
    return (
      <div className="patch-detail">
        <span className="skeleton rig-title-skeleton" aria-hidden="true" />
        <RailSkeleton label="Loading patch" rows={1} />
      </div>
    );
  }

  if (state !== "ready" || !patch) {
    return (
      <section className="screen-state" aria-labelledby="patch-missing">
        <h1 id="patch-missing" className="empty-title">
          {state === "error" ? "Couldn't load this patch." : "No patch here."}
        </h1>
        {state === "error" ? (
          <p className="status status-danger" role="alert">
            {failureReason(failure)}
          </p>
        ) : null}
        {state === "error" ? (
          <button
            className="button button-primary"
            type="button"
            onClick={() => setAttempt((n) => n + 1)}
          >
            Retry
          </button>
        ) : (
          <p>It may have been removed, or belong to another account.</p>
        )}
        <Link className="button button-secondary" to={`/racks/${rigIdNum}?tab=patches`}>
          Back to the rig&apos;s patches
        </Link>
      </section>
    );
  }

  if (patch.rack_id !== rigIdNum) {
    return <Navigate replace to={`/rigs/${patch.rack_id}/patches/${patch.id}`} />;
  }

  const cables = patch.connections.length;
  const difficulty = patch.difficulty || difficultyFromConnections(patch);

  return (
    <section className="patch-detail" aria-labelledby="patch-title">
      <header className="workspace-header">
        <div>
          <nav className="breadcrumb" aria-label="Breadcrumb">
            <Link to={`/racks/${rigIdNum}?tab=patches&patch=${patch.id}`}>Rigs</Link>
            <span aria-hidden="true">/</span>
            <Link to={`/rigs/${rigIdNum}?tab=patches&patch=${patch.id}`}>
              {rig?.name || "This rig"}
            </Link>
          </nav>
          <h1 id="patch-title">{patchName(patch)}</h1>
          {patch.description ? <p className="muted">{patch.description}</p> : null}
          <p className="muted">
            {patch.category}, {difficulty}, {cables} cable{cables === 1 ? "" : "s"}. Seed{" "}
            {patch.generation_seed}, generator {patch.generation_version}.
          </p>
        </div>
      </header>

      {rig ? (
        <PatchRail rack={rig} patch={patch} />
      ) : (
        <div className="screen-state-actions">
          <p className="status status-warning" role="status">
            Couldn&apos;t load this patch&apos;s rig, so its cables can&apos;t be drawn on the rail.
          </p>
          <button
            className="button button-secondary"
            type="button"
            onClick={() => setAttempt((n) => n + 1)}
          >
            Retry
          </button>
        </div>
      )}

      <PatchOverlay patchId={patch.id} headingLevel={2} />
    </section>
  );
}
