import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import {
  canonApi,
  caseApi,
  caseCatalogApi,
  moduleApi,
  evidenceApi,
  rackApi,
  type EvidenceCandidate,
} from "@/lib/api";
import { rigDetailToRack, rigSummaryToRack } from "@/lib/canonRigAdapter";
import CaseStep from "@/components/builder/CaseStep";
import EvidenceStep, {
  type CandidateStatus,
  type EvidenceState,
  type FusedEntityView,
  type ReviewCandidate,
} from "@/components/builder/EvidenceStep";
import PlacementStep, { type RackCompat } from "@/components/builder/PlacementStep";
import Toast from "@/components/Toast";
import { failureReason } from "@/lib/loadError";
import { checkSlot, moveTo, slotPhrase, type Slot } from "@/lib/placementMove";
import { firstFreeStartHp, packModulesOntoRows } from "@/lib/placementPack";
import { placementPower, railMeter, summarizePower, type RailKey } from "@/lib/powerBudget";
import { useAuthStore } from "@/lib/store";
import { useDebouncedValue } from "@/lib/useDebouncedValue";
import { useToast } from "@/lib/useToast";
import type { Case, CatalogCaseListItem, Module, Rack, RackModuleSpec } from "@/types/api";

/** Demo ranked set when no rack id is available (create flow); shown with a Demo label. */
const DEMO_CANDIDATES: ReviewCandidate[] = [
  {
    id: "cand-mod-a",
    label: "Oscillator A",
    manufacturer: "MockAudio",
    confidence: 0.81,
    alternatives: ["Oscillator A (higher-gain revision)"],
    status: "inferred",
    moduleRevisionId: "catalog-module-osc-a",
  },
  {
    id: "cand-mod-b",
    label: "VCA B",
    manufacturer: "MockAudio",
    confidence: 0.64,
    alternatives: [],
    status: "inferred",
    moduleRevisionId: "catalog-module-vca-b",
  },
];

const BUILDER_STEPS = [
  { n: 1, label: "Case" },
  { n: 2, label: "Create rig" },
  { n: 3, label: "Place modules" },
] as const;

function mapApiCandidates(rows: EvidenceCandidate[]): ReviewCandidate[] {
  return rows.map((row) => ({
    id: row.candidate_id,
    label: row.model || row.entity_type || row.candidate_id,
    manufacturer: row.manufacturer || "Unknown",
    confidence: row.confidence,
    alternatives: row.alternative_candidates ?? [],
    status: "inferred",
    moduleRevisionId:
      row.gallery_revision_id ||
      (row.gallery_module_id ? `gallery-${row.gallery_module_id}` : `catalog-${row.candidate_id}`),
    decision: row.decision_advisory
      ? {
          disposition: row.decision_advisory.disposition,
          provider: row.decision_advisory.provider,
          confidence: row.decision_advisory.confidence,
          reasonCodes: row.decision_advisory.reason_codes,
        }
      : undefined,
  }));
}

const ALLOWED_TYPES = ["image/jpeg", "image/png", "image/webp"];
const MAX_BYTES = 12 * 1024 * 1024;

function formatValidationError(
  err: unknown,
  fallback = "Could not create rig. Check case selection and try again.",
): string {
  const apiError = err as {
    response?: {
      data?: {
        detail?: string | { message?: string; errors?: { field?: string; message?: string }[] };
      };
    };
  };
  const detail = apiError.response?.data?.detail;
  if (typeof detail === "string") return detail;
  if (detail && typeof detail === "object") {
    const errs = detail.errors;
    if (Array.isArray(errs) && errs.length) {
      return errs.map((e) => e.message || e.field || "Validation error").join("; ");
    }
    if (detail.message) return detail.message;
  }
  return fallback;
}

/** The case rails a placement draws on, with the names the builder shows. */
const POWER_RAILS: {
  key: RailKey;
  rail: string;
  capacity: "power_12v_ma" | "power_neg12v_ma" | "power_5v_ma";
}[] = [
  { key: "p12", rail: "+12V", capacity: "power_12v_ma" },
  { key: "n12", rail: "−12V", capacity: "power_neg12v_ma" },
  { key: "p5", rail: "+5V", capacity: "power_5v_ma" },
];

/** ", in a Sim Co Sim 84 case, 84HP in one row", and whether compatibility can be checked. */
function caseLine(c: NonNullable<Rack["case"]>): string {
  const rowHp = c.hp_per_row ?? [];
  const size =
    c.total_hp == null
      ? ""
      : rowHp.length === 1
        ? `, ${c.total_hp}HP in one row`
        : rowHp.length > 1
          ? `, ${c.total_hp}HP in rows of ${rowHp.join(" + ")}`
          : `, ${c.total_hp}HP`;
  const link = c.catalog_slug
    ? ""
    : ". It has no catalog link, so compatibility checks are partial";
  return `, in a ${c.brand} ${c.name} case${size}${link}`;
}

/** Suggest start HP for single add (0 if row cannot fit — user may still override). */
function nextFreeStartHp(
  rowIndex: number,
  moduleHp: number,
  placements: RackModuleSpec[],
  resolveHp: (moduleId: number) => number | null,
  rowCapacity: number,
): number {
  return firstFreeStartHp(rowIndex, moduleHp, placements, resolveHp, rowCapacity) ?? 0;
}

export default function RackBuilderPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { id: routeId } = useParams<{ id: string }>();
  const rackId = routeId && /^\d+$/.test(routeId) ? Number(routeId) : null;
  const liveMode = rackId != null;
  const preselectedCaseId = Number(searchParams.get("case_id") || "") || null;
  const preselectedCatalogSlug = searchParams.get("catalog_slug") || null;
  const preselectedModuleId = Number(searchParams.get("module_id") || "") || null;

  const [racks, setRacks] = useState<Rack[]>([]);
  const [selectedRackId, setSelectedRackId] = useState<number | null>(rackId);
  const [evidenceState, setEvidenceState] = useState<EvidenceState>("idle");
  const [fileLabel, setFileLabel] = useState("");
  const [pendingFiles, setPendingFiles] = useState<File[]>([]);
  /** Photo evidence errors; rig creation keeps its own in createError. */
  const [error, setError] = useState("");
  // Rigs belong to the signed-in user, so creating one needs an account.
  const signedIn = useAuthStore((st) => st.isAuthenticated());
  // Bulk materialize rewrites shared catalog data; the API allows only Admin and Ops.
  const canBulkMaterialize = useAuthStore(
    (st) => st.user?.role === "Admin" || st.user?.role === "Ops",
  );
  const [candidates, setCandidates] = useState<ReviewCandidate[]>(DEMO_CANDIDATES);
  const [inventoryRevisionId, setInventoryRevisionId] = useState<string | null>(null);
  const [readyForGeneration, setReadyForGeneration] = useState(false);
  const [fromLiveApi, setFromLiveApi] = useState(false);
  const [fused, setFused] = useState<FusedEntityView[]>([]);
  /** User-applied fusion decisions keyed by fuse_id (still maps to candidate rows). */
  const [fusedApplied, setFusedApplied] = useState<Record<string, CandidateStatus>>({});
  const [fusionFeedback, setFusionFeedback] = useState<string | null>(null);
  const [reconcileStatus, setReconcileStatus] = useState<string | null>(null);
  const [reconcileNote, setReconcileNote] = useState<string | null>(null);
  const [imageCount, setImageCount] = useState(0);

  /** C0: case-bound create on /racks/new — catalog-first with legacy materialize bridge */
  const [catalogCases, setCatalogCases] = useState<CatalogCaseListItem[]>([]);
  const [legacyCases, setLegacyCases] = useState<Case[]>([]);
  const [casesLoading, setCasesLoading] = useState(false);
  const [selectedCaseId, setSelectedCaseId] = useState<number | null>(preselectedCaseId);
  const [selectedCatalogSlug, setSelectedCatalogSlug] = useState<string | null>(
    preselectedCatalogSlug,
  );
  const [rigName, setRigName] = useState("");
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState("");
  const [caseQuery, setCaseQuery] = useState("");
  // The case search asks once the typing pauses.
  const caseTerm = useDebouncedValue(caseQuery.trim());
  const [casesError, setCasesError] = useState<unknown>(null);
  const [casesAttempt, setCasesAttempt] = useState(0);
  const [compatNote, setCompatNote] = useState<string | null>(null);

  /** Live placement editor (method 01) */
  const { toast, show: showToast, dismiss: dismissToast } = useToast();
  /** Counts placement saves, so only the latest one's answer updates the rail. */
  const commitSeq = useRef(0);
  /** A placed module the rail should focus once it is drawn, such as one Undo put back. */
  const [focusRequest, setFocusRequest] = useState<{
    module_id: number;
    row: number;
    start: number;
  } | null>(null);
  const [liveRack, setLiveRack] = useState<Rack | null>(null);
  const [liveRackLoading, setLiveRackLoading] = useState(false);
  const [placementModules, setPlacementModules] = useState<RackModuleSpec[]>([]);
  const [galleryModules, setGalleryModules] = useState<Module[]>([]);
  const [addModuleId, setAddModuleId] = useState<number | null>(null);
  const [addRow, setAddRow] = useState(0);
  const [addStartHp, setAddStartHp] = useState(0);
  const [placementSaving, setPlacementSaving] = useState(false);
  const [placementError, setPlacementError] = useState("");
  const [rackCompat, setRackCompat] = useState<RackCompat | null>(null);
  const [batchNote, setBatchNote] = useState("");
  const [moduleMaterializeNote, setModuleMaterializeNote] = useState("");
  const [moduleQuery, setModuleQuery] = useState("");
  /** Multi-select for batch place (module ids). */
  const [batchSelectedIds, setBatchSelectedIds] = useState<number[]>([]);
  const [batchPlaceNote, setBatchPlaceNote] = useState("");
  /** Label for module_id deep-link when gallery list is not yet loaded (create flow). */
  const [preselectedLabel, setPreselectedLabel] = useState<string | null>(null);

  const activeRackId = selectedRackId ?? rackId;

  useEffect(() => {
    if (preselectedModuleId == null) {
      setPreselectedLabel(null);
      return;
    }
    let cancelled = false;
    moduleApi
      .list({ limit: 500 })
      .then((res) => {
        if (cancelled) return;
        const rows = res.data.modules ?? [];
        const m = rows.find((row) => row.id === preselectedModuleId);
        if (m) {
          setPreselectedLabel(`${m.brand} ${m.name} (${m.hp}HP)`);
          if (!liveMode) {
            setGalleryModules((prev) => (prev.length ? prev : rows));
          }
        } else {
          setPreselectedLabel(`Module #${preselectedModuleId}`);
        }
      })
      .catch(() => {
        if (!cancelled) setPreselectedLabel(`Module #${preselectedModuleId}`);
      });
    return () => {
      cancelled = true;
    };
  }, [preselectedModuleId, liveMode]);

  const placementPowerSummary = useMemo(
    () =>
      summarizePower(
        placementModules.map((spec) =>
          placementPower(
            liveRack?.modules?.find((m) => m.module_id === spec.module_id)?.module ??
              galleryModules.find((m) => m.id === spec.module_id),
            spec.power_config_id,
          ),
        ),
      ),
    [placementModules, liveRack, galleryModules],
  );

  const previewModule = useMemo(() => {
    if (addModuleId == null) return null;
    return galleryModules.find((m) => m.id === addModuleId) ?? null;
  }, [addModuleId, galleryModules]);

  const filteredGalleryModules = useMemo(() => {
    const q = moduleQuery.trim().toLowerCase();
    let rows = [...galleryModules];
    if (q) {
      // Match the "Brand Name" label too: the module_id deep link prefills the query with it.
      rows = rows.filter(
        (m) => `${m.brand} ${m.name}`.toLowerCase().includes(q) || String(m.id) === q,
      );
    }
    // Prefer modules with known power, then smaller HP
    rows.sort((a, b) => {
      const ap = a.power_12v_ma != null ? 0 : 1;
      const bp = b.power_12v_ma != null ? 0 : 1;
      if (ap !== bp) return ap - bp;
      return a.hp - b.hp || a.brand.localeCompare(b.brand);
    });
    return rows;
  }, [galleryModules, moduleQuery]);

  const resolveModuleHp = useMemo(() => {
    return (moduleId: number): number | null => {
      const fromLive = liveRack?.modules?.find((m) => m.module_id === moduleId)?.module;
      if (fromLive?.hp != null) return fromLive.hp;
      const fromGallery = galleryModules.find((m) => m.id === moduleId);
      return fromGallery?.hp ?? null;
    };
  }, [liveRack, galleryModules]);

  /** The module a placement refers to: the rig's own record first, else the gallery's. */
  const placedModule = (spec: RackModuleSpec) =>
    liveRack?.modules?.find(
      (m) =>
        m.module_id === spec.module_id &&
        m.row_index === spec.row_index &&
        m.start_hp === spec.start_hp,
    )?.module ?? galleryModules.find((m) => m.id === spec.module_id);

  /** Per-row HP occupancy for visual usage bars. */
  const rowHpUsage = useMemo(() => {
    if (!liveRack?.case)
      return [] as { row: number; capacity: number; used: number; free: number }[];
    const rows = liveRack.case.rows || liveRack.case.hp_per_row?.length || 1;
    const hpPerRow = liveRack.case.hp_per_row?.length
      ? liveRack.case.hp_per_row
      : Array.from(
          { length: rows },
          () => Math.floor((liveRack.case?.total_hp || 0) / rows) || liveRack.case?.total_hp || 0,
        );
    return hpPerRow.map((capacity, row) => {
      let used = 0;
      for (const spec of placementModules) {
        if (spec.row_index !== row) continue;
        used += resolveModuleHp(spec.module_id) ?? 0;
      }
      return { row, capacity, used, free: Math.max(0, capacity - used) };
    });
  }, [liveRack, placementModules, resolveModuleHp]);

  const preselectedModule = useMemo(() => {
    if (preselectedModuleId == null) return null;
    return galleryModules.find((m) => m.id === preselectedModuleId) ?? null;
  }, [galleryModules, preselectedModuleId]);

  const builderStep = liveMode ? 3 : selectedCatalogSlug || selectedCaseId ? 2 : 1;

  const selectedLegacyCase = useMemo(
    () => legacyCases.find((c) => c.id === selectedCaseId) ?? null,
    [legacyCases, selectedCaseId],
  );
  const selectedCatalogCase = useMemo(
    () => catalogCases.find((c) => c.slug === selectedCatalogSlug) ?? null,
    [catalogCases, selectedCatalogSlug],
  );

  /** Smart start HP: snap to first free gap when module or row changes. */
  useEffect(() => {
    if (!liveMode || addModuleId == null || !liveRack?.case) return;
    const modHp = resolveModuleHp(addModuleId);
    if (modHp == null || modHp <= 0) return;
    const capacity =
      liveRack.case.hp_per_row?.[addRow] ??
      (liveRack.case.rows
        ? Math.floor(liveRack.case.total_hp / liveRack.case.rows)
        : liveRack.case.total_hp);
    const next = nextFreeStartHp(
      addRow,
      modHp,
      placementModules,
      resolveModuleHp,
      capacity || liveRack.case.total_hp,
    );
    setAddStartHp(next);
    // Only when selection changes — not every keystroke of start HP
  }, [liveMode, addModuleId, addRow, placementModules, liveRack?.case, resolveModuleHp]);

  useEffect(() => {
    if (rackId != null) {
      setSelectedRackId(rackId);
      return;
    }
    // Spec 008 F5: inventory reads go through the canon alias; writes stay on rackApi.
    canonApi
      .listRigs({ limit: 50 })
      .then((res) => {
        const rows = (res.data.rigs ?? []).map(rigSummaryToRack);
        setRacks(rows);
        if (rows.length && selectedRackId == null) {
          setSelectedRackId(rows[0].id);
        }
      })
      .catch(() => {
        setRacks([]);
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps -- initial rack list only
  }, [rackId]);

  useEffect(() => {
    if (liveMode) return;
    let current = true;
    setCasesLoading(true);
    setCasesError(null);
    setCompatNote(null);
    const q = caseTerm || undefined;
    void Promise.allSettled([
      caseCatalogApi
        .list({ limit: 200, format_family: "eurorack", q })
        .then((res) => res.data.cases ?? []),
      caseApi
        .list({ limit: 200, format_family: "Eurorack", q })
        .then((res) => res.data.cases ?? []),
    ])
      .then(([catalogResult, legacyResult]) => {
        if (!current) return;
        const catalogRows = catalogResult.status === "fulfilled" ? catalogResult.value : [];
        const legacyRows = legacyResult.status === "fulfilled" ? legacyResult.value : [];
        // Either list is enough to choose from; with neither, the cases didn't load.
        if (catalogResult.status === "rejected" && legacyResult.status === "rejected") {
          setCasesError(catalogResult.reason);
        }
        setCatalogCases(catalogRows);
        setLegacyCases(legacyRows);
        if (selectedCaseId == null && preselectedCaseId != null) {
          setSelectedCaseId(preselectedCaseId);
        }
        if (selectedCatalogSlug == null && preselectedCatalogSlug) {
          setSelectedCatalogSlug(preselectedCatalogSlug);
        } else if (selectedCatalogSlug == null && catalogRows.length === 1) {
          setSelectedCatalogSlug(catalogRows[0].slug);
        } else if (
          selectedCaseId == null &&
          selectedCatalogSlug == null &&
          legacyRows.length === 1 &&
          catalogRows.length === 0
        ) {
          setSelectedCaseId(legacyRows[0].id);
        }
      })
      .finally(() => {
        if (current) setCasesLoading(false);
      });
    return () => {
      current = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- case catalog load
  }, [liveMode, caseTerm, casesAttempt]);

  useEffect(() => {
    if (liveMode || !selectedCatalogSlug) {
      setCompatNote(null);
      return;
    }
    caseCatalogApi
      .compatibility(selectedCatalogSlug, { modules: [], plan_close_lid: false })
      .then((res) => {
        const c = res.data;
        const rails = c.power_headroom.map((r) => `${r.rail} ${r.status}`).join(", ");
        setCompatNote(
          `Compatibility baseline: ${c.overall_status}; format ${c.format_check.status}; ${rails}`,
        );
      })
      .catch(() => setCompatNote(null));
  }, [liveMode, selectedCatalogSlug]);

  const createRigFromCase = async () => {
    setCreating(true);
    setCreateError("");
    try {
      let caseId = selectedCaseId;
      if (selectedCatalogSlug) {
        const mat = await caseCatalogApi.materialize(selectedCatalogSlug);
        caseId = mat.data.case.id;
        setSelectedCaseId(caseId);
        setLegacyCases((prev) => {
          const exists = prev.some((c) => c.id === mat.data.case.id);
          return exists ? prev : [...prev, mat.data.case];
        });
      }
      if (caseId == null) {
        setCreateError("Select a Eurorack case (catalog or legacy) before creating a rig.");
        setCreating(false);
        return;
      }
      const res = await rackApi.create({
        case_id: caseId,
        name: rigName.trim() || undefined,
        modules: [],
      });
      const id = res.data.id;
      const qs = preselectedModuleId != null ? `?module_id=${preselectedModuleId}` : "";
      navigate(`/racks/${id}/edit${qs}`);
    } catch (err) {
      setCreateError(formatValidationError(err));
    } finally {
      setCreating(false);
    }
  };

  /** Reloads the rig; `isCurrent` lets a superseded save skip writing its stale answer. */
  const refreshLiveRack = async (id: number, isCurrent: () => boolean = () => true) => {
    const res = await canonApi.getRig(id);
    if (!isCurrent()) return;
    const rig = rigDetailToRack(res.data);
    setLiveRack(rig);
    setPlacementModules(
      (rig.modules ?? []).map((m) => ({
        module_id: m.module_id,
        row_index: m.row_index,
        start_hp: m.start_hp,
        power_config_id: m.power_config_id ?? null,
      })),
    );
    try {
      const compat = await rackApi.compatibility(id);
      setRackCompat(compat.data);
    } catch {
      setRackCompat(null);
    }
  };

  useEffect(() => {
    if (!liveMode || rackId == null) {
      setLiveRack(null);
      setPlacementModules([]);
      setRackCompat(null);
      return;
    }
    setLiveRackLoading(true);
    void refreshLiveRack(rackId)
      .catch(() => {
        setLiveRack(null);
        setPlacementError("Unable to load rig for placement.");
      })
      .finally(() => setLiveRackLoading(false));
    moduleApi
      .list({ limit: 500 })
      .then((res) => {
        const rows = res.data.modules ?? [];
        setGalleryModules(rows);
        if (preselectedModuleId != null) {
          const hit = rows.find((m) => m.id === preselectedModuleId);
          if (hit) {
            setAddModuleId(hit.id);
            setModuleQuery(`${hit.brand} ${hit.name}`);
          }
        }
      })
      .catch(() => setGalleryModules([]));
  }, [liveMode, rackId, preselectedModuleId]);

  /** Saves placements once the server accepts them. Says whether it saved. */
  const savePlacements = async (next: RackModuleSpec[]): Promise<boolean> => {
    if (rackId == null) return false;
    setPlacementSaving(true);
    setPlacementError("");
    try {
      await rackApi.update(rackId, { modules: next });
      setPlacementModules(next);
      await refreshLiveRack(rackId);
      return true;
    } catch (err) {
      setPlacementError(formatValidationError(err));
      return false;
    } finally {
      setPlacementSaving(false);
    }
  };

  /** Each row's HP, declared before the checks and saves that read it. */
  const rowCapacities = useMemo(() => {
    if (!liveRack?.case) return [] as number[];
    const c = liveRack.case;
    if (c.hp_per_row?.length) return c.hp_per_row;
    const rows = c.rows || 1;
    const each = Math.floor((c.total_hp || 0) / rows) || c.total_hp || 0;
    return Array.from({ length: rows }, () => each);
  }, [liveRack]);

  /** A placed module's name, for messages: the rig's record, else the gallery's. */
  const placementName = (spec: RackModuleSpec) => {
    const mod = placedModule(spec);
    return mod ? `${mod.brand} ${mod.name}` : `Module #${spec.module_id}`;
  };

  /** Focus the placed module in this slot once the rail draws it. */
  const focusPlacement = (spec: RackModuleSpec | undefined) =>
    setFocusRequest(
      spec ? { module_id: spec.module_id, row: spec.row_index, start: spec.start_hp } : null,
    );

  /**
   * Saves placements at once on screen and rolls them back if the server refuses. The toast
   * comes once the rig has reloaded, so its Undo never races the save it reverses. `undo`, when
   * given, is offered there: it saves the placements as they were, and focuses `undoFocus`.
   * `focus` is the module to return to when the toast is dismissed.
   */
  const commitPlacements = async (
    next: RackModuleSpec[],
    message: string,
    options: { undo?: string; undoFocus?: RackModuleSpec; focus?: RackModuleSpec } = {},
  ) => {
    if (rackId == null) return;
    const seq = ++commitSeq.current;
    const isCurrent = () => seq === commitSeq.current;
    const before = placementModules;
    setPlacementModules(next);
    setPlacementSaving(true);
    setPlacementError("");
    dismissToast();
    try {
      await rackApi.update(rackId, { modules: next });
      await refreshLiveRack(rackId, isCurrent);
      if (!isCurrent()) return;
      const { undo, undoFocus, focus } = options;
      showToast(message, {
        action: undo
          ? {
              label: "Undo",
              run: () => {
                focusPlacement(undoFocus);
                void commitPlacements(before, undo, { focus: undoFocus });
              },
            }
          : undefined,
        returnFocus: () => focusPlacement(focus),
      });
    } catch (err) {
      if (!isCurrent()) return;
      setPlacementModules(before);
      const why = formatValidationError(err, failureReason(err));
      setPlacementError(why);
      showToast(`Not saved, so nothing changed. ${why}`, { tone: "danger" });
    } finally {
      if (isCurrent()) setPlacementSaving(false);
    }
  };

  /** Whether a module may sit in a slot, against every other placement and the case's rows. */
  const checkPlacementSlot = (slot: Slot, ignoreIndex: number) =>
    checkSlot(slot, placementModules, rowCapacities, resolveModuleHp, placementName, ignoreIndex);

  const movePlacement = (index: number, row: number, startHp: number) => {
    const spec = placementModules[index];
    if (!spec) return;
    const name = placementName(spec);
    void commitPlacements(
      moveTo(placementModules, index, row, startHp),
      `${name} moved to ${slotPhrase(row, startHp)}.`,
      {
        undo: `${name} is back at ${slotPhrase(spec.row_index, spec.start_hp)}.`,
        undoFocus: spec,
        focus: { ...spec, row_index: row, start_hp: startHp },
      },
    );
  };

  /** The rails a placement list would take past the case's stated capacity. */
  const railsOverBudget = (next: RackModuleSpec[]) => {
    const rack = liveRack?.case;
    if (!rack) return [] as string[];
    const summary = summarizePower(
      next.map((spec) => placementPower(placedModule(spec), spec.power_config_id)),
    );
    return POWER_RAILS.flatMap(({ key, rail, capacity }) => {
      const meter = railMeter(summary[key], rack[capacity]);
      return meter.headroom != null && meter.headroom < 0
        ? [`${rail} by ${-meter.headroom}mA`]
        : [];
    });
  };

  const addPlacement = async () => {
    if (addModuleId == null) {
      setPlacementError("Select a module from the gallery.");
      return;
    }
    if (previewCheck && !previewCheck.ok) {
      setPlacementError(previewCheck.reason);
      return;
    }
    const next = [
      ...placementModules,
      { module_id: addModuleId, row_index: addRow, start_hp: addStartHp },
    ];
    // Over budget is the case's call to make, not the builder's: it warns, and still places.
    const over = railsOverBudget(next);
    const before = railsOverBudget(placementModules);
    const saved = await savePlacements(next);
    if (saved && over.length > before.length) {
      showToast(`This placement takes the case over budget on ${over.join(" and ")}.`, {
        tone: "warning",
      });
    }
  };

  // The next single placement, checked before it can be added: overlapping or off the row, the
  // rail shows it red with the reason and Add placement waits.
  const previewCheck =
    previewModule && previewModule.hp > 0
      ? checkPlacementSlot({ row: addRow, start: addStartHp, hp: previewModule.hp }, -1)
      : null;

  const batchPreview = useMemo(() => {
    if (!batchSelectedIds.length || !rowCapacities.length) {
      return null;
    }
    return packModulesOntoRows(
      batchSelectedIds,
      placementModules,
      resolveModuleHp,
      rowCapacities,
      addRow,
    );
  }, [batchSelectedIds, placementModules, resolveModuleHp, rowCapacities, addRow]);

  const toggleBatchModule = (id: number) => {
    setBatchSelectedIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id],
    );
    setBatchPlaceNote("");
  };

  const selectAllFilteredForBatch = () => {
    setBatchSelectedIds(filteredGalleryModules.map((m) => m.id));
    setBatchPlaceNote("");
  };

  const clearBatchSelection = () => {
    setBatchSelectedIds([]);
    setBatchPlaceNote("");
  };

  const addBatchPlacements = async () => {
    if (!batchSelectedIds.length) {
      setPlacementError("Select at least one module for batch place.");
      return;
    }
    if (!rowCapacities.length) {
      setPlacementError("Case row capacity unknown: cannot batch pack.");
      return;
    }
    const result = packModulesOntoRows(
      batchSelectedIds,
      placementModules,
      resolveModuleHp,
      rowCapacities,
      addRow,
    );
    if (!result.added.length) {
      setPlacementError(
        result.unplaced.length
          ? `Nothing placed. ${result.unplaced.map((u) => `#${u.module_id}: ${u.reason}`).join("; ")}`
          : "Nothing to place.",
      );
      setBatchPlaceNote("");
      return;
    }
    await savePlacements(result.placements);
    const unMsg = result.unplaced.length
      ? `, ${result.unplaced.length} could not fit (${result.unplaced
          .map((u) => `#${u.module_id}`)
          .join(", ")})`
      : "";
    setBatchPlaceNote(
      `Batch placed ${result.added.length} module${result.added.length === 1 ? "" : "s"}${unMsg}.`,
    );
    setBatchSelectedIds([]);
  };

  /** Choose the jumper setting a placed module is set to; empty = not chosen (draw unknown). */
  const choosePowerConfig = async (index: number, powerConfigId: number | null) => {
    const next = placementModules.map((spec, i) =>
      i === index ? { ...spec, power_config_id: powerConfigId } : spec,
    );
    await savePlacements(next);
  };

  const removePlacement = (index: number) => {
    const spec = placementModules[index];
    if (!spec) return;
    const name = placementName(spec);
    void commitPlacements(
      placementModules.filter((_, i) => i !== index),
      `${name} removed from ${slotPhrase(spec.row_index, spec.start_hp)}.`,
      { undo: `${name} is back at ${slotPhrase(spec.row_index, spec.start_hp)}.`, undoFocus: spec },
    );
  };

  const materializeAllEurorack = async () => {
    setBatchNote("");
    try {
      const res = await caseCatalogApi.materializeBatch({ format_family: "eurorack" });
      const b = res.data;
      setBatchNote(
        `Synced the Eurorack catalog: scanned ${b.scanned}, created ${b.created}, updated ${b.updated}, failed ${b.failed}.`,
      );
      // Refresh legacy case list for create flow
      const legacy = await caseApi.list({ limit: 200, format_family: "Eurorack" });
      setLegacyCases(legacy.data.cases ?? []);
    } catch {
      setBatchNote("Bulk sync failed. Check that the catalog seed is imported.");
    }
  };

  const materializeHpKnownModules = async () => {
    setModuleMaterializeNote("");
    try {
      const res = await moduleApi.materializeCatalogBatch({
        hp_known_only: true,
        limit: 500,
      });
      const b = res.data;
      setModuleMaterializeNote(
        `Loaded HP-known catalog modules: scanned ${b.scanned}, created ${b.created}, already present ${b.exists}, failed ${b.failed}.`,
      );
      const list = await moduleApi.list({ limit: 500 });
      setGalleryModules(list.data.modules ?? []);
    } catch {
      setModuleMaterializeNote(
        "Loading HP-known modules failed. Check that the research catalog is imported and the API is up.",
      );
    }
  };

  const ranked = useMemo(
    () => [...candidates].sort((a, b) => b.confidence - a.confidence),
    [candidates],
  );

  const allResolved = ranked.every((c) => c.status !== "inferred");
  const confirmedCount = ranked.filter((c) => c.status === "confirmed").length;

  const selectPhotos = (list?: FileList | null) => {
    setError("");
    setInventoryRevisionId(null);
    setReadyForGeneration(false);
    setFused([]);
    setFusedApplied({});
    setFusionFeedback(null);
    setReconcileStatus(null);
    setReconcileNote(null);
    setImageCount(0);
    if (!list || list.length === 0) return;

    const accepted: File[] = [];
    const reasons: string[] = [];
    Array.from(list).forEach((file) => {
      if (!ALLOWED_TYPES.includes(file.type) || file.size > MAX_BYTES) {
        reasons.push(`${file.name}: type/size rejected`);
        return;
      }
      accepted.push(file);
    });
    if (!accepted.length) {
      setError(reasons.join("; ") || "Choose JPEG, PNG, or WebP images ≤ 12 MB.");
      setEvidenceState("idle");
      setPendingFiles([]);
      return;
    }
    if (reasons.length) {
      setError(`Some files skipped: ${reasons.join("; ")}`);
    }
    setPendingFiles(accepted);
    setFileLabel(
      accepted.length === 1
        ? accepted[0].name
        : `${accepted.length} photos (${accepted.map((f) => f.name).join(", ")})`,
    );
    setFromLiveApi(false);
    setCandidates(DEMO_CANDIDATES.map((c) => ({ ...c, status: "inferred" as const })));
    setEvidenceState("ready");
  };

  const setStatus = (id: string, status: CandidateStatus) => {
    setCandidates((prev) => prev.map((c) => (c.id === id ? { ...c, status } : c)));
  };

  /** Apply a fusion-panel decision onto the matching candidate row (still user-initiated). */
  const applyFusedDecision = (entity: FusedEntityView, status: CandidateStatus) => {
    const targetId = entity.representative_candidate_id;
    if (!targetId) {
      setError("Fused entity has no representative candidate id to resolve.");
      setFusionFeedback(null);
      return;
    }
    if (entity.conflict && status === "confirmed") {
      setError(
        "Cannot confirm a conflicted fusion from the panel: resolve the underlying candidates individually.",
      );
      setFusionFeedback(null);
      return;
    }
    setError("");
    setStatus(targetId, status);
    setFusedApplied((prev) => ({ ...prev, [entity.fuse_id]: status }));
    const label = entity.model || entity.fuse_id;
    setFusionFeedback(`Applied ${status} to fused “${label}” (candidate ${targetId}).`);
  };

  const confirmAllNonConflictFused = () => {
    setError("");
    const eligible = fused.filter((e) => !e.conflict && e.representative_candidate_id);
    const confirmIds = new Set(eligible.map((e) => e.representative_candidate_id as string));
    const blocked = fused.length - confirmIds.size;
    if (!confirmIds.size) {
      setError(
        blocked
          ? "No non-conflict fused entities to confirm. Resolve conflicts in the candidate list."
          : "No fused entities available.",
      );
      setFusionFeedback(null);
      return;
    }
    setCandidates((prev) =>
      prev.map((c) => (confirmIds.has(c.id) ? { ...c, status: "confirmed" as const } : c)),
    );
    setFusedApplied((prev) => {
      const next = { ...prev };
      eligible.forEach((e) => {
        next[e.fuse_id] = "confirmed";
      });
      return next;
    });
    setFusionFeedback(
      `Confirmed ${eligible.length} non-conflict fusion${eligible.length === 1 ? "" : "s"}` +
        (blocked ? `, ${blocked} blocked (conflict or missing rep)` : ""),
    );
  };

  const detectModules = async () => {
    setError("");
    if (!pendingFiles.length) {
      setError("Choose at least one rig photo first.");
      return;
    }
    // Live path: multi-image upload → candidates → multi-photo reconcile
    if (activeRackId != null) {
      setEvidenceState("uploading");
      try {
        const upload = await evidenceApi.uploadImages(activeRackId, pendingFiles, {
          run_vision_mock: true,
          consent_provider_processing: false,
        });
        if (upload.data.rejected?.length && !upload.data.uploaded?.length) {
          setError(upload.data.rejected.map((r) => `${r.filename}: ${r.reason}`).join("; "));
          setEvidenceState("error");
          return;
        }
        const listed = await evidenceApi.listCandidates(activeRackId);
        const mapped = mapApiCandidates(listed.data.candidates ?? []);
        if (mapped.length) {
          setCandidates(mapped);
          setFromLiveApi(true);
        } else {
          setCandidates(DEMO_CANDIDATES.map((c) => ({ ...c, status: "inferred" })));
          setFromLiveApi(false);
        }
        try {
          const recon = await evidenceApi.reconcile(activeRackId);
          setFused(recon.data.fused_entities ?? []);
          setFusedApplied({});
          setFusionFeedback(null);
          setReconcileStatus(recon.data.status);
          setReconcileNote(recon.data.note);
          setImageCount(recon.data.image_count);
        } catch {
          setFused([]);
          setFusedApplied({});
          setReconcileStatus(null);
          setReconcileNote("Reconciliation API unavailable; showing per-image candidates only.");
        }
        setEvidenceState("review");
      } catch {
        setError("Evidence upload or detection failed. Falling back to local demo candidates.");
        setCandidates(DEMO_CANDIDATES.map((c) => ({ ...c, status: "inferred" })));
        setFromLiveApi(false);
        setFused([]);
        setEvidenceState("review");
      }
      return;
    }
    // Create flow without rack: local demo only.
    setFromLiveApi(false);
    setCandidates(DEMO_CANDIDATES.map((c) => ({ ...c, status: "inferred" })));
    setFused([]);
    setReconcileStatus(pendingFiles.length >= 2 ? "DEMO_MULTI" : "DEMO_SINGLE");
    setReconcileNote(
      pendingFiles.length >= 2
        ? "Multi-photo fusion needs a target rig."
        : "Choose a target rig to reconcile your photos.",
    );
    setEvidenceState("review");
  };

  const createInventoryRevision = async () => {
    if (!allResolved || confirmedCount < 1) {
      setError(
        "Confirm at least one module and resolve every candidate before creating a revision.",
      );
      return;
    }
    setError("");

    if (activeRackId != null && fromLiveApi) {
      try {
        const decisions = ranked.map((c) => {
          if (c.status === "confirmed") {
            return {
              candidate_id: c.id,
              status: "confirm",
              module_revision_id: c.moduleRevisionId,
            };
          }
          if (c.status === "rejected") {
            return { candidate_id: c.id, status: "reject" };
          }
          return { candidate_id: c.id, status: "defer" };
        });
        const result = await evidenceApi.confirm(activeRackId, {
          confirmed_by: "workspace-user",
          decisions,
        });
        setInventoryRevisionId(result.data.inventory_revision_id);
        setReadyForGeneration(result.data.ready_for_generation);
        setEvidenceState("confirmed");
        return;
      } catch {
        setError("Confirmation API failed. Inventory was not persisted.");
        return;
      }
    }

    const material = ranked
      .filter((c) => c.status === "confirmed")
      .map((c) => `${c.id}:${c.moduleRevisionId}`)
      .join("|");
    const syntheticId = `inv-rev-local-${Math.abs(
      Array.from(material).reduce((acc, ch) => (acc * 31 + ch.charCodeAt(0)) | 0, 7),
    ).toString(16)}`;
    setInventoryRevisionId(syntheticId);
    setReadyForGeneration(true);
    setEvidenceState("confirmed");
  };

  return (
    <section
      className="builder"
      aria-labelledby="builder-title"
      // Room below the last row, so a toast never sits over it.
      data-toast-open={toast ? "" : undefined}
    >
      <header className="workspace-header">
        <div>
          <h1 id="builder-title">
            {liveMode ? "Module placement" : "Establish your module inventory"}
          </h1>
          {liveMode ? (
            <p className="muted builder-rig-line">
              <strong>{liveRack?.name ?? "This rig"}</strong>
              {liveRack?.case ? caseLine(liveRack.case) : ""}.
            </p>
          ) : (
            <p className="muted">
              Choose a case, create the rig, then place modules from the{" "}
              <Link to="/modules">module gallery</Link>.
            </p>
          )}
        </div>
        {rackId != null ? (
          <div className="header-actions">
            <Link className="button button-quiet" to={`/rigs/${rackId}`}>
              Open rig detail
            </Link>
            <Link className="button button-quiet" to="/racks">
              Back to rigs
            </Link>
          </div>
        ) : null}
      </header>

      <ol className="step-progress" aria-label="Builder steps">
        {BUILDER_STEPS.map((step) => {
          const state = builderStep > step.n ? "done" : builderStep === step.n ? "current" : "todo";
          return (
            <li
              key={step.n}
              className={`step-progress__item step-progress__item--${state}`}
              aria-current={state === "current" ? "step" : undefined}
            >
              <span className="step-progress__num" aria-hidden="true">
                {step.n}
              </span>
              <span className="step-progress__label">{step.label}</span>
              {state === "done" ? <span className="visually-hidden">, done</span> : null}
            </li>
          );
        })}
      </ol>

      <div className="builder-flow">
        {!liveMode && preselectedModuleId != null ? (
          <div className="module-preselect-banner" role="status">
            <p>
              <strong>Module ready to place:</strong>{" "}
              {preselectedLabel ||
                (preselectedModule
                  ? `${preselectedModule.brand} ${preselectedModule.name} (${preselectedModule.hp}HP)`
                  : `Module #${preselectedModuleId}`)}
              . Create a rig, then placement opens with this module preselected.
            </p>
          </div>
        ) : null}

        {rackId != null ? (
          <PlacementStep
            rack={liveRack}
            loading={liveRackLoading}
            preselected={
              preselectedModuleId != null
                ? {
                    label: preselectedModule
                      ? `${preselectedModule.brand} ${preselectedModule.name}`
                      : `module #${preselectedModuleId}`,
                    hp: preselectedModule?.hp ?? null,
                  }
                : null
            }
            rail={{
              rows: rowHpUsage,
              placements: placementModules,
              moduleFor: placedModule,
              resolveHp: resolveModuleHp,
              preview:
                previewModule && !batchSelectedIds.length
                  ? {
                      module: previewModule,
                      row: addRow,
                      startHp: addStartHp,
                      check: previewCheck ?? undefined,
                    }
                  : null,
              batchPlan: batchPreview?.added ?? [],
              onPickSlot: (row, startHp) => {
                setAddRow(row);
                setAddStartHp(startHp);
              },
              checkSlot: checkPlacementSlot,
              onMove: movePlacement,
              onRemove: removePlacement,
              busy: placementSaving,
              focusRequest,
            }}
            powerSummary={placementPowerSummary}
            modules={filteredGalleryModules}
            add={{
              query: moduleQuery,
              onQuery: setModuleQuery,
              moduleId: addModuleId,
              onModule: setAddModuleId,
              row: addRow,
              onRow: setAddRow,
              startHp: addStartHp,
              onStartHp: setAddStartHp,
              blocked: previewCheck && !previewCheck.ok ? previewCheck.reason : null,
              onAdd: () => void addPlacement(),
            }}
            batch={{
              selectedIds: batchSelectedIds,
              onToggle: toggleBatchModule,
              onSelectAll: selectAllFilteredForBatch,
              onClear: clearBatchSelection,
              onPlace: () => void addBatchPlacements(),
              plan: batchPreview,
              note: batchPlaceNote,
            }}
            placements={placementModules}
            moduleFor={placedModule}
            saving={placementSaving}
            error={placementError}
            onChoosePowerConfig={(index, id) => void choosePowerConfig(index, id)}
            onRemove={removePlacement}
            compat={rackCompat}
            canLoadModules={canBulkMaterialize}
            onLoadModules={() => void materializeHpKnownModules()}
            loadNote={moduleMaterializeNote}
          />
        ) : (
          <CaseStep
            step={builderStep === 1 ? 1 : 2}
            caseQuery={caseQuery}
            onCaseQuery={setCaseQuery}
            casesLoading={casesLoading}
            casesError={casesError}
            onRetryCases={() => setCasesAttempt((n) => n + 1)}
            catalogCases={catalogCases}
            legacyCases={legacyCases}
            selectedCatalogSlug={selectedCatalogSlug}
            onSelectCatalog={(slug) => {
              setSelectedCatalogSlug(slug);
              if (slug) setSelectedCaseId(null);
            }}
            selectedCaseId={selectedCaseId}
            onSelectLegacy={(id) => {
              setSelectedCaseId(id);
              if (id != null) setSelectedCatalogSlug(null);
            }}
            selectedCatalogCase={selectedCatalogCase}
            selectedLegacyCase={selectedLegacyCase}
            compatNote={compatNote}
            rigName={rigName}
            onRigName={setRigName}
            signedIn={signedIn}
            creating={creating}
            onCreate={() => void createRigFromCase()}
            error={createError}
            canSyncCatalog={canBulkMaterialize}
            syncNote={batchNote}
            onSyncCatalog={() => void materializeAllEurorack()}
          />
        )}

        <EvidenceStep
          rackChoices={liveMode ? null : racks}
          selectedRackId={selectedRackId}
          onSelectRack={setSelectedRackId}
          targetRackId={activeRackId}
          state={evidenceState}
          error={error}
          fileLabel={fileLabel}
          pendingCount={pendingFiles.length}
          onSelectPhotos={selectPhotos}
          onDetect={() => void detectModules()}
          candidates={ranked}
          fromLiveApi={fromLiveApi}
          onSetStatus={setStatus}
          fusion={{
            entities: fused,
            applied: fusedApplied,
            feedback: fusionFeedback,
            status: reconcileStatus,
            note: reconcileNote,
            imageCount,
            onApply: applyFusedDecision,
            onConfirmAll: confirmAllNonConflictFused,
          }}
          confirmedCount={confirmedCount}
          allResolved={allResolved}
          onCreateRevision={() => void createInventoryRevision()}
          revisionId={inventoryRevisionId}
          readyForGeneration={readyForGeneration}
        />
      </div>
      <Toast toast={toast} onDismiss={dismissToast} actionDisabled={placementSaving} />
    </section>
  );
}
