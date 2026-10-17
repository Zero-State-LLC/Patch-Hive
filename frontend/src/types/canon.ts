export const CANON_SCHEMA_VERSION = "patchhive.canon.v1" as const;
export type EpistemicStatus = "confirmed" | "inferred" | "disputed" | "missing";
export type SignalType = "audio" | "cv" | "gate" | "trigger" | "clock" | "unknown";
export type PortDirection = "input" | "output" | "bidirectional";

export interface PatchPort {
  schema_version: typeof CANON_SCHEMA_VERSION;
  port_id: string;
  module_instance_id: string;
  module_port_id: string;
  label: string;
  direction: PortDirection;
  signal_type: SignalType;
  active_modes?: string[];
}

export interface PatchNode {
  schema_version: typeof CANON_SCHEMA_VERSION;
  node_id: string;
  module_instance_id: string;
  label: string;
  active_mode?: string | null;
  ports: PatchPort[];
}

export interface PatchEdge {
  schema_version: typeof CANON_SCHEMA_VERSION;
  edge_id: string;
  source_port_id: string;
  target_port_id: string;
  signal_type: SignalType;
  attenuate?: boolean;
  breaks_normal?: boolean;
  feedback_cycle_id?: string | null;
}

export interface PatchGraph {
  schema_version: typeof CANON_SCHEMA_VERSION;
  artifact_id: string;
  nodes: PatchNode[];
  edges: PatchEdge[];
}

export interface EvidenceRecord {
  schema_version: typeof CANON_SCHEMA_VERSION;
  evidence_id: string;
  source_type: "manual" | "gallery" | "photo" | "provider" | "import";
  captured_at: string;
  confidence: number;
  status: EpistemicStatus;
}
export interface DetectedModule {
  schema_version: typeof CANON_SCHEMA_VERSION;
  detection_id: string;
  label_guess: string;
  evidence: EvidenceRecord[];
  confidence: number;
  status: EpistemicStatus;
}
export interface ResolvedModuleRef {
  schema_version: typeof CANON_SCHEMA_VERSION;
  detection_id: string;
  module_gallery_id?: string | null;
  module_revision_id?: string | null;
  confidence: number;
  status: EpistemicStatus;
}
export interface ModuleGalleryEntry {
  schema_version: typeof CANON_SCHEMA_VERSION;
  module_gallery_id: string;
  manufacturer: string;
  name: string;
  current_revision_id?: string | null;
  status: EpistemicStatus;
}
export interface ModuleRevision {
  schema_version: typeof CANON_SCHEMA_VERSION;
  module_revision_id: string;
  module_gallery_id: string;
  previous_revision_id?: string | null;
  ports: PatchPort[];
  status: EpistemicStatus;
  created_at: string;
}
export interface RigModule {
  schema_version: typeof CANON_SCHEMA_VERSION;
  instance_id: string;
  module_revision_id: string;
  position: number;
}
export interface RigSpec {
  schema_version: typeof CANON_SCHEMA_VERSION;
  rig_id: string;
  name: string;
  modules: RigModule[];
  evidence: EvidenceRecord[];
}
export interface CanonicalRig {
  schema_version: typeof CANON_SCHEMA_VERSION;
  rig_id: string;
  rig_revision_id: string;
  modules: RigModule[];
  canonical_hash: string;
}
export interface RigRevision {
  schema_version: typeof CANON_SCHEMA_VERSION;
  rig_revision_id: string;
  rig_id: string;
  previous_revision_id?: string | null;
  canonical_rig: CanonicalRig;
  created_at: string;
}
export interface CanonicalArtifactIdentity {
  schema_version: typeof CANON_SCHEMA_VERSION;
  artifact_id: string;
  entity_id: string;
  generator_version: string;
  generation_seed: number;
  canonical_hash?: string | null;
  source_run_id: string;
  source_rig_revision_id: string;
  created_at: string;
  provenance: EvidenceRecord[];
  confidence: number;
  status: EpistemicStatus;
}
export interface RigMetricsPacket extends CanonicalArtifactIdentity {
  module_count: number;
  total_hp?: number | null;
  routing_flex_score: number;
  confidence_notes: string[];
}
export interface LayoutPlacement {
  schema_version: typeof CANON_SCHEMA_VERSION;
  instance_id: string;
  row: number;
  start_hp: number;
}
export interface SuggestedLayout extends CanonicalArtifactIdentity {
  layout_id: string;
  label: string;
  placements: LayoutPlacement[];
  score: number;
}
export type PatchPhase = "prep" | "threshold" | "peak" | "release" | "seal";
export interface PatchStep {
  schema_version: typeof CANON_SCHEMA_VERSION;
  position: number;
  phase: PatchPhase;
  instruction: string;
  expected_result?: string | null;
  warning?: string | null;
}
export interface PatchVariation {
  schema_version: typeof CANON_SCHEMA_VERSION;
  variation_id: string;
  label: string;
  generation_seed: number;
  graph_hash: string;
}
export interface PatchPlan extends CanonicalArtifactIdentity {
  title: string;
  intent: string;
  steps: PatchStep[];
  variations: PatchVariation[];
}
export interface ValidationIssue {
  schema_version: typeof CANON_SCHEMA_VERSION;
  code: string;
  severity: "info" | "warning" | "error" | "critical";
  message: string;
  edge_id?: string | null;
  module_instance_id?: string | null;
  remediation?: string | null;
}
export interface ValidationReport extends CanonicalArtifactIdentity {
  valid: boolean;
  issues: ValidationIssue[];
}
export interface SymbolicPatchEnvelope extends CanonicalArtifactIdentity {
  topology_hash: string;
  signal_domains: string[];
  feedback_cycle_ids: string[];
  closure_strength: number;
}
export interface ManifestArtifact {
  schema_version: typeof CANON_SCHEMA_VERSION;
  path: string;
  media_type: string;
  byte_length: number;
  sha256: string;
}
export interface StageReceipt extends CanonicalArtifactIdentity {
  stage: string;
  operation: string;
  operation_version: string;
  determinism_class: "deterministic" | "evidence_acquisition";
  input_hash: string;
  output_hash: string;
  permitted_side_effects: string[];
}
export interface ArtifactManifest extends CanonicalArtifactIdentity {
  artifacts: ManifestArtifact[];
  stage_receipts: StageReceipt[];
}
export interface GenerationRequest {
  schema_version: typeof CANON_SCHEMA_VERSION;
  request_id: string;
  user_id: number;
  rig_revision_id: string;
  seed: number;
  generator_version: string;
  idempotency_key: string;
  requested_at: string;
}
export interface GenerationJob {
  schema_version: typeof CANON_SCHEMA_VERSION;
  job_id: string;
  request_id: string;
  run_id: string;
  status: "queued" | "running" | "succeeded" | "failed";
  attempts: number;
  error_code?: string | null;
  created_at: string;
  updated_at: string;
}
export interface ExportRequest {
  schema_version: typeof CANON_SCHEMA_VERSION;
  request_id: string;
  user_id: number;
  source_run_id: string;
  source_rig_revision_id: string;
  formats: ("pdf" | "svg" | "json" | "zip")[];
  license: string;
  credit_cost: number;
  idempotency_key: string;
  requested_at: string;
}
export interface ExportRecord {
  schema_version: typeof CANON_SCHEMA_VERSION;
  export_id: string;
  user_id: number;
  source_run_id: string;
  source_rig_revision_id: string;
  artifact_manifest_hash: string;
  export_version: string;
  license: string;
  credit_cost: number;
  ledger_entry_id: string;
  status: "queued" | "running" | "succeeded" | "failed" | "refunded";
  created_at: string;
}
export interface CreditLedgerEntry {
  schema_version: typeof CANON_SCHEMA_VERSION;
  ledger_entry_id: string;
  user_id: number;
  delta: number;
  entry_type: "purchase" | "debit" | "grant" | "refund" | "reversal";
  idempotency_key: string;
  export_id?: string | null;
  created_at: string;
}
export interface StripeEventRecord {
  schema_version: typeof CANON_SCHEMA_VERSION;
  stripe_event_id: string;
  event_type: string;
  payload_hash: string;
  livemode: boolean;
  status: "received" | "processed" | "rejected";
  received_at: string;
  processed_at?: string | null;
}
export interface AdminAuditEvent {
  schema_version: typeof CANON_SCHEMA_VERSION;
  audit_event_id: string;
  actor_user_id: number;
  actor_role: string;
  action: string;
  target_type: string;
  target_id: string;
  before_hash?: string | null;
  after_hash?: string | null;
  reason: string;
  created_at: string;
}
export interface UserPatchAnnotation {
  schema_version: typeof CANON_SCHEMA_VERSION;
  annotation_id: string;
  user_id: number;
  patch_id: string;
  notes?: string | null;
  favorite: boolean;
  tried: boolean;
  updated_at: string;
}
