/**
 * API client for PatchHive backend.
 */
import axios from "axios";
import type {
  CatalogMaterializeResponse,
  CatalogModuleListResponse,
  CatalogModuleStats,
  ModuleListResponse,
  CaseListResponse,
  CatalogCaseListResponse,
  CatalogFormatListResponse,
  CatalogStatsResponse,
  CompatibilityResponse,
  MaterializeCaseResponse,
  RackListResponse,
  PatchListResponse,
  GeneratePatchesRequest,
  GeneratePatchesResponse,
  RunListResponse,
  RunPatchesResponse,
  LoginRequest,
  TokenResponse,
  Module,
  Case,
  Rack,
  RackModuleSpec,
  Patch,
  User,
  CanonicalExportRecord,
  ReferralSummary,
  RegistryCoverage,
  RegistryManufacturerList,
  RegistrySearchResult,
  Manufacturer,
  DeviceModel,
} from "@/types/api";
import type {
  AdminUserList,
  AdminGalleryRevisionList,
  AdminRunList,
  AdminLeaderboardEntry,
} from "@/types/admin";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api";

// Create axios instance
const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    "Content-Type": "application/json",
  },
});

// Add auth token to requests
api.interceptors.request.use((config) => {
  const token = localStorage.getItem("auth_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Module API
export const moduleApi = {
  list: (params?: {
    skip?: number;
    limit?: number;
    brand?: string;
    module_type?: string;
    hp_min?: number;
    hp_max?: number;
    tag?: string;
  }) => api.get<ModuleListResponse>("/modules/", { params }),

  /** Lightweight research/curated catalog browse (module_catalog table). */
  catalog: (params?: {
    skip?: number;
    limit?: number;
    search?: string;
    brand?: string;
    category?: string;
    hp_min?: number;
    hp_max?: number;
    hp_known?: boolean;
    is_available?: string;
    source?: string;
    sort_by?: string;
    sort_order?: string;
  }) => api.get<CatalogModuleListResponse>("/modules/catalog", { params }),

  catalogStats: () => api.get<CatalogModuleStats>("/modules/catalog/stats"),

  catalogBrands: () =>
    api.get<{ total: number; brands: { name: string; module_count: number }[] }>(
      "/modules/catalog/brands",
    ),

  catalogCategories: () =>
    api.get<{ total: number; categories: { name: string; module_count: number }[] }>(
      "/modules/catalog/categories",
    ),

  /** Materialize catalog row → full modules record (requires known HP). */
  materializeCatalog: (slug: string) =>
    api.post<CatalogMaterializeResponse>(
      `/modules/catalog/${encodeURIComponent(slug)}/materialize`,
    ),

  /** Bulk materialize HP-known catalog rows into placeable modules. */
  materializeCatalogBatch: (params?: { brand?: string; hp_known_only?: boolean; limit?: number }) =>
    api.post<{
      status: string;
      scanned: number;
      created: number;
      exists: number;
      failed: number;
      failed_samples?: { catalog_slug: string; error: string }[];
    }>("/modules/catalog/materialize-batch", null, { params }),

  get: (id: number) => api.get<Module>(`/modules/${id}`),

  create: (data: Partial<Module>) => api.post<Module>("/modules/", data),

  update: (id: number, data: Partial<Module>) => api.patch<Module>(`/modules/${id}`, data),

  delete: (id: number) => api.delete(`/modules/${id}`),
};

// Case API
export type CaseListParams = {
  skip?: number;
  limit?: number;
  brand?: string;
  min_hp?: number;
  max_hp?: number;
  q?: string;
  format_family?: string;
  powered?: boolean;
  min_rows?: number;
};

export const caseApi = {
  list: (params?: CaseListParams) => api.get<CaseListResponse>("/cases/", { params }),

  get: (id: number) => api.get<Case>(`/cases/${id}`),

  create: (data: Partial<Case>) => api.post<Case>("/cases/", data),

  update: (id: number, data: Partial<Case>) => api.patch<Case>(`/cases/${id}`, data),

  delete: (id: number) => api.delete(`/cases/${id}`),
};

/** Normalized modular case catalog + compatibility + legacy materialize bridge. */
export type CatalogListParams = {
  skip?: number;
  limit?: number;
  manufacturer?: string;
  format_family?: string;
  production_status?: string;
  powered?: boolean;
  q?: string;
  capacity_unit?: string;
  min_capacity?: number;
  max_capacity?: number;
  min_rows?: number;
  min_depth_mm?: number;
  min_pos12_ma?: number;
  portable?: boolean;
  feature_key?: string;
};

export const caseCatalogApi = {
  list: (params?: CatalogListParams) =>
    api.get<CatalogCaseListResponse>("/cases/catalog", { params }),

  formats: () => api.get<CatalogFormatListResponse>("/cases/catalog/formats"),

  stats: () => api.get<CatalogStatsResponse>("/cases/catalog/stats"),

  get: (slug: string) => api.get(`/cases/catalog/${encodeURIComponent(slug)}`),

  materialize: (slug: string, revision_key?: string) =>
    api.post<MaterializeCaseResponse>(
      `/cases/catalog/${encodeURIComponent(slug)}/materialize`,
      null,
      { params: revision_key ? { revision_key } : undefined },
    ),

  materializeBatch: (params?: { format_family?: string; limit?: number }) =>
    api.post<{
      status: string;
      scanned: number;
      created: number;
      updated: number;
      failed: number;
      failures: { catalog_slug: string; error: string }[];
    }>("/cases/catalog/materialize-batch", null, { params }),

  compatibility: (
    slug: string,
    body: {
      revision_key?: string;
      plan_close_lid?: boolean;
      modules?: {
        module_id?: number;
        name?: string;
        row_index?: number;
        start_hp?: number;
        hp?: number;
        depth_mm?: number;
        format_family?: string;
        power_12v_ma?: number;
        power_neg12v_ma?: number;
        power_5v_ma?: number;
      }[];
    },
  ) =>
    api.post<CompatibilityResponse>(
      `/cases/catalog/${encodeURIComponent(slug)}/compatibility`,
      body,
    ),
};

// Rack API
export const rackApi = {
  list: (params?: { skip?: number; limit?: number; is_public?: boolean; user_id?: number }) =>
    api.get<RackListResponse>("/racks/", { params }),

  get: (id: number) => api.get<Rack>(`/racks/${id}`),

  create: (data: Partial<Rack>) => api.post<Rack>("/racks/", data),

  update: (id: number, data: Partial<Omit<Rack, "modules">> & { modules?: RackModuleSpec[] }) =>
    api.patch<Rack>(`/racks/${id}`, data),

  delete: (id: number) => api.delete(`/racks/${id}`),

  /** Catalog compatibility for a rack's placed modules (requires meta.catalog_slug). */
  compatibility: (id: number, params?: { plan_close_lid?: boolean }) =>
    api.get<{
      bridge_status: string;
      message: string;
      catalog_slug?: string | null;
      case_id?: number;
      module_count?: number;
      compatibility?: CompatibilityResponse | null;
    }>(`/racks/${id}/compatibility`, { params }),
};

// Patch API
export const patchApi = {
  list: (params?: {
    skip?: number;
    limit?: number;
    rack_id?: number;
    category?: string;
    is_public?: boolean;
  }) => api.get<PatchListResponse>("/patches", { params }),

  get: (id: number) => api.get<Patch>(`/patches/${id}`),

  create: (data: Partial<Patch>) => api.post<Patch>("/patches", data),

  update: (id: number, data: Partial<Patch>) => api.patch<Patch>(`/patches/${id}`, data),

  delete: (id: number) => api.delete(`/patches/${id}`),

  generate: (rackId: number, request: GeneratePatchesRequest) =>
    api.post<GeneratePatchesResponse>(`/patches/generate/${rackId}`, request),
};

// Visual evidence API (photo → candidates → confirmation → inventory)
export interface EvidenceCandidate {
  candidate_id: string;
  entity_type: string;
  manufacturer?: string | null;
  model?: string | null;
  confidence: number;
  confidence_method: string;
  alternative_candidates: string[];
  classification_status: string;
  evidence_id: string;
  image_asset_id?: string | null;
  gallery_revision_id?: string | null;
  gallery_module_id?: string | null;
  /** Optional, non-authoritative Decision Intelligence projection. */
  decision_advisory?: {
    disposition: "auto_propose" | "user_review" | "unresolved" | "escalate" | "reject";
    provider?: string;
    confidence?: number | null;
    reason_codes?: string[];
  } | null;
}

export interface EvidenceCandidateListResponse {
  total: number;
  candidates: EvidenceCandidate[];
}

export interface MultiImageUploadResponse {
  uploaded: Array<{
    id: string;
    rack_id: number;
    content_sha256: string;
    evidence_status?: string | null;
  }>;
  rejected: Array<{ filename: string; reason: string }>;
}

export interface ConfirmationBatchResponse {
  inventory_revision_id: string;
  inventory_canonical_hash?: string | null;
  confirmed_count: number;
  unresolved_candidate_ids: string[];
  ready_for_generation: boolean;
}

export interface InventoryRevisionSummary {
  inventory_revision_id: string;
  system_id: string;
  rack_id?: number | null;
  confirmed_count: number;
  unresolved_count: number;
  ready_for_generation: boolean;
  canonical_hash?: string | null;
  created_by?: string | null;
  created_at?: string | null;
}

export interface InventoryRevisionListResponse {
  total: number;
  latest: InventoryRevisionSummary | null;
  revisions: InventoryRevisionSummary[];
}

/** F4: evidence under canon prefix (rig_id ≡ rack_id). Legacy /racks/.../evidence still works. */
const evidencePath = (rigId: number, suffix: string) => `/canon/rigs/${rigId}/evidence/${suffix}`;

export const evidenceApi = {
  uploadImages: (
    rackId: number,
    files: File[],
    options?: {
      retention_days?: number;
      consent_provider_processing?: boolean;
      run_vision_mock?: boolean;
    },
  ) => {
    const form = new FormData();
    files.forEach((file) => form.append("files", file));
    form.append("retention_days", String(options?.retention_days ?? 30));
    form.append(
      "consent_provider_processing",
      String(options?.consent_provider_processing ?? false),
    );
    form.append("run_vision_mock", String(options?.run_vision_mock ?? true));
    return api.post<MultiImageUploadResponse>(evidencePath(rackId, "images"), form, {
      headers: { "Content-Type": "multipart/form-data" },
    });
  },

  listImages: (rackId: number) => api.get(evidencePath(rackId, "images")),

  listCandidates: (rackId: number) =>
    api.get<EvidenceCandidateListResponse>(evidencePath(rackId, "candidates")),

  reconcile: (rackId: number) =>
    api.get<{
      image_asset_ids: string[];
      image_count: number;
      fused_entities: Array<{
        fuse_id: string;
        entity_key: string;
        manufacturer?: string | null;
        model?: string | null;
        entity_type: string;
        observation_count: number;
        supporting_image_ids: string[];
        mean_confidence: number;
        max_confidence: number;
        conflict: boolean;
        conflict_notes: string[];
        classification_status: string;
        representative_candidate_id?: string | null;
      }>;
      unmatched_candidate_ids: string[];
      conflict_count: number;
      status: string;
      note: string;
    }>(evidencePath(rackId, "reconcile")),

  confirm: (
    rackId: number,
    body: {
      confirmed_by?: string;
      decisions: Array<{
        candidate_id: string;
        status: string;
        module_revision_id?: string | null;
        notes?: string | null;
      }>;
    },
  ) => api.post<ConfirmationBatchResponse>(evidencePath(rackId, "confirmations"), body),

  listInventory: (rackId: number) =>
    api.get<InventoryRevisionListResponse>(evidencePath(rackId, "inventory")),
};

// Run API — list prefers canon alias; patches still legacy until dual-written.
export const runApi = {
  /** @deprecated Prefer `canonApi.listRuns` (same bridge DTO). */
  list: (rackId: number) => api.get<RunListResponse>("/canon/runs", { params: { rig_id: rackId } }),
  patches: (runId: number) => api.get<RunPatchesResponse>(`/runs/${runId}/patches`),
};

// Auth API
export const authApi = {
  login: (data: LoginRequest) => api.post<TokenResponse>("/community/auth/login", data),

  register: (data: { username: string; email: string; password: string }) =>
    api.post<User>("/community/users", data),

  getUser: (id: number) => api.get<User>(`/community/users/${id}`),

  getUserByUsername: (username: string) => api.get<User>(`/community/users/username/${username}`),

  updateProfile: (data: {
    avatar_url?: string;
    bio?: string;
    display_name?: string;
    allow_public_avatar?: boolean;
  }) => api.patch<User>("/community/users/me", data),

  getMe: () => api.get<User>("/community/users/me"),
};

// Community social API clients live under `src/legacy/apiClients.ts` (unrouted MVP).

// Export API
// PDF/SVG file URLs remain on legacy `/export/*` (artifact bytes).
// Debited patch-book requests must use `canonApi.createExport` (ledger boundary).
export const exportApi = {
  patchPdf: (patchId: number) => `${API_BASE_URL}/export/patches/${patchId}/pdf`,

  rackPdf: (rackId: number) => `${API_BASE_URL}/export/racks/${rackId}/pdf`,

  rackLayoutSvg: (rackId: number) => `${API_BASE_URL}/export/racks/${rackId}/layout.svg`,

  patchDiagramSvg: (patchId: number) => `${API_BASE_URL}/export/patches/${patchId}/diagram.svg`,

  patchWaveformSvg: (patchId: number) => `${API_BASE_URL}/export/patches/${patchId}/waveform.svg`,
};

// Canonical credits + exports (preferred MVP monetization boundary)
export const canonApi = {
  /** Matrix slice B — same bridge DTO as GET /api/runs?rack_id= */
  listRuns: (rigId: number) =>
    api.get<RunListResponse>("/canon/runs", { params: { rig_id: rigId } }),

  getBalance: () => api.get<{ balance: number }>("/canon/credits/balance"),

  getCreditsSummary: () =>
    api.get<{
      balance: number;
      entries: Array<{
        id: string;
        delta: number;
        entry_type: string;
        export_id: string | null;
        created_at: string;
      }>;
    }>("/canon/credits/summary"),

  listExports: () => api.get<CanonicalExportRecord[]>("/canon/exports"),

  getExport: (exportId: string) => api.get<CanonicalExportRecord>(`/canon/exports/${exportId}`),

  createExport: (body: {
    source_run_id: string;
    source_rig_revision_id: string;
    artifact_manifest_hash: string;
    formats?: Array<"pdf" | "svg" | "json" | "zip">;
    license?: string;
    credit_cost?: number | null;
    idempotency_key: string;
    style_recipe?: Record<string, unknown> | null;
    style_recipe_id?: string | null;
  }) => api.post<CanonicalExportRecord>("/canon/exports", body),

  /** Free Design Engine preview — no debit (KD-15). */
  previewExport: (body: {
    source_run_id: string;
    source_rig_revision_id: string;
    artifact_manifest_hash: string;
    style_recipe?: Record<string, unknown> | null;
    style_recipe_id?: string | null;
    max_pages?: number;
  }) =>
    api.post<{
      resolved_recipe: Record<string, unknown>;
      resolution_events: Array<{
        code: string;
        severity: string;
        message: string;
        field?: string | null;
      }>;
      style_recipe_hash: string;
      library_content_hash: string;
      load_path: string;
      page_summaries: Array<{
        position: number;
        title: string;
        intent: string;
        edge_count: number;
        steps: Array<{ phase: string; instruction: string }>;
        warnings?: Array<{ code: string; severity: string; message: string }>;
      }>;
      composition_preview_hash?: string | null;
    }>("/canon/exports/preview", body),

  listStyleRecipes: () =>
    api.get<
      Array<{
        id: string;
        name: string;
        notes: string | null;
        style_recipe: Record<string, unknown>;
        recipe_hash: string;
        created_at: string;
        updated_at: string;
      }>
    >("/canon/style-recipes"),

  createStyleRecipe: (body: {
    name: string;
    style_recipe: Record<string, unknown>;
    notes?: string | null;
  }) =>
    api.post<{
      id: string;
      name: string;
      notes: string | null;
      style_recipe: Record<string, unknown>;
      recipe_hash: string;
      created_at: string;
      updated_at: string;
    }>("/canon/style-recipes", body),

  deleteStyleRecipe: (recipeId: string) =>
    api.delete(`/canon/style-recipes/${encodeURIComponent(recipeId)}`),

  createDownloadToken: (exportId: string, ttl_seconds = 300) =>
    api.post<{ export_id: string; token: string; ttl_seconds: number }>(
      `/canon/exports/${exportId}/download-token`,
      { ttl_seconds },
    ),

  /** Build authenticated artifact URL (requires prior download token). */
  exportArtifactUrl: (
    exportId: string,
    artifact: "pdf" | "companion" | "manifest" | "zip",
    token: string,
  ) => {
    const base = API_BASE_URL.replace(/\/$/, "");
    const q = new URLSearchParams({ token });
    return `${base}/canon/exports/${encodeURIComponent(exportId)}/artifacts/${artifact}?${q}`;
  },

  updateStyleRecipe: (
    recipeId: string,
    body: {
      name?: string;
      style_recipe?: Record<string, unknown>;
      notes?: string | null;
      is_shared?: boolean;
    },
  ) =>
    api.patch<{
      id: string;
      name: string;
      notes: string | null;
      style_recipe: Record<string, unknown>;
      recipe_hash: string;
      is_shared: boolean;
      created_at: string;
      updated_at: string;
    }>(`/canon/style-recipes/${encodeURIComponent(recipeId)}`, body),

  getSharedStyleRecipe: (recipeId: string) =>
    api.get<{
      id: string;
      name: string;
      notes: string | null;
      style_recipe: Record<string, unknown>;
      recipe_hash: string;
      is_shared: boolean;
      created_at: string;
      updated_at: string;
    }>(`/canon/style-recipes/shared/${encodeURIComponent(recipeId)}`),

  /** F2: list inventory rigs via canon prefix (rig_id ≡ rack_id). Optional FE cutover. */
  listRigs: (params?: { skip?: number; limit?: number; is_public?: boolean; user_id?: number }) => {
    const q = new URLSearchParams();
    if (params?.skip != null) q.set("skip", String(params.skip));
    if (params?.limit != null) q.set("limit", String(params.limit));
    if (params?.is_public != null) q.set("is_public", String(params.is_public));
    if (params?.user_id != null) q.set("user_id", String(params.user_id));
    const qs = q.toString();
    return api.get<{
      total: number;
      rigs: Array<{
        rig_id: number;
        rack_id: number;
        user_id: number;
        case_id: number;
        name: string | null;
        name_suggested: string | null;
        description: string | null;
        tags: string[];
        is_public: boolean;
        module_count: number;
        created_at: string;
        updated_at: string;
      }>;
    }>(`/canon/rigs${qs ? `?${qs}` : ""}`);
  },

  /** F2: single inventory rig (≡ GET /api/racks/{id}). */
  getRig: (rigId: number) =>
    api.get<{
      rig_id: number;
      rack_id: number;
      user_id: number;
      case_id: number;
      name: string | null;
      name_suggested: string | null;
      description: string | null;
      tags: string[];
      is_public: boolean;
      module_count: number;
      created_at: string;
      updated_at: string;
      generation_seed: number | null;
      modules: Array<Record<string, unknown>>;
      case: Record<string, unknown> | null;
      vote_count: number;
    }>(`/canon/rigs/${rigId}`),

  listRevisions: (rigId: number) =>
    api.get<{
      total: number;
      revisions: Array<{
        rig_revision_id: string;
        content_hash?: string | null;
        run_count: number;
        latest_run_id?: number | null;
        latest_run_at?: string | null;
        export_bridge_ready: boolean;
      }>;
    }>(`/canon/rigs/${rigId}/revisions`),

  getOverlay: (patchRef: string) =>
    api.get<{
      id: string;
      patch_ref: string;
      notes: string | null;
      favorite: boolean;
      tried: boolean;
      updated_at: string;
    }>(`/canon/overlays/${encodeURIComponent(patchRef)}`),

  upsertOverlay: (
    patchRef: string,
    body: { notes?: string | null; favorite?: boolean; tried?: boolean },
  ) =>
    api.put<{
      id: string;
      patch_ref: string;
      notes: string | null;
      favorite: boolean;
      tried: boolean;
      updated_at: string;
    }>(`/canon/overlays/${encodeURIComponent(patchRef)}`, body),
};

export function legacyPatchRef(patchId: number): string {
  return `legacy-patch-${patchId}`;
}

// Monetization API — balance is a thin alias over the canonical ledger.
export const monetizationApi = {
  balance: () => canonApi.getBalance(),
};

// Admin API
export const adminApi = {
  listUsers: (query?: string) =>
    api.get<AdminUserList>("/admin/users", { params: query ? { query } : undefined }),

  updateUserRole: (userId: number, role: string, reason: string) =>
    api.patch(`/admin/users/${userId}/role`, { role, reason }),

  updateUserAvatar: (userId: number, avatar_url: string | null, reason: string) =>
    api.patch(`/admin/users/${userId}/avatar`, { avatar_url, reason }),

  grantCredits: (userId: number, credits: number, reason: string) =>
    api.post(`/admin/users/${userId}/credits/grant`, { credits, reason }),

  createModule: (payload: Record<string, unknown>) => api.post(`/admin/modules`, payload),

  importModules: (payload: Record<string, unknown>) => api.post(`/admin/modules/import`, payload),

  updateModuleStatus: (moduleId: number, status: string, reason: string) =>
    api.patch(`/admin/modules/${moduleId}/status`, { status, reason }),

  mergeModule: (moduleId: number, replacement_module_id: number, reason: string) =>
    api.patch(`/admin/modules/${moduleId}/merge`, { replacement_module_id, reason }),

  listGalleryRevisions: (status?: string) =>
    api.get<AdminGalleryRevisionList>("/admin/gallery/revisions", {
      params: status ? { status } : undefined,
    }),

  approveRevision: (revisionId: number) =>
    api.post(`/admin/gallery/revisions/${revisionId}/approve`),

  confirmRevision: (revisionId: number) =>
    api.post(`/admin/gallery/revisions/${revisionId}/confirm`),

  listRuns: (status?: string) =>
    api.get<AdminRunList>("/admin/runs", { params: status ? { status } : undefined }),

  rerunRig: (rigId: number) => api.post(`/admin/runs/${rigId}/rerun`),

  unlockExport: (exportId: number, reason: string) =>
    api.post(`/admin/exports/${exportId}/unlock`, { reason }),

  revokeExport: (exportId: number, reason: string) =>
    api.post(`/admin/exports/${exportId}/revoke`, { reason }),

  invalidateCache: (payload: { run_id?: number; export_type?: string; reason: string }) =>
    api.post(`/admin/cache/invalidate`, payload),

  popularModules: () => api.get<AdminLeaderboardEntry[]>(`/admin/leaderboards/modules/popular`),

  trendingModules: (window_days: number) =>
    api.get<AdminLeaderboardEntry[]>(`/admin/leaderboards/modules/trending`, {
      params: { window_days },
    }),

  exportedCategories: () =>
    api.get<AdminLeaderboardEntry[]>(`/admin/leaderboards/categories/exported`),
};

// Publishing / leaderboard clients live under `src/legacy/apiClients.ts`.

// Account API
// Credits/exports prefer the canonical ledger. Referrals remain legacy-flagged.
export const accountApi = {
  getCredits: async () => {
    const summary = await canonApi.getCreditsSummary();
    return {
      ...summary,
      data: {
        balance: summary.data.balance,
        entries: summary.data.entries.map((entry) => ({
          id: entry.id,
          entry_type: entry.entry_type,
          amount: entry.delta,
          description: entry.export_id ? `export ${entry.export_id}` : undefined,
          created_at: entry.created_at,
        })),
      },
    };
  },
  getExports: async () => {
    const listed = await canonApi.listExports();
    return {
      ...listed,
      data: listed.data.map((record) => ({
        id: record.export_id,
        export_type: "canon",
        entity_id: record.source_run_id,
        run_id: record.source_run_id,
        unlocked:
          record.status === "succeeded" ||
          record.status === "queued" ||
          record.status === "running",
        license_type: undefined,
        created_at: record.created_at,
        status: record.status,
        source: "canon" as const,
      })),
    };
  },
  getReferrals: () => api.get<ReferralSummary>("/me/referrals"),
};

// Registry / PDB API (Phase 2)
export const registryApi = {
  listManufacturers: (params?: { limit?: number; offset?: number }) =>
    api.get<RegistryManufacturerList>("/registry/manufacturers", { params }),
  search: (q: string, limit = 20) =>
    api.get<RegistrySearchResult>("/registry/search", { params: { q, limit } }),
  getCoverage: () => api.get<RegistryCoverage>("/registry/coverage"),
  getManufacturer: (slug: string) => api.get<Manufacturer>(`/registry/manufacturers/${slug}`),
  listModelsForManufacturer: (slug: string) =>
    api.get<{ models: DeviceModel[] }>(`/registry/manufacturers/${slug}/models`),
};

export default api;
