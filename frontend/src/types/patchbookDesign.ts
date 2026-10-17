/**
 * PatchBook Design Engine — StyleRecipe + Layout IR (wire contracts).
 * Mirrors backend/export/patchbook/design/*.py
 * @see docs/design/PATCHBOOK_DESIGN_ENGINE.md
 */

export const STYLE_RECIPE_SCHEMA_VERSION = "patchhive.style_recipe.v1" as const;
export const DESIGN_ENGINE_VERSION = "0.1.0" as const;
export const LAYOUT_IR_SCHEMA_VERSION = "patchhive.layout_ir.v1" as const;

export type PatchBookMode =
  | "professional"
  | "editorial"
  | "collector"
  | "educational"
  | "technical_archive"
  | "symbolic"
  | "abstract"
  | "surreal"
  | "gallery";

export const ARTISTIC_MODES: readonly PatchBookMode[] = [
  "symbolic",
  "abstract",
  "surreal",
  "gallery",
] as const;

export type TemplateFamilyId =
  | "signal_manual"
  | "hive_systems_atlas"
  | "open_state"
  | "modular_field_notes"
  | "oscilloscope_journal"
  | "circuit_archive"
  | "museum_of_signal"
  | "patent_future"
  | "patch_cartography"
  | "sonic_brutalism"
  | "ritual_machine"
  | "impossible_instrument";

export type OutputProfile =
  "print_pdf" | "screen_pdf" | "svg_pack" | "html_companion" | "archive_zip";

export type BookProfile = "execution_page" | "publication";

export type StyleWeights = {
  legibility: number;
  technical_density: number;
  editorial_expression: number;
  symbolism: number;
  abstraction: number;
  surrealism: number;
  ornamentation: number;
  grid_rigidity: number;
  white_space: number;
  visual_motion: number;
  materiality: number;
  brand_presence: number;
  diagram_literalness: number;
  historical_influence: number;
  experimental_typography: number;
};

export type StyleConstraints = {
  book_profile: BookProfile;
  canonical_appendix_required: boolean;
  artistic_disclosure_acknowledged: boolean;
  minimum_body_size_pt: number;
  minimum_contrast_ratio: number;
  color_independent_diagrams: boolean;
  tagged_pdf: boolean;
  force_layout_class?: "diagram_first" | "instruction_first" | "performance_first" | null;
};

export type ConstraintResolutionEvent = {
  code: string;
  severity: "info" | "warning" | "error";
  message: string;
  field?: string | null;
  requested?: number | string | boolean | null;
  resolved?: number | string | boolean | null;
  authority_layer: number;
};

export type RequestStyleRecipe = {
  schema_version: typeof STYLE_RECIPE_SCHEMA_VERSION;
  engine_version: string;
  mode: PatchBookMode;
  template_family: TemplateFamilyId;
  template_family_version: string;
  seed: number;
  weights: StyleWeights;
  influences: Record<string, number>;
  constraints: StyleConstraints;
  output_profile: OutputProfile;
  preset_id?: string | null;
  notes?: string;
};

export type ResolvedStyleRecipe = RequestStyleRecipe & {
  events: ConstraintResolutionEvent[];
  resolved_tier: "free" | "core" | "pro" | "studio";
  zero_state_brand_cap: number;
};

export type PageKind =
  "execution" | "plate" | "front_matter" | "back_matter" | "appendix_execution";

export type StylePreviewResponse = {
  resolved_recipe: ResolvedStyleRecipe;
  resolution_events: ConstraintResolutionEvent[];
  page_svgs: string[];
  layout_irs?: unknown[];
  composition_hash?: string;
};

export const DEFAULT_STYLE_WEIGHTS: StyleWeights = {
  legibility: 90,
  technical_density: 75,
  editorial_expression: 55,
  symbolism: 10,
  abstraction: 5,
  surrealism: 0,
  ornamentation: 20,
  grid_rigidity: 80,
  white_space: 55,
  visual_motion: 35,
  materiality: 25,
  brand_presence: 15,
  diagram_literalness: 90,
  historical_influence: 10,
  experimental_typography: 5,
};

/** Full influence catalog (mirrors backend INFLUENCE_IDS). */
export const ALL_INFLUENCE_IDS = [
  "engineering",
  "scientific",
  "swiss",
  "editorial",
  "industrial",
  "architectural",
  "museum",
  "archival",
  "technical_manual",
  "field_notebook",
  "patent",
  "blueprint",
  "circuit_board",
  "oscilloscope",
  "cyber_hive",
  "brutalist",
  "minimal",
  "luxury",
  "organic",
  "biomorphic",
  "symbolic",
  "ritual",
  "abstract",
  "surreal",
  "futurist",
  "retro_futurist",
  "analog_studio",
  "modular_synth",
  "record_packaging",
  "data_visualization",
  "generative_geometry",
  "open_form_zero_state",
] as const;

export type InfluenceId = (typeof ALL_INFLUENCE_IDS)[number];

export const RECIPE_LIBRARY_STORAGE_KEY = "patchhive.patchbook.recipe_library.v1";

export type SavedStyleRecipe = {
  id: string;
  name: string;
  saved_at: string;
  recipe: RequestStyleRecipe;
};

export function loadRecipeLibrary(): SavedStyleRecipe[] {
  try {
    const raw = localStorage.getItem(RECIPE_LIBRARY_STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as SavedStyleRecipe[];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

export function saveRecipeToLibrary(name: string, recipe: RequestStyleRecipe): SavedStyleRecipe[] {
  const entry: SavedStyleRecipe = {
    id: `recipe-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`,
    name: name.trim() || "Untitled recipe",
    saved_at: new Date().toISOString(),
    recipe,
  };
  const next = [entry, ...loadRecipeLibrary()].slice(0, 40);
  localStorage.setItem(RECIPE_LIBRARY_STORAGE_KEY, JSON.stringify(next));
  return next;
}

export function deleteRecipeFromLibrary(id: string): SavedStyleRecipe[] {
  const next = loadRecipeLibrary().filter((r) => r.id !== id);
  localStorage.setItem(RECIPE_LIBRARY_STORAGE_KEY, JSON.stringify(next));
  return next;
}

export function defaultRequestStyleRecipe(seed = 0): RequestStyleRecipe {
  return {
    schema_version: STYLE_RECIPE_SCHEMA_VERSION,
    engine_version: DESIGN_ENGINE_VERSION,
    mode: "professional",
    template_family: "signal_manual",
    template_family_version: "1.0.0",
    seed,
    weights: { ...DEFAULT_STYLE_WEIGHTS },
    influences: {
      engineering: 92,
      swiss: 65,
      scientific: 55,
      cyber_hive: 24,
    },
    constraints: {
      book_profile: "execution_page",
      canonical_appendix_required: false,
      artistic_disclosure_acknowledged: false,
      minimum_body_size_pt: 9.5,
      minimum_contrast_ratio: 4.5,
      color_independent_diagrams: true,
      tagged_pdf: true,
    },
    output_profile: "print_pdf",
  };
}
