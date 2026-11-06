"""Request / resolved StyleRecipe contracts for the PatchBook Design Engine.

Presentation only — never mutates sealed patch content.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from canon.contracts import canonical_sha256

STYLE_RECIPE_SCHEMA_VERSION = "patchhive.style_recipe.v1"
DESIGN_ENGINE_VERSION = "0.3.0"


class PatchBookMode(str, Enum):
    PROFESSIONAL = "professional"
    EDITORIAL = "editorial"
    COLLECTOR = "collector"
    EDUCATIONAL = "educational"
    TECHNICAL_ARCHIVE = "technical_archive"
    SYMBOLIC = "symbolic"
    ABSTRACT = "abstract"
    SURREAL = "surreal"
    GALLERY = "gallery"


ARTISTIC_MODES: frozenset[PatchBookMode] = frozenset(
    {
        PatchBookMode.SYMBOLIC,
        PatchBookMode.ABSTRACT,
        PatchBookMode.SURREAL,
        PatchBookMode.GALLERY,
    }
)


class TemplateFamilyId(str, Enum):
    SIGNAL_MANUAL = "signal_manual"
    HIVE_SYSTEMS_ATLAS = "hive_systems_atlas"
    OPEN_STATE = "open_state"
    MODULAR_FIELD_NOTES = "modular_field_notes"
    OSCILLOSCOPE_JOURNAL = "oscilloscope_journal"
    CIRCUIT_ARCHIVE = "circuit_archive"
    MUSEUM_OF_SIGNAL = "museum_of_signal"
    PATENT_FUTURE = "patent_future"
    PATCH_CARTOGRAPHY = "patch_cartography"
    SONIC_BRUTALISM = "sonic_brutalism"
    RITUAL_MACHINE = "ritual_machine"
    IMPOSSIBLE_INSTRUMENT = "impossible_instrument"


class OutputProfile(str, Enum):
    PRINT_PDF = "print_pdf"
    SCREEN_PDF = "screen_pdf"
    SVG_PACK = "svg_pack"
    HTML_COMPANION = "html_companion"
    ARCHIVE_ZIP = "archive_zip"


class BookProfile(str, Enum):
    EXECUTION_PAGE = "execution_page"
    PUBLICATION = "publication"


INFLUENCE_IDS: tuple[str, ...] = (
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
)


def influence_ids() -> tuple[str, ...]:
    return INFLUENCE_IDS


def _weight_field(default: int) -> Any:
    return Field(default=default, ge=0, le=100)


class StyleWeights(BaseModel):
    """Master control sliders (0–100). Defaults match Design Engine brief."""

    model_config = ConfigDict(extra="forbid")

    legibility: int = _weight_field(90)
    technical_density: int = _weight_field(75)
    editorial_expression: int = _weight_field(55)
    symbolism: int = _weight_field(10)
    abstraction: int = _weight_field(5)
    surrealism: int = _weight_field(0)
    ornamentation: int = _weight_field(20)
    grid_rigidity: int = _weight_field(80)
    white_space: int = _weight_field(55)
    visual_motion: int = _weight_field(35)
    materiality: int = _weight_field(25)
    brand_presence: int = _weight_field(15)
    diagram_literalness: int = _weight_field(90)
    historical_influence: int = _weight_field(10)
    experimental_typography: int = _weight_field(5)


class StyleConstraints(BaseModel):
    """Hard constraints carried with a recipe (shape-validated on request)."""

    model_config = ConfigDict(extra="forbid")

    book_profile: BookProfile = BookProfile.EXECUTION_PAGE
    canonical_appendix_required: bool = False
    artistic_disclosure_acknowledged: bool = False
    minimum_body_size_pt: float = Field(default=9.5, ge=8.0, le=24.0)
    minimum_contrast_ratio: float = Field(default=4.5, ge=3.0, le=21.0)
    color_independent_diagrams: bool = True
    tagged_pdf: bool = True
    force_layout_class: (
        Literal["diagram_first", "instruction_first", "performance_first"] | None
    ) = None


class ConstraintResolutionEvent(BaseModel):
    """Explained clamp / override from the constraint resolver (not silent)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str
    severity: Literal["info", "warning", "error"]
    message: str
    field: str | None = None
    requested: float | str | bool | None = None
    resolved: float | str | bool | None = None
    authority_layer: int = Field(
        ge=1,
        le=10,
        description="1=canonical … 10=seeded variation (design §A.3)",
    )


class RequestStyleRecipe(BaseModel):
    """Client/API request recipe — shape-validated; may be out of resolved range.

    Hard-fail only for invalid schema, unknown family/mode, artistic without
    disclosure/appendix flags, or oversized payload (checked at API boundary).
    Soft clamps (experimental type, family downgrade) happen in the resolver
    and produce a ``ResolvedStyleRecipe``.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: str = STYLE_RECIPE_SCHEMA_VERSION
    engine_version: str = DESIGN_ENGINE_VERSION
    mode: PatchBookMode = PatchBookMode.PROFESSIONAL
    template_family: TemplateFamilyId = TemplateFamilyId.SIGNAL_MANUAL
    template_family_version: str = "1.0.0"
    seed: int = Field(default=0, ge=0, le=2_147_483_647)
    weights: StyleWeights = Field(default_factory=StyleWeights)
    influences: dict[str, int] = Field(default_factory=dict)
    constraints: StyleConstraints = Field(default_factory=StyleConstraints)
    output_profile: OutputProfile = OutputProfile.PRINT_PDF
    preset_id: str | None = None
    notes: str = Field(default="", max_length=500)

    @field_validator("schema_version")
    @classmethod
    def _schema_version_ok(cls, value: str) -> str:
        if value != STYLE_RECIPE_SCHEMA_VERSION:
            raise ValueError(f"unsupported style recipe schema_version: {value}")
        return value

    @field_validator("influences")
    @classmethod
    def _influences_ok(cls, value: dict[str, int]) -> dict[str, int]:
        allowed = set(INFLUENCE_IDS)
        cleaned: dict[str, int] = {}
        for key, weight in value.items():
            if key not in allowed:
                raise ValueError(f"unknown influence id: {key}")
            if not isinstance(weight, int) or weight < 0 or weight > 100:
                raise ValueError(f"influence {key} must be int 0–100")
            if weight > 0:
                cleaned[key] = weight
        return cleaned

    @model_validator(mode="after")
    def _artistic_disclosure_shape(self) -> RequestStyleRecipe:
        """Hard-fail when artistic mode lacks disclosure/appendix flags.

        Resolver may still soft-clamp other weights; this is the only
        mode-gated hard-fail on request shape (KD-6 / KD-16).
        """
        if self.mode in ARTISTIC_MODES:
            if not self.constraints.artistic_disclosure_acknowledged:
                raise ValueError(
                    "artistic modes require constraints.artistic_disclosure_acknowledged=true"
                )
            if not self.constraints.canonical_appendix_required:
                raise ValueError(
                    "artistic modes require constraints.canonical_appendix_required=true"
                )
        return self


class ResolvedStyleRecipe(BaseModel):
    """Post-constraint sealed recipe used for composition and export identity."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = STYLE_RECIPE_SCHEMA_VERSION
    engine_version: str = DESIGN_ENGINE_VERSION
    mode: PatchBookMode
    template_family: TemplateFamilyId
    template_family_version: str
    seed: int = Field(ge=0, le=2_147_483_647)
    weights: StyleWeights
    influences: dict[str, int] = Field(default_factory=dict)
    constraints: StyleConstraints
    output_profile: OutputProfile
    preset_id: str | None = None
    notes: str = ""
    events: tuple[ConstraintResolutionEvent, ...] = ()
    resolved_tier: Literal["free", "core", "pro", "studio"] = "core"
    zero_state_brand_cap: int = Field(
        default=10,
        ge=0,
        le=100,
        description="Zero State parent brand presence; must stay ≤ PatchHive brand_presence",
    )

    @model_validator(mode="after")
    def _zs_cap(self) -> ResolvedStyleRecipe:
        if self.zero_state_brand_cap > self.weights.brand_presence:
            raise ValueError(
                "zero_state_brand_cap must be ≤ weights.brand_presence "
                f"({self.zero_state_brand_cap} > {self.weights.brand_presence})"
            )
        return self


def recipe_hash(recipe: RequestStyleRecipe | ResolvedStyleRecipe) -> str:
    """Deterministic hash of a recipe for idempotency and composition binding."""
    payload = recipe.model_dump(mode="json")
    return canonical_sha256(payload)


def default_request_recipe(
    *,
    mode: PatchBookMode = PatchBookMode.PROFESSIONAL,
    template_family: TemplateFamilyId = TemplateFamilyId.SIGNAL_MANUAL,
    seed: int = 0,
) -> RequestStyleRecipe:
    """Server default recipe for fulfillment when client omits style fields."""
    return RequestStyleRecipe(
        mode=mode,
        template_family=template_family,
        seed=seed,
        influences={"engineering": 92, "swiss": 65, "scientific": 55, "cyber_hive": 24},
    )
