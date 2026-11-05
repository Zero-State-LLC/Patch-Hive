/**
 * EvidenceStep — photo evidence for a rig: upload, detect, then resolve every ranked candidate
 * by hand. Multi-photo fusion is advisory; nothing joins the inventory until the user confirms.
 * Candidates that did not come from the user's photos are labelled Demo.
 */
import { Link } from "react-router-dom";
import ModulesToPlace from "@/components/builder/ModulesToPlace";
import type { ModuleToPlace } from "@/lib/api";
import type { Rack } from "@/types/api";

export type EvidenceState = "idle" | "ready" | "uploading" | "review" | "confirmed" | "error";
export type CandidateStatus = "inferred" | "confirmed" | "rejected" | "deferred";

export interface DecisionAdvisory {
  disposition: "auto_propose" | "user_review" | "unresolved" | "escalate" | "reject";
  provider?: string;
  confidence?: number | null;
  reasonCodes?: string[];
}

export interface ReviewCandidate {
  id: string;
  label: string;
  manufacturer: string;
  confidence: number;
  alternatives: string[];
  status: CandidateStatus;
  moduleRevisionId: string;
  decision?: DecisionAdvisory;
}

export interface FusedEntityView {
  fuse_id: string;
  manufacturer?: string | null;
  model?: string | null;
  observation_count: number;
  supporting_image_ids: string[];
  mean_confidence: number;
  conflict: boolean;
  conflict_notes: string[];
  classification_status: string;
  representative_candidate_id?: string | null;
}

export interface FusionView {
  entities: FusedEntityView[];
  /** Decisions applied from the fusion panel, keyed by fuse_id. */
  applied: Record<string, CandidateStatus>;
  feedback: string | null;
  status: string | null;
  note: string | null;
  imageCount: number;
  onApply: (entity: FusedEntityView, status: CandidateStatus) => void;
  onConfirmAll: () => void;
}

interface EvidenceStepProps {
  /** Create flow only: the rigs photos can be uploaded to. Null on a rig's edit page. */
  rackChoices: Rack[] | null;
  selectedRackId: number | null;
  onSelectRack: (id: number | null) => void;
  /** The rig photos upload to, or null for a demo run. */
  targetRackId: number | null;
  state: EvidenceState;
  error: string;
  fileLabel: string;
  pendingCount: number;
  onSelectPhotos: (files: FileList | null) => void;
  onDetect: () => void;
  /** Ranked by confidence, highest first. */
  candidates: ReviewCandidate[];
  /** False when the candidates are the built-in demo set. */
  fromLiveApi: boolean;
  onSetStatus: (id: string, status: CandidateStatus) => void;
  fusion: FusionView;
  confirmedCount: number;
  allResolved: boolean;
  onCreateRevision: () => void;
  revisionId: string | null;
  readyForGeneration: boolean;
  modulesToPlace: ModuleToPlace[];
}

const RECONCILE_WORDS: Record<string, string> = {
  OK: "Reconciled",
  RECONCILED: "Reconciled",
  RECONCILED_WITH_CONFLICTS: "Reconciled, with conflicts",
  INSUFFICIENT_IMAGES: "Needs photos from more than one angle",
  EMPTY: "Nothing detected to reconcile",
  DEMO_MULTI: "Demo, several photos",
  DEMO_SINGLE: "Demo, one photo",
};

/** A status code as words: "RECONCILED_WITH_CONFLICTS" reads "reconciled with conflicts". */
function phrase(code: string): string {
  return code.replace(/_/g, " ").toLowerCase();
}

function reconcileWords(status: string | null): string {
  if (!status) return "Unknown";
  const s = RECONCILE_WORDS[status] ?? phrase(status);
  return s.charAt(0).toUpperCase() + s.slice(1);
}

function plural(n: number, noun: string): string {
  return `${n} ${noun}${n === 1 ? "" : "s"}`;
}

/** A rig's name; a name two rigs share also carries the id that tells them apart. */
function rigLabel(rack: Rack, all: Rack[]): string {
  const name = rack.name?.trim() || "Untitled rig";
  const shared = all.filter((r) => (r.name?.trim() || "Untitled rig") === name).length > 1;
  return shared ? `${name}, id ${rack.id}` : name;
}

/** Undecided is the normal state of a candidate, so it reads in muted ink, not as a warning. */
function statusTone(status: CandidateStatus | undefined): string {
  return status === "confirmed" ? "success" : status === "rejected" ? "danger" : "neutral";
}

export default function EvidenceStep({
  rackChoices,
  selectedRackId,
  onSelectRack,
  targetRackId,
  state,
  error,
  fileLabel,
  pendingCount,
  onSelectPhotos,
  onDetect,
  candidates,
  fromLiveApi,
  onSetStatus,
  fusion,
  confirmedCount,
  allResolved,
  onCreateRevision,
  revisionId,
  readyForGeneration,
  modulesToPlace,
}: EvidenceStepProps) {
  const reviewing = state === "review" || state === "confirmed";
  const locked = state === "confirmed";
  const showFusion = fusion.entities.length > 0 || fusion.status;

  return (
    <>
      <section className="builder-step" aria-labelledby="photo-title">
        <div className="builder-step__head">
          <h2 id="photo-title">Add modules from photos</h2>
          <p className="muted">
            Detection only suggests modules. Nothing joins the inventory until you confirm it.
          </p>
        </div>
        <div className="panel">
          {rackChoices ? (
            rackChoices.length > 0 ? (
              <label className="field evidence-target" htmlFor="evidence-rack">
                Target rig for evidence
                <select
                  id="evidence-rack"
                  value={selectedRackId ?? ""}
                  onChange={(event) =>
                    onSelectRack(event.target.value ? Number(event.target.value) : null)
                  }
                >
                  <option value="">Demo (no rig)</option>
                  {rackChoices.map((rack) => (
                    <option key={rack.id} value={rack.id}>
                      {rigLabel(rack, rackChoices)}
                    </option>
                  ))}
                </select>
              </label>
            ) : (
              <p className="muted">Create a rig first to detect modules from your own photos.</p>
            )
          ) : null}
          <div className="field">
            <label htmlFor="rig-photo">Rig photo</label>
            <input
              id="rig-photo"
              type="file"
              accept="image/jpeg,image/png,image/webp"
              multiple
              aria-describedby="photo-help photo-error"
              onChange={(event) => onSelectPhotos(event.target.files)}
            />
            <span id="photo-help" className="muted">
              JPEG, PNG, or WebP, up to 12 MB each. Add several angles to reconcile them.
              {targetRackId != null
                ? " Photos upload to the target rig."
                : " Without a target rig, detection runs as a demo."}
            </span>
            {error ? (
              <span id="photo-error" role="alert" className="status status-danger">
                {error}
              </span>
            ) : null}
          </div>
          {state === "ready" ? (
            <div className="evidence-ready">
              <p className="status status-success">Ready to scan: {fileLabel}</p>
              <button className="button button-secondary" type="button" onClick={onDetect}>
                Detect modules
              </button>
            </div>
          ) : null}
          {state === "uploading" ? (
            <p className="status" role="status">
              Uploading {plural(pendingCount, "image")} and reconciling…
            </p>
          ) : null}
        </div>
      </section>

      {reviewing ? (
        <section className="builder-step" aria-labelledby="review-title">
          <div className="builder-step__head">
            <div className="builder-step__title">
              <h2 id="review-title">Review ranked detection candidates</h2>
              {fromLiveApi ? null : <span className="status-chip status-chip--warning">Demo</span>}
            </div>
            <p className="muted">
              Human confirmation required. Provider suggestions stay inferred until you confirm an
              authoritative gallery match.
            </p>
            {fromLiveApi ? null : (
              <p className="muted">
                Demo candidates: these were not detected from your photos.
                {targetRackId == null ? " Choose a target rig to detect from your own." : ""}
              </p>
            )}
          </div>

          {showFusion ? (
            <section className="panel" aria-label="Multi-photo reconciliation">
              <h3>Multi-photo reconciliation</h3>
              <p className="muted" role="status">
                Status: {reconcileWords(fusion.status)}
                {fusion.imageCount ? `, ${plural(fusion.imageCount, "image")}` : ""}
                {fusion.note ? `. ${fusion.note}` : ""}
              </p>
              {fusion.entities.length === 0 ? (
                <p className="muted">No fused entities yet.</p>
              ) : (
                <>
                  <button
                    className="button button-secondary"
                    type="button"
                    onClick={fusion.onConfirmAll}
                    disabled={locked}
                  >
                    Confirm all non-conflict fused
                  </button>
                  <p className="muted builder-note">
                    Confirms only non-conflict fusions, through their representative candidate.
                    Resolve conflicts in the candidate list below.
                  </p>
                  {fusion.feedback ? (
                    <p className="status status-success" role="status">
                      {fusion.feedback}
                    </p>
                  ) : null}
                  <ul className="candidate-list" aria-label="Fused module entities">
                    {fusion.entities.map((entity) => {
                      const applied = fusion.applied[entity.fuse_id];
                      const tone = entity.conflict ? "danger" : statusTone(applied);
                      const statusText = entity.conflict
                        ? `Conflict: ${entity.conflict_notes.join("; ") || "disagreement"}`
                        : applied
                          ? `Applied: ${applied}`
                          : `Status: ${phrase(entity.classification_status)}, not confirmed`;
                      const noRep = !entity.representative_candidate_id;
                      return (
                        <li key={entity.fuse_id} className="detection-row">
                          <div className="detection-row__body">
                            <strong>
                              {entity.manufacturer || "Unknown"} {entity.model || entity.fuse_id}
                            </strong>
                            <p className="muted">
                              Support: {plural(entity.observation_count, "observation")} across{" "}
                              {plural(entity.supporting_image_ids.length, "image")}, mean confidence{" "}
                              {(entity.mean_confidence * 100).toFixed(0)}%
                              {noRep
                                ? ", no representative candidate"
                                : ", linked to ranked candidate"}
                            </p>
                            <p className={`status status-${tone}`}>{statusText}</p>
                          </div>
                          <div
                            className="detection-actions"
                            role="group"
                            aria-label={`Resolve fused ${entity.model || entity.fuse_id}`}
                          >
                            <button
                              className="button button-secondary"
                              type="button"
                              disabled={entity.conflict || noRep || locked}
                              onClick={() => fusion.onApply(entity, "confirmed")}
                            >
                              Confirm fused match
                            </button>
                            <button
                              className="button button-quiet"
                              type="button"
                              disabled={noRep || locked}
                              onClick={() => fusion.onApply(entity, "rejected")}
                            >
                              Reject fused
                            </button>
                            <button
                              className="button button-quiet"
                              type="button"
                              disabled={noRep || locked}
                              onClick={() => fusion.onApply(entity, "deferred")}
                            >
                              Defer fused
                            </button>
                          </div>
                        </li>
                      );
                    })}
                  </ul>
                </>
              )}
            </section>
          ) : null}

          <div className="panel">
            <h3>Candidates, most confident first</h3>
            <ul className="candidate-list" aria-label="Ranked module candidates">
              {candidates.map((candidate) => (
                <li key={candidate.id} className="detection-row">
                  <div className="detection-row__body">
                    <strong>
                      {candidate.manufacturer} {candidate.label}
                    </strong>
                    <p className="muted">
                      Confidence {(candidate.confidence * 100).toFixed(0)}%
                      {candidate.alternatives.length
                        ? `. Alternatives: ${candidate.alternatives.join(", ")}`
                        : ""}
                    </p>
                    <p className={`status status-${statusTone(candidate.status)}`}>
                      Status: {candidate.status}
                    </p>
                    {candidate.decision ? (
                      <div
                        className="status status-neutral"
                        role="group"
                        aria-label="Decision Intelligence advisory"
                      >
                        <strong>Decision Intelligence: advisory only</strong>
                        <span>
                          {": "}
                          {candidate.decision.disposition.replace("_", " ")}
                          {candidate.decision.confidence != null
                            ? `, ${(candidate.decision.confidence * 100).toFixed(0)}%`
                            : ""}
                          {candidate.decision.provider ? `, ${candidate.decision.provider}` : ""}
                        </span>
                        {candidate.decision.reasonCodes?.length ? (
                          <span className="muted">
                            {" "}
                            ({candidate.decision.reasonCodes.join(", ")})
                          </span>
                        ) : null}
                        <p className="muted">
                          This suggestion cannot confirm hardware. Use Confirm match, Reject, or
                          Defer below.
                        </p>
                      </div>
                    ) : null}
                  </div>
                  <div
                    className="detection-actions"
                    role="group"
                    aria-label={`Resolve ${candidate.label}`}
                  >
                    <button
                      className="button button-secondary"
                      type="button"
                      onClick={() => onSetStatus(candidate.id, "confirmed")}
                    >
                      Confirm match
                    </button>
                    <button
                      className="button button-quiet"
                      type="button"
                      onClick={() => onSetStatus(candidate.id, "rejected")}
                    >
                      Reject
                    </button>
                    <button
                      className="button button-quiet"
                      type="button"
                      onClick={() => onSetStatus(candidate.id, "deferred")}
                    >
                      Defer
                    </button>
                  </div>
                </li>
              ))}
            </ul>

            <p className="muted" role="status">
              {confirmedCount} confirmed, {candidates.length - confirmedCount} not confirmed. All
              resolved: {allResolved ? "yes" : "no"}.
            </p>

            <button
              className="button button-primary"
              type="button"
              disabled={!allResolved || confirmedCount < 1 || locked}
              onClick={onCreateRevision}
            >
              Create immutable rig revision
            </button>

            {revisionId ? (
              <>
                <p
                  className={`status status-${readyForGeneration ? "success" : "warning"}`}
                  role="status"
                >
                  Inventory revision sealed: {revisionId}
                  {readyForGeneration ? ", ready for generation" : ", not ready for generation"}.
                  {targetRackId != null ? (
                    <>
                      {" "}
                      <Link to={`/rigs/${targetRackId}`}>
                        {readyForGeneration ? "Generate patches on this rig" : "Open this rig"}
                      </Link>
                    </>
                  ) : null}
                </p>
                <ModulesToPlace modules={modulesToPlace} rackId={targetRackId} />
              </>
            ) : null}
          </div>
        </section>
      ) : null}
    </>
  );
}
