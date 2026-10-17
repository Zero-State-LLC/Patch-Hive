/**
 * TypeScript types matching the backend API schemas.
 */

// Module types
export interface IOPort {
  name: string;
  type: string;
}

export interface Module {
  id: number;
  brand: string;
  name: string;
  hp: number;
  module_type: string;
  power_12v_ma?: number;
  power_neg12v_ma?: number;
  power_5v_ma?: number;
  /** Optional depth for case fit; null/omitted = unspecified. */
  depth_mm?: number | null;
  io_ports: IOPort[];
  tags: string[];
  description?: string;
  manufacturer_url?: string;
  status?: string;
  replacement_module_id?: number | null;
  deprecated_at?: string | null;
  tombstoned_at?: string | null;
  source: string;
  source_reference?: string;
  imported_at: string;
  created_at: string;
  updated_at: string;
}

export interface ModuleListResponse {
  total: number;
  modules: Module[];
}

/** Lightweight module_catalog browse row (research + curated discovery). */
export interface CatalogModule {
  id: number;
  modulargrid_id?: number | null;
  slug: string;
  brand: string;
  name: string;
  hp?: number | null;
  category?: string | null;
  image_url?: string | null;
  modulargrid_url?: string | null;
  manufacturer_url?: string | null;
  is_available?: string | null;
  /** Admit pipeline, e.g. SynthCatalogResearch */
  source?: string | null;
  created_at?: string;
  updated_at?: string;
  /** Registry wiring */
  registry_manufacturer_slug?: string | null;
  registry_device_slug?: string | null;
}

export interface CatalogModuleListResponse {
  total: number;
  skip: number;
  limit: number;
  modules: CatalogModule[];
}

export interface CatalogModuleStats {
  total_modules: number;
  total_brands: number;
  total_categories: number;
  hp_stats: {
    average: number;
    min: number | null;
    max: number | null;
    known: number;
    unknown: number;
    coverage_pct: number;
  };
  /** Counts by module_catalog.source when present */
  by_source?: Record<string, number>;
  availability: {
    available: number;
    discontinued: number;
  };
}

export interface CatalogMaterializeResponse {
  status: "exists" | "created";
  catalog_slug: string;
  module_id: number;
  module: {
    id: number;
    brand: string;
    name: string;
    hp: number;
    module_type: string;
    source: string;
    power_12v_ma?: number;
    power_neg12v_ma?: number;
    io_ports?: IOPort[];
    tags?: string[];
    description?: string;
    registry_manufacturer_slug?: string | null;
    registry_device_slug?: string | null;
  };
}

// Case types
export interface Case {
  id: number;
  brand: string;
  name: string;
  total_hp: number;
  rows: number;
  hp_per_row: number[];
  format_family?: string | null;
  capacity_unit?: string | null;
  powered?: boolean | null;
  power_12v_ma?: number;
  power_neg12v_ma?: number;
  power_5v_ma?: number;
  description?: string;
  manufacturer_url?: string;
  meta?: Record<string, unknown>;
  /** Present when case was materialized from the normalized catalog. */
  catalog_slug?: string | null;
  source: string;
  source_reference?: string;
  created_at: string;
  updated_at: string;
}

export interface CaseListResponse {
  total: number;
  cases: Case[];
}

/** Normalized modular case catalog (additive to legacy Case). */
export interface CatalogRevisionSummary {
  revision_key: string;
  revision_label?: string | null;
  row_count?: number | null;
  capacity_value?: number | null;
  capacity_unit?: string | null;
  depth_min_mm?: number | null;
  depth_max_mm?: number | null;
  portable?: boolean | null;
  removable_lid?: boolean | null;
  integrated_stand?: boolean | null;
  confidence: string;
}

export interface CatalogCaseListItem {
  slug: string;
  manufacturer: string;
  model: string;
  format_family: string;
  production_status: string;
  powered?: boolean | null;
  official_url?: string | null;
  image_url?: string | null;
  primary_revision?: CatalogRevisionSummary | null;
}

export interface CatalogCaseListResponse {
  total: number;
  skip: number;
  limit: number;
  cases: CatalogCaseListItem[];
}

export interface CatalogFormatCount {
  format_family: string;
  case_count: number;
}

export interface CatalogFormatListResponse {
  total: number;
  formats: CatalogFormatCount[];
}

export interface CatalogStatsResponse {
  case_count: number;
  revision_count: number;
  manufacturer_count: number;
  format_family_counts: Record<string, number>;
  powered_counts: Record<string, number>;
  with_power_rails: number;
  with_depth: number;
  with_prices: number;
  with_sources: number;
  source_packet_count: number;
  publication_note?: string;
}

export type CompatibilityStatus = "verified" | "incomplete" | "conflict";

export interface CompatibilityCheck {
  status: CompatibilityStatus;
  code: string;
  message: string;
  details?: Record<string, unknown>;
}

export interface CompatibilityResponse {
  case_slug: string;
  manufacturer: string;
  model: string;
  format_family: string;
  revision_key: string;
  overall_status: CompatibilityStatus;
  format_check: CompatibilityCheck;
  physical_fit: CompatibilityCheck;
  power_headroom: {
    rail: string;
    case_capacity_ma?: number | null;
    module_draw_ma: number;
    headroom_ma?: number | null;
    status: CompatibilityStatus;
    message: string;
  }[];
  connector_availability: CompatibilityCheck;
  pos5_compatibility: CompatibilityCheck;
  lid_close: CompatibilityCheck;
  warnings: CompatibilityCheck[];
  notes: string[];
}

export interface MaterializeCaseResponse {
  created: boolean;
  catalog_slug: string;
  case: Case;
}

// Rack types
export interface RackModuleSpec {
  module_id: number;
  row_index: number;
  start_hp: number;
}

export interface RackModule extends RackModuleSpec {
  id: number;
  module?: {
    id: number;
    brand: string;
    name: string;
    hp: number;
    module_type: string;
    power_12v_ma?: number | null;
    power_neg12v_ma?: number | null;
    power_5v_ma?: number | null;
    depth_mm?: number | null;
  };
}

export interface Rack {
  id: number;
  user_id: number;
  case_id: number;
  name: string;
  name_suggested?: string;
  description?: string;
  tags: string[];
  is_public: boolean;
  generation_seed?: number;
  created_at: string;
  updated_at: string;
  modules: RackModule[];
  case?: {
    id: number;
    brand: string;
    name: string;
    total_hp: number;
    rows: number;
    hp_per_row: number[];
    format_family?: string | null;
    capacity_unit?: string | null;
    powered?: boolean | null;
    power_12v_ma?: number | null;
    power_neg12v_ma?: number | null;
    power_5v_ma?: number | null;
    meta?: Record<string, unknown>;
    catalog_slug?: string | null;
  };
  vote_count: number;
}

export interface RackListResponse {
  total: number;
  racks: Rack[];
}

// Patch types
export interface Connection {
  from_module_id: number;
  from_port: string;
  to_module_id: number;
  to_port: string;
  cable_type: string;
}

export interface Patch {
  id: number;
  rack_id: number;
  run_id?: number | null;
  name: string;
  suggested_name?: string | null;
  name_override?: string | null;
  category: string;
  description?: string;
  tags?: string[];
  difficulty?: string;
  diagram_svg_url?: string;
  connections: Connection[];
  generation_seed: number;
  generation_version: string;
  engine_config?: Record<string, unknown>;
  waveform_svg_path?: string;
  waveform_params?: Record<string, unknown>;
  is_public: boolean;
  created_at: string;
  updated_at: string;
  vote_count: number;
}

export interface PatchListResponse {
  total: number;
  patches: Patch[];
}

export interface Run {
  id: number;
  rack_id: number;
  status: string;
  created_at: string;
  /** Server-authored canon export bridge (do not invent client-side). */
  rig_revision_id: string;
  source_run_id: string;
  artifact_manifest_hash: string;
  export_bridge_ready: boolean;
}

export interface RunListResponse {
  total: number;
  runs: Run[];
}

export interface GeneratePatchesRequest {
  seed?: number;
  max_patches?: number;
  allow_feedback?: boolean;
  prefer_simple?: boolean;
}

export interface GeneratePatchesResponse {
  generated_count: number;
  patches: Patch[];
  run_id?: number;
  export_bridge_ready?: boolean;
  source_run_id?: string | null;
  rig_revision_id?: string | null;
  artifact_manifest_hash?: string | null;
  inventory_revision_id?: string | null;
  inventory_gate_code?: string | null;
  generation_status?: string | null;
}

export interface RunPatchesResponse {
  run_id: number;
  total: number;
  created_at?: string;
  patches: Patch[];
}

// User types
export interface User {
  id: number;
  username: string;
  email: string;
  display_name?: string;
  avatar_url?: string;
  allow_public_avatar?: boolean;
  bio?: string;
  role: string;
  created_at: string;
  updated_at: string;
}

export interface CreditLedgerEntry {
  id: number | string;
  entry_type: string;
  amount: number;
  description?: string;
  created_at: string;
}

export interface CreditsSummary {
  balance: number;
  entries: CreditLedgerEntry[];
}

/** Canonical export record from `/api/canon/exports`. */
export interface CanonicalExportRecord {
  export_id: string;
  status: string;
  credit_cost: number;
  ledger_entry_id: string | null;
  source_run_id: string;
  source_rig_revision_id: string;
  idempotency_key: string;
  created_at: string;
  composition_hash?: string | null;
  style_recipe_hash?: string | null;
  error_code?: string | null;
  pack_manifest_hash?: string | null;
  style_recipe_id?: string | null;
}

export interface UserExportRecord {
  id: number | string;
  export_type: string;
  entity_id: number | string;
  run_id: string;
  unlocked: boolean;
  license_type?: string;
  created_at: string;
  status?: string;
  source?: "canon" | "legacy";
}

export interface ReferralRecord {
  referred_user_id: string;
  status: string;
  rewarded_at?: string;
}

export interface ReferralSummary {
  referral_code: string;
  referral_link: string;
  pending_count: number;
  earned_count: number;
  recent_referrals: ReferralRecord[];
}

export interface LeaderboardEntry {
  rank: number;
  module_name: string;
  manufacturer: string;
  count: number;
}

export interface LoginRequest {
  username: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  user: User;
}

// Feed types
export interface FeedItem {
  type: "rack" | "patch";
  id: number;
  name: string;
  description?: string;
  user: User;
  vote_count: number;
  created_at: string;
}

export interface FeedResponse {
  total: number;
  items: FeedItem[];
}

// Publishing types
export interface ExportArtifactUrls {
  pdf?: string;
  svg?: string;
  zip?: string;
  waveform_svg?: string;
}

export interface ExportRecord {
  id: number;
  export_type: "patch" | "rack";
  license: string;
  run_id: string;
  generated_at: string;
  patch_count?: number;
  manifest_hash: string;
  artifact_urls: ExportArtifactUrls;
}

export interface PublicationRecord {
  id: number;
  export_id: number;
  slug: string;
  visibility: "public" | "unlisted";
  status: "published" | "hidden" | "draft" | "removed";
  allow_download: boolean;
  allow_remix: boolean;
  title: string;
  description?: string;
  cover_image_url?: string;
  published_at?: string;
  updated_at: string;
}

export interface PublicationListResponse {
  publications: PublicationRecord[];
}

export interface PublicPublicationResponse {
  title: string;
  description?: string;
  cover_image_url?: string;
  export_type: "patch" | "rack";
  license: string;
  provenance: {
    run_id: string;
    generated_at: string;
    patch_count?: number;
    manifest_hash: string;
  };
  publisher_display: string;
  avatar_url?: string;
  allow_download: boolean;
  download_urls?: {
    pdf_url: string;
    svg_url: string;
    zip_url: string;
  };
}

export interface PublicationCard {
  slug: string;
  title: string;
  description?: string;
  cover_image_url?: string;
  export_type: "patch" | "rack";
  published_at?: string;
}

export interface GalleryResponse {
  publications: PublicationCard[];
  next_cursor?: string;
}

// Registry / Product Database types (Phase 2)
export interface Manufacturer {
  id: number;
  name: string;
  slug: string;
  aliases?: string[];
  website?: string | null;
  status?: string | null;
}

export interface DeviceModel {
  id: number;
  name: string;
  slug: string;
  brand?: string;
  manufacturer_id?: number;
  hp?: number | null;
  device_type?: string | null;
}

export interface RegistryManufacturerList {
  total: number;
  items: Manufacturer[];
}

export interface RegistrySearchResult {
  results: DeviceModel[];
  total?: number;
}

export interface RegistryCoverage {
  total_manufacturers: number;
  total_models: number;
  hp_known?: number;
  hp_unknown?: number;
  hp_coverage_pct?: number;
}
