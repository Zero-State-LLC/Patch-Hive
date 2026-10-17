import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import {
  caseApi,
  caseCatalogApi,
  moduleApi,
  evidenceApi,
  rackApi,
  type EvidenceCandidate,
} from "@/lib/api";
import { firstFreeStartHp, packModulesOntoRows } from "@/lib/placementPack";
import type {
  Case,
  CatalogCaseListItem,
  CompatibilityResponse,
  Module,
  Rack,
  RackModuleSpec,
} from "@/types/api";

type EvidenceState = "idle" | "ready" | "uploading" | "review" | "confirmed" | "error";
type CandidateStatus = "inferred" | "confirmed" | "rejected" | "deferred";

interface DecisionAdvisory {
  disposition: "auto_propose" | "user_review" | "unresolved" | "escalate" | "reject";
  provider?: string;
  confidence?: number | null;
  reasonCodes?: string[];
}

interface ReviewCandidate {
  id: string;
  label: string;
  manufacturer: string;
  confidence: number;
  alternatives: string[];
  status: CandidateStatus;
  moduleRevisionId: string;
  decision?: DecisionAdvisory;
}

interface FusedEntityView {
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

/** Demo ranked set when no rack id is available (create flow). */
const DEMO_CANDIDATES: ReviewCandidate[] = [
  {
    id: "cand-mod-a",
    label: "Oscillator A",
    manufacturer: "MockAudio",
    confidence: 0.81,
    alternatives: ["cand-mod-a-alt · higher-gain rev"],
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

function casePowerSummary(c: Case): string {
  const parts: string[] = [];
  if (c.power_12v_ma != null) parts.push(`+12 ${c.power_12v_ma}mA`);
  if (c.power_neg12v_ma != null) parts.push(`−12 ${c.power_neg12v_ma}mA`);
  if (c.power_5v_ma != null) parts.push(`+5 ${c.power_5v_ma}mA`);
  if (parts.length) return parts.join(" · ");
  if (c.powered === false || c.meta?.powered === false) return "Unpowered";
  return "Power unspecified (placement will not enforce rails)";
}

function formatValidationError(err: unknown): string {
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
      return errs.map((e) => e.message || e.field || "Validation error").join(" · ");
    }
    if (detail.message) return detail.message;
  }
  return "Could not create rig. Check case selection and try again.";
}

/** Map dual-gate status → chip tone class. */
function gateTone(status?: string | null): "success" | "warning" | "danger" | "neutral" {
  if (!status) return "neutral";
  const s = status.toLowerCase();
  if (s === "verified" || s === "ok" || s === "pass") return "success";
  if (s === "incomplete" || s === "warning" || s === "unknown") return "warning";
  if (s === "conflict" || s === "fail" || s === "error") return "danger";
  return "neutral";
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
  const [error, setError] = useState("");
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
  const [caseQuery, setCaseQuery] = useState("");
  const [compatNote, setCompatNote] = useState<string | null>(null);

  /** Live placement editor (method 01) */
  const [liveRack, setLiveRack] = useState<Rack | null>(null);
  const [placementModules, setPlacementModules] = useState<RackModuleSpec[]>([]);
  const [galleryModules, setGalleryModules] = useState<Module[]>([]);
  const [addModuleId, setAddModuleId] = useState<number | null>(null);
  const [addRow, setAddRow] = useState(0);
  const [addStartHp, setAddStartHp] = useState(0);
  const [placementSaving, setPlacementSaving] = useState(false);
  const [placementError, setPlacementError] = useState("");
  const [rackCompat, setRackCompat] = useState<{
    bridge_status: string;
    message: string;
    catalog_slug?: string | null;
    compatibility?: CompatibilityResponse | null;
  } | null>(null);
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
          setPreselectedLabel(`${m.brand} — ${m.name} (${m.hp}HP)`);
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

  const placementPowerSummary = useMemo(() => {
    let known = 0;
    let unknown = 0;
    let draw12 = 0;
    let drawN12 = 0;
    let draw5 = 0;
    for (const spec of placementModules) {
      const mod =
        liveRack?.modules?.find((m) => m.module_id === spec.module_id)?.module ??
        galleryModules.find((m) => m.id === spec.module_id);
      if (!mod) {
        unknown += 1;
        continue;
      }
      if (mod.power_12v_ma != null) {
        known += 1;
        draw12 += mod.power_12v_ma || 0;
        drawN12 += mod.power_neg12v_ma || 0;
        draw5 += mod.power_5v_ma || 0;
      } else {
        unknown += 1;
      }
    }
    return { known, unknown, draw12, drawN12, draw5, total: placementModules.length };
  }, [placementModules, liveRack, galleryModules]);

  /** Case rail capacity vs known placement draw (fail-closed: null capacity = unspecified). */
  const powerRailMeters = useMemo(() => {
    const c = liveRack?.case;
    if (!c)
      return [] as {
        rail: string;
        draw: number;
        capacity: number | null;
        headroom: number | null;
        tone: "success" | "warning" | "danger" | "neutral";
        pct: number;
      }[];

    const rails: { rail: string; draw: number; capacity: number | null | undefined }[] = [
      { rail: "+12V", draw: placementPowerSummary.draw12, capacity: c.power_12v_ma },
      { rail: "−12V", draw: placementPowerSummary.drawN12, capacity: c.power_neg12v_ma },
      { rail: "+5V", draw: placementPowerSummary.draw5, capacity: c.power_5v_ma },
    ];

    return rails.map((r) => {
      const capacity = r.capacity ?? null;
      if (capacity == null) {
        return {
          rail: r.rail,
          draw: r.draw,
          capacity: null,
          headroom: null,
          tone: "neutral" as const,
          pct: 0,
        };
      }
      const headroom = capacity - r.draw;
      const pct = capacity > 0 ? Math.min(100, Math.round((r.draw / capacity) * 100)) : 0;
      const tone =
        headroom < 0
          ? ("danger" as const)
          : pct >= 85
            ? ("warning" as const)
            : ("success" as const);
      return { rail: r.rail, draw: r.draw, capacity, headroom, tone, pct };
    });
  }, [liveRack, placementPowerSummary]);

  const previewModule = useMemo(() => {
    if (addModuleId == null) return null;
    return galleryModules.find((m) => m.id === addModuleId) ?? null;
  }, [addModuleId, galleryModules]);

  const filteredGalleryModules = useMemo(() => {
    const q = moduleQuery.trim().toLowerCase();
    let rows = [...galleryModules];
    if (q) {
      rows = rows.filter(
        (m) =>
          m.brand.toLowerCase().includes(q) ||
          m.name.toLowerCase().includes(q) ||
          String(m.id) === q,
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
    rackApi
      .list({ limit: 50 })
      .then((res) => {
        setRacks(res.data.racks ?? []);
        if (res.data.racks?.length && selectedRackId == null) {
          setSelectedRackId(res.data.racks[0].id);
        }
      })
      .catch(() => {
        setRacks([]);
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps -- initial rack list only
  }, [rackId]);

  useEffect(() => {
    if (liveMode) return;
    setCasesLoading(true);
    setCompatNote(null);
    const q = caseQuery.trim() || undefined;
    Promise.all([
      caseCatalogApi
        .list({ limit: 200, format_family: "eurorack", q })
        .then((res) => res.data.cases ?? [])
        .catch(() => [] as CatalogCaseListItem[]),
      caseApi
        .list({ limit: 200, format_family: "Eurorack", q })
        .then((res) => res.data.cases ?? [])
        .catch(() => [] as Case[]),
    ])
      .then(([catalogRows, legacyRows]) => {
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
      .finally(() => setCasesLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps -- case catalog load
  }, [liveMode, caseQuery]);

  useEffect(() => {
    if (liveMode || !selectedCatalogSlug) {
      setCompatNote(null);
      return;
    }
    caseCatalogApi
      .compatibility(selectedCatalogSlug, { modules: [], plan_close_lid: false })
      .then((res) => {
        const c = res.data;
        const rails = c.power_headroom.map((r) => `${r.rail} ${r.status}`).join(" · ");
        setCompatNote(
          `Compatibility baseline: ${c.overall_status} · format ${c.format_check.status} · ${rails}`,
        );
      })
      .catch(() => setCompatNote(null));
  }, [liveMode, selectedCatalogSlug]);

  const createRigFromCase = async () => {
    setCreating(true);
    setError("");
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
        setError("Select a Eurorack case (catalog or legacy) before creating a rig.");
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
      setError(formatValidationError(err));
    } finally {
      setCreating(false);
    }
  };

  const refreshLiveRack = async (id: number) => {
    const res = await rackApi.get(id);
    setLiveRack(res.data);
    setPlacementModules(
      (res.data.modules ?? []).map((m) => ({
        module_id: m.module_id,
        row_index: m.row_index,
        start_hp: m.start_hp,
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
    void refreshLiveRack(rackId).catch(() => {
      setLiveRack(null);
      setPlacementError("Unable to load rig for placement.");
    });
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

  const savePlacements = async (next: RackModuleSpec[]) => {
    if (rackId == null) return;
    setPlacementSaving(true);
    setPlacementError("");
    try {
      await rackApi.update(rackId, { modules: next });
      setPlacementModules(next);
      await refreshLiveRack(rackId);
    } catch (err) {
      setPlacementError(formatValidationError(err));
    } finally {
      setPlacementSaving(false);
    }
  };

  const addPlacement = async () => {
    if (addModuleId == null) {
      setPlacementError("Select a module from the gallery.");
      return;
    }
    const next = [
      ...placementModules,
      { module_id: addModuleId, row_index: addRow, start_hp: addStartHp },
    ];
    await savePlacements(next);
  };

  const rowCapacities = useMemo(() => {
    if (!liveRack?.case) return [] as number[];
    const c = liveRack.case;
    if (c.hp_per_row?.length) return c.hp_per_row;
    const rows = c.rows || 1;
    const each = Math.floor((c.total_hp || 0) / rows) || c.total_hp || 0;
    return Array.from({ length: rows }, () => each);
  }, [liveRack]);

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
      setPlacementError("Case row capacity unknown — cannot batch pack.");
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
          ? `Nothing placed. ${result.unplaced.map((u) => `#${u.module_id}: ${u.reason}`).join(" · ")}`
          : "Nothing to place.",
      );
      setBatchPlaceNote("");
      return;
    }
    await savePlacements(result.placements);
    const unMsg = result.unplaced.length
      ? ` · ${result.unplaced.length} could not fit (${result.unplaced
          .map((u) => `#${u.module_id}`)
          .join(", ")})`
      : "";
    setBatchPlaceNote(
      `Batch placed ${result.added.length} module${result.added.length === 1 ? "" : "s"}${unMsg}.`,
    );
    setBatchSelectedIds([]);
  };

  const removePlacement = async (index: number) => {
    const next = placementModules.filter((_, i) => i !== index);
    await savePlacements(next);
  };

  const materializeAllEurorack = async () => {
    setBatchNote("");
    try {
      const res = await caseCatalogApi.materializeBatch({ format_family: "eurorack" });
      const b = res.data;
      setBatchNote(
        `Materialized Eurorack catalog: scanned ${b.scanned}, created ${b.created}, updated ${b.updated}, failed ${b.failed}.`,
      );
      // Refresh legacy case list for create flow
      const legacy = await caseApi.list({ limit: 200, format_family: "Eurorack" });
      setLegacyCases(legacy.data.cases ?? []);
    } catch {
      setBatchNote("Bulk materialize failed. Ensure catalog seed is imported.");
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
        `Module catalog materialize: scanned ${b.scanned}, created ${b.created}, exists ${b.exists}, failed ${b.failed}.`,
      );
      const list = await moduleApi.list({ limit: 500 });
      setGalleryModules(list.data.modules ?? []);
    } catch {
      setModuleMaterializeNote(
        "Module bulk materialize failed. Ensure research catalog is imported and API is up.",
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
        "Cannot confirm a conflicted fusion from the panel — resolve the underlying candidates individually.",
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
        (blocked ? ` · ${blocked} blocked (conflict or missing rep)` : ""),
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
        ? "Demo mode: multi-photo fusion requires a live rig target."
        : "Demo mode: select a rig for live multi-photo reconciliation.",
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
    <section aria-labelledby="builder-title">
      <header className="workspace-header">
        <div>
          <p className="eyebrow">{liveMode ? "Place modules" : "Create rig"}</p>
          <h1 id="builder-title">
            {liveMode ? "Place modules on this rig" : "Establish your module inventory"}
          </h1>
          <p className="muted">
            Bind a Eurorack case, then place modules manually or review photo evidence. Multi-photo
            fusion never auto-confirms inventory. Missing case power stays unchecked.
          </p>
        </div>
      </header>

      <nav className="step-progress" aria-label="Builder steps">
        {(
          [
            { n: 1, label: "Case" },
            { n: 2, label: "Create rig" },
            { n: 3, label: "Place modules" },
          ] as const
        ).map((step) => {
          const state = builderStep > step.n ? "done" : builderStep === step.n ? "current" : "todo";
          return (
            <div
              key={step.n}
              className={`step-progress__item step-progress__item--${state}`}
              aria-current={state === "current" ? "step" : undefined}
            >
              <span className="step-progress__num" aria-hidden="true">
                {step.n}
              </span>
              <span className="step-progress__label">{step.label}</span>
            </div>
          );
        })}
      </nav>

      {!liveMode && preselectedModuleId != null ? (
        <div
          className="panel module-preselect-banner"
          role="status"
          style={{ marginBottom: "var(--space-4)" }}
        >
          <p className="eyebrow" style={{ marginTop: 0 }}>
            Module ready to place
          </p>
          <p style={{ margin: 0 }}>
            {preselectedLabel ||
              (preselectedModule
                ? `${preselectedModule.brand} — ${preselectedModule.name} (${preselectedModule.hp}HP)`
                : `Module #${preselectedModuleId}`)}
            {" · "}
            <strong>create a rig</strong>, then placement opens with this module preselected.
          </p>
        </div>
      ) : null}

      {!liveMode ? (
        <div
          className="panel"
          style={{ marginBottom: "var(--space-4)" }}
          aria-labelledby="case-step-title"
        >
          <p className="eyebrow">Step 1 · case envelope</p>
          <h2 id="case-step-title" style={{ marginTop: 0 }}>
            Choose a case envelope
          </h2>
          <p className="muted">
            Only Eurorack cases are selectable for placement. Other formats remain catalog-only on{" "}
            <Link to="/cases">Cases</Link>.
          </p>
          <div className="toolbar" style={{ marginTop: "var(--space-3)" }}>
            <label className="field" style={{ flex: "1 1 12rem" }}>
              Search cases
              <input
                type="search"
                value={caseQuery}
                placeholder="Manufacturer or model…"
                onChange={(e) => setCaseQuery(e.target.value)}
              />
            </label>
            <label className="field" style={{ flex: "1 1 14rem" }}>
              Catalog case (preferred)
              <select
                value={selectedCatalogSlug ?? ""}
                onChange={(e) => {
                  const slug = e.target.value || null;
                  setSelectedCatalogSlug(slug);
                  if (slug) setSelectedCaseId(null);
                }}
                disabled={casesLoading}
                aria-required={catalogCases.length > 0}
              >
                <option value="">
                  {casesLoading
                    ? "Loading…"
                    : catalogCases.length
                      ? "Select from normalized catalog…"
                      : "No catalog cases (use legacy below)"}
                </option>
                {catalogCases.map((c) => {
                  const cap = c.primary_revision?.capacity_value;
                  const unit = c.primary_revision?.capacity_unit || "hp";
                  return (
                    <option key={c.slug} value={c.slug}>
                      {c.manufacturer} — {c.model}
                      {cap != null ? ` (${cap} ${unit})` : ""}
                    </option>
                  );
                })}
              </select>
            </label>
            <label className="field" style={{ flex: "1 1 14rem" }}>
              Legacy case (fallback)
              <select
                value={selectedCaseId ?? ""}
                onChange={(e) => {
                  setSelectedCaseId(e.target.value ? Number(e.target.value) : null);
                  if (e.target.value) setSelectedCatalogSlug(null);
                }}
                disabled={casesLoading}
              >
                <option value="">
                  {casesLoading
                    ? "Loading…"
                    : catalogCases.length > 0
                      ? "Optional legacy override…"
                      : "Select legacy Eurorack case…"}
                </option>
                {legacyCases.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.brand} — {c.name} ({c.total_hp}HP · {c.rows} row
                    {c.rows === 1 ? "" : "s"})
                  </option>
                ))}
              </select>
            </label>
            <label className="field" style={{ flex: "1 1 10rem" }}>
              Rig name (optional)
              <input
                type="text"
                value={rigName}
                onChange={(e) => setRigName(e.target.value)}
                placeholder="Auto-named if empty"
              />
            </label>
            <button
              type="button"
              className="button button-primary"
              onClick={() => void createRigFromCase()}
              disabled={creating || (selectedCatalogSlug == null && selectedCaseId == null)}
            >
              {creating ? "Creating…" : "Create empty rig"}
            </button>
          </div>
          {selectedCatalogCase ? (
            <div className="stat-row" style={{ marginTop: "var(--space-4)" }}>
              <div className="stat-block">
                <p className="muted" style={{ margin: 0 }}>
                  Layout
                </p>
                <h3 style={{ fontSize: "1rem" }}>
                  {selectedCatalogCase.primary_revision?.capacity_value ?? "—"}{" "}
                  {selectedCatalogCase.primary_revision?.capacity_unit || "hp"}
                  {selectedCatalogCase.primary_revision?.row_count != null
                    ? ` · ${selectedCatalogCase.primary_revision.row_count} row(s)`
                    : ""}
                </h3>
              </div>
              <div className="stat-block">
                <p className="muted" style={{ margin: 0 }}>
                  Power
                </p>
                <h3 style={{ fontSize: "1rem" }}>
                  {selectedCatalogCase.powered === false
                    ? "Unpowered"
                    : selectedCatalogCase.powered === true
                      ? "Powered (materialize fills rails when known)"
                      : "Power unspecified"}
                </h3>
              </div>
            </div>
          ) : null}
          {selectedLegacyCase && !selectedCatalogCase ? (
            <div className="stat-row" style={{ marginTop: "var(--space-4)" }}>
              <div className="stat-block">
                <p className="muted" style={{ margin: 0 }}>
                  Layout
                </p>
                <h3 style={{ fontSize: "1rem" }}>
                  {selectedLegacyCase.hp_per_row?.join(" + ") || selectedLegacyCase.total_hp} HP
                </h3>
              </div>
              <div className="stat-block">
                <p className="muted" style={{ margin: 0 }}>
                  Power
                </p>
                <h3 style={{ fontSize: "1rem" }}>{casePowerSummary(selectedLegacyCase)}</h3>
              </div>
            </div>
          ) : null}
          {compatNote ? (
            <p className="muted" style={{ marginTop: "var(--space-3)", fontSize: "0.9rem" }}>
              {compatNote}
            </p>
          ) : null}
          {error && !liveMode ? (
            <p
              className="status status-danger"
              role="alert"
              style={{ marginTop: "var(--space-3)" }}
            >
              {error}
            </p>
          ) : null}
          {!casesLoading && catalogCases.length === 0 && legacyCases.length === 0 ? (
            <p className="status status-warning" style={{ marginTop: "var(--space-3)" }}>
              No Eurorack cases available. Import <code>data/cases/seed-v1.json</code> via the
              catalog populator, or open <Link to="/cases">Cases</Link>.
            </p>
          ) : null}

          <div style={{ marginTop: "var(--space-4)" }}>
            <button
              type="button"
              className="button button-secondary"
              onClick={() => void materializeAllEurorack()}
            >
              Materialize all Eurorack catalog cases
            </button>
            {batchNote ? (
              <p className="muted" style={{ marginTop: "var(--space-2)" }} role="status">
                {batchNote}
              </p>
            ) : (
              <p className="muted" style={{ marginTop: "var(--space-2)" }}>
                Syncs normalized catalog rows into legacy placement cases (idempotent).
              </p>
            )}
          </div>

          <hr
            style={{ border: 0, borderTop: "1px solid var(--border)", margin: "var(--space-5) 0" }}
          />

          <p className="muted">
            Photo evidence binds to an existing rig. Select a rig for live multi-photo upload, or
            continue with local demo detection after create.
          </p>
          {racks.length > 0 ? (
            <label className="field" htmlFor="evidence-rack" style={{ maxWidth: "24rem" }}>
              Target rig for evidence
              <select
                id="evidence-rack"
                value={selectedRackId ?? ""}
                onChange={(event) =>
                  setSelectedRackId(event.target.value ? Number(event.target.value) : null)
                }
              >
                <option value="">Demo only (no API)</option>
                {racks.map((rack) => (
                  <option key={rack.id} value={rack.id}>
                    #{rack.id} · {rack.name}
                    {rack.case_id != null ? ` · case #${rack.case_id}` : ""}
                  </option>
                ))}
              </select>
            </label>
          ) : (
            <p className="muted">Create a case-bound rig above to enable live evidence APIs.</p>
          )}
        </div>
      ) : (
        <div className="panel" style={{ marginBottom: "var(--space-4)" }}>
          <p className="muted" style={{ marginTop: 0 }}>
            Live placement + evidence for rig #{rackId}.{" "}
            <Link to={`/rigs/${rackId}`}>Open rig detail</Link>
            {" · "}
            <Link to="/racks">Back to rigs</Link>
          </p>
          {liveRack?.case ? (
            <p className="muted">
              Case: {liveRack.case.brand} — {liveRack.case.name}
              {liveRack.case.catalog_slug
                ? ` · catalog ${liveRack.case.catalog_slug}`
                : " · no catalog link (materialize for full compatibility)"}
              {liveRack.case.total_hp != null
                ? ` · ${liveRack.case.total_hp}HP / ${(liveRack.case.hp_per_row || []).join("+") || "—"} rows`
                : ""}
            </p>
          ) : null}

          {preselectedModuleId != null ? (
            <div className="module-preselect-banner" role="status">
              <p style={{ margin: 0 }}>
                Preselected from gallery:{" "}
                <strong>
                  {preselectedModule
                    ? `${preselectedModule.brand} — ${preselectedModule.name}`
                    : `module #${preselectedModuleId}`}
                </strong>
                {preselectedModule?.hp != null ? ` · ${preselectedModule.hp}HP` : ""}
                {" · "}start HP auto-snaps to the first free gap on the selected row.
              </p>
            </div>
          ) : null}

          <h2 style={{ marginTop: "var(--space-3)" }}>Module placement</h2>
          <p className="muted">
            Place modules by row and start HP. Saves through rack validation; catalog compatibility
            runs when the case has <code>meta.catalog_slug</code>.
          </p>

          {rowHpUsage.length > 0 ? (
            <div className="hp-usage" aria-label="Row HP usage">
              {rowHpUsage.map((row) => {
                const pct =
                  row.capacity > 0 ? Math.min(100, Math.round((row.used / row.capacity) * 100)) : 0;
                const tone =
                  pct >= 100 ? "danger" : pct >= 85 ? "warning" : pct > 0 ? "success" : "neutral";
                const blocks = placementModules
                  .map((spec, index) => {
                    if (spec.row_index !== row.row) return null;
                    const hp = resolveModuleHp(spec.module_id) ?? 0;
                    if (hp <= 0 || row.capacity <= 0) return null;
                    const mod =
                      liveRack?.modules?.find(
                        (m) =>
                          m.module_id === spec.module_id &&
                          m.row_index === spec.row_index &&
                          m.start_hp === spec.start_hp,
                      )?.module ?? galleryModules.find((m) => m.id === spec.module_id);
                    const leftPct = (spec.start_hp / row.capacity) * 100;
                    const widthPct = Math.max(1.5, (hp / row.capacity) * 100);
                    const powerKnown = mod?.power_12v_ma != null;
                    return {
                      key: `${spec.module_id}-${spec.start_hp}-${index}`,
                      index,
                      leftPct,
                      widthPct,
                      label: mod ? `${mod.brand} ${mod.name}` : `#${spec.module_id}`,
                      short: mod?.name || `#${spec.module_id}`,
                      hp,
                      start: spec.start_hp,
                      powerKnown,
                    };
                  })
                  .filter(Boolean) as {
                  key: string;
                  index: number;
                  leftPct: number;
                  widthPct: number;
                  label: string;
                  short: string;
                  hp: number;
                  start: number;
                  powerKnown: boolean;
                }[];
                return (
                  <div key={row.row} className="hp-usage__row">
                    <div className="hp-usage__meta">
                      <span>Row {row.row}</span>
                      <span className="muted">
                        {row.used}/{row.capacity}HP used · {row.free} free
                      </span>
                    </div>
                    <div
                      className="usage-bar"
                      role="meter"
                      aria-valuemin={0}
                      aria-valuemax={row.capacity}
                      aria-valuenow={row.used}
                      aria-label={`Row ${row.row} HP usage`}
                    >
                      <div
                        className={`usage-bar__fill usage-bar__fill--${tone}`}
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                    <div
                      className="rack-row-map"
                      role="img"
                      aria-label={`Row ${row.row} layout, ${row.capacity} HP`}
                      onClick={(e) => {
                        // Click empty track → set start HP + row for next placement
                        const track = e.currentTarget.querySelector(".rack-row-map__track");
                        if (!track || e.target !== track) return;
                        const rect = (track as HTMLElement).getBoundingClientRect();
                        const frac = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
                        setAddRow(row.row);
                        setAddStartHp(Math.floor(frac * row.capacity));
                      }}
                    >
                      <div className="rack-row-map__track">
                        {blocks.map((b) => (
                          <button
                            key={b.key}
                            type="button"
                            className={`rack-row-map__block${b.powerKnown ? "" : " rack-row-map__block--unknown-power"}`}
                            style={{ left: `${b.leftPct}%`, width: `${b.widthPct}%` }}
                            title={`${b.label} · HP ${b.start}–${b.start + b.hp - 1}${b.powerKnown ? "" : " · power unknown"}`}
                            onClick={(ev) => {
                              ev.stopPropagation();
                              setAddRow(row.row);
                              setAddStartHp(b.start);
                            }}
                          >
                            <span className="rack-row-map__block-label">{b.short}</span>
                            <span className="rack-row-map__block-hp">{b.hp}H</span>
                          </button>
                        ))}
                        {previewModule &&
                        !batchSelectedIds.length &&
                        addRow === row.row &&
                        previewModule.hp > 0 &&
                        row.capacity > 0 ? (
                          <div
                            className="rack-row-map__block rack-row-map__block--preview"
                            style={{
                              left: `${(addStartHp / row.capacity) * 100}%`,
                              width: `${Math.max(1.5, (previewModule.hp / row.capacity) * 100)}%`,
                            }}
                            aria-hidden="true"
                            title={`Preview: ${previewModule.brand} ${previewModule.name} @ HP ${addStartHp}`}
                          >
                            <span className="rack-row-map__block-label">{previewModule.name}</span>
                            <span className="rack-row-map__block-hp">{previewModule.hp}H</span>
                          </div>
                        ) : null}
                        {batchPreview?.added
                          .filter((spec) => spec.row_index === row.row)
                          .map((spec) => {
                            const hp = resolveModuleHp(spec.module_id) ?? 0;
                            if (hp <= 0 || row.capacity <= 0) return null;
                            const mod = galleryModules.find((m) => m.id === spec.module_id);
                            return (
                              <div
                                key={`batch-preview-${spec.module_id}-${spec.start_hp}`}
                                className="rack-row-map__block rack-row-map__block--preview rack-row-map__block--batch"
                                style={{
                                  left: `${(spec.start_hp / row.capacity) * 100}%`,
                                  width: `${Math.max(1.5, (hp / row.capacity) * 100)}%`,
                                }}
                                aria-hidden="true"
                                title={`Batch plan: ${mod ? `${mod.brand} ${mod.name}` : `#${spec.module_id}`} @ HP ${spec.start_hp}`}
                              >
                                <span className="rack-row-map__block-label">
                                  {mod?.name || `#${spec.module_id}`}
                                </span>
                                <span className="rack-row-map__block-hp">{hp}H</span>
                              </div>
                            );
                          })}
                      </div>
                      <div className="rack-row-map__scale" aria-hidden="true">
                        <span>0</span>
                        <span>{Math.floor(row.capacity / 2)}</span>
                        <span>{row.capacity}HP</span>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          ) : null}

          <div className="toolbar" style={{ marginTop: "var(--space-3)" }}>
            <button
              type="button"
              className="button button-secondary"
              onClick={() => void materializeHpKnownModules()}
            >
              Materialize HP-known modules
            </button>
            <Link className="button button-quiet" to="/modules?hp=known">
              Browse placeable catalog
            </Link>
          </div>
          {moduleMaterializeNote ? (
            <p className="status" role="status">
              {moduleMaterializeNote}
            </p>
          ) : null}

          {placementModules.length > 0 || liveRack?.case ? (
            <div className="power-rail-panel" aria-label="Power rail usage" aria-live="polite">
              <p className="muted" style={{ marginTop: 0, marginBottom: "var(--space-2)" }}>
                Placement power: <strong>{placementPowerSummary.known}</strong> modules with +12
                known
                {placementPowerSummary.unknown
                  ? ` · ${placementPowerSummary.unknown} unknown (not assumed)`
                  : ""}
                {placementPowerSummary.known
                  ? ` · Σ +12 ${placementPowerSummary.draw12}mA / −12 ${placementPowerSummary.drawN12}mA / +5 ${placementPowerSummary.draw5}mA`
                  : ""}
              </p>
              {powerRailMeters.length > 0 ? (
                <div className="power-rail-meters">
                  {powerRailMeters.map((rail) => (
                    <div key={rail.rail} className="power-rail-meters__row">
                      <div className="hp-usage__meta">
                        <span>
                          <span
                            className={`status-chip status-chip--${rail.tone}`}
                            style={{ marginRight: "0.35rem" }}
                          >
                            {rail.rail}
                          </span>
                        </span>
                        <span className="muted">
                          {rail.capacity == null
                            ? `draw ${rail.draw}mA · case capacity unspecified`
                            : `${rail.draw}/${rail.capacity}mA · headroom ${rail.headroom}mA`}
                        </span>
                      </div>
                      <div
                        className="usage-bar"
                        role="meter"
                        aria-valuemin={0}
                        aria-valuemax={rail.capacity ?? 0}
                        aria-valuenow={rail.draw}
                        aria-label={`${rail.rail} power usage`}
                      >
                        <div
                          className={`usage-bar__fill usage-bar__fill--${rail.tone}`}
                          style={{
                            width:
                              rail.capacity == null
                                ? rail.draw > 0
                                  ? "8%"
                                  : "0%"
                                : `${rail.pct}%`,
                          }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              ) : null}
              {placementPowerSummary.unknown > 0 ? (
                <p
                  className="status status-warning"
                  style={{ marginBottom: 0, fontSize: "0.85rem" }}
                >
                  Soft gap: {placementPowerSummary.unknown} module
                  {placementPowerSummary.unknown === 1 ? "" : "s"} without +12 specs — not assumed
                  in draw totals.
                </p>
              ) : null}
            </div>
          ) : null}

          <div className="toolbar" style={{ marginTop: "var(--space-3)" }}>
            <label className="field" style={{ flex: "1 1 10rem" }}>
              Filter modules
              <input
                type="search"
                value={moduleQuery}
                placeholder="Brand, name, id…"
                aria-label="Filter placeable modules"
                onChange={(e) => setModuleQuery(e.target.value)}
              />
            </label>
            <label className="field" style={{ flex: "2 1 14rem" }}>
              Module
              <select
                value={addModuleId ?? ""}
                onChange={(e) => setAddModuleId(e.target.value ? Number(e.target.value) : null)}
                aria-label="Select module to place"
              >
                <option value="">Select module…</option>
                {filteredGalleryModules.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.brand} — {m.name} ({m.hp}HP
                    {m.power_12v_ma != null ? ` · +12 ${m.power_12v_ma}mA` : " · power unknown"}
                    {m.depth_mm != null ? ` · ${m.depth_mm}mm` : " · depth unknown"})
                  </option>
                ))}
              </select>
            </label>
            <label className="field" style={{ flex: "0 0 6rem" }}>
              Row
              <input
                type="number"
                min={0}
                value={addRow}
                aria-label="Row index"
                onChange={(e) => setAddRow(Number(e.target.value) || 0)}
              />
            </label>
            <label className="field" style={{ flex: "0 0 7rem" }}>
              Start HP
              <input
                type="number"
                min={0}
                value={addStartHp}
                aria-label="Start HP"
                title="Auto-fills to first free gap when you pick a module or row; override freely"
                onChange={(e) => setAddStartHp(Number(e.target.value) || 0)}
              />
            </label>
            <button
              type="button"
              className="button button-primary"
              disabled={placementSaving || addModuleId == null}
              onClick={() => void addPlacement()}
            >
              {placementSaving ? "Saving…" : "Add placement"}
            </button>
          </div>
          {addModuleId != null ? (
            <p className="muted" style={{ marginTop: "var(--space-2)", fontSize: "0.85rem" }}>
              Start HP suggests the first free gap ({addStartHp}) on row {addRow}. Override if you
              want a specific slot.
            </p>
          ) : null}

          <div
            className="panel batch-place-panel"
            style={{ marginTop: "var(--space-4)" }}
            aria-labelledby="batch-place-title"
          >
            <p className="eyebrow" style={{ marginTop: 0 }}>
              Multi-module
            </p>
            <h3 id="batch-place-title" style={{ marginTop: 0 }}>
              Batch place
            </h3>
            <p className="muted" style={{ marginTop: 0 }}>
              Select several gallery modules, then pack left-to-right starting at row {addRow}.
              Unknown HP is skipped (never invented). One save applies the full pack.
            </p>
            <div className="toolbar" style={{ marginBottom: "var(--space-3)" }}>
              <button
                type="button"
                className="button button-quiet"
                onClick={selectAllFilteredForBatch}
                disabled={!filteredGalleryModules.length}
              >
                Select filtered ({filteredGalleryModules.length})
              </button>
              <button
                type="button"
                className="button button-quiet"
                onClick={clearBatchSelection}
                disabled={!batchSelectedIds.length}
              >
                Clear selection
              </button>
              <button
                type="button"
                className="button button-primary"
                disabled={placementSaving || !batchSelectedIds.length}
                onClick={() => void addBatchPlacements()}
              >
                {placementSaving ? "Saving…" : `Place ${batchSelectedIds.length || 0} selected`}
              </button>
            </div>
            {batchPreview && batchSelectedIds.length > 0 ? (
              <p className="muted" role="status" style={{ fontSize: "0.9rem" }}>
                Plan: <strong>{batchPreview.added.length}</strong> will pack
                {batchPreview.unplaced.length
                  ? ` · ${batchPreview.unplaced.length} will not fit`
                  : ""}
                {batchPreview.added.length
                  ? ` · e.g. row ${batchPreview.added[0].row_index} @ HP ${batchPreview.added[0].start_hp}`
                  : ""}
              </p>
            ) : null}
            {batchPlaceNote ? (
              <p className="status status-success" role="status">
                {batchPlaceNote}
              </p>
            ) : null}
            <ul className="batch-module-list" aria-label="Batch module selection">
              {filteredGalleryModules.slice(0, 80).map((m) => {
                const checked = batchSelectedIds.includes(m.id);
                const already = placementModules.some((p) => p.module_id === m.id);
                return (
                  <li key={m.id}>
                    <label className={`batch-module-list__item${checked ? " is-selected" : ""}`}>
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={() => toggleBatchModule(m.id)}
                        aria-label={`Select ${m.brand} ${m.name} for batch`}
                      />
                      <span>
                        <strong>
                          {m.brand} — {m.name}
                        </strong>
                        <span className="muted">
                          {" "}
                          · {m.hp}HP
                          {m.power_12v_ma != null
                            ? ` · +12 ${m.power_12v_ma}mA`
                            : " · power unknown"}
                          {already ? " · already on rig" : ""}
                        </span>
                      </span>
                    </label>
                  </li>
                );
              })}
            </ul>
            {filteredGalleryModules.length > 80 ? (
              <p className="muted" style={{ fontSize: "0.85rem" }}>
                Showing first 80 of {filteredGalleryModules.length} filtered — narrow the filter to
                batch more precisely.
              </p>
            ) : null}
            {!filteredGalleryModules.length ? (
              <p className="status status-warning">No modules match the filter.</p>
            ) : null}
          </div>

          {placementError ? (
            <p className="status status-danger" role="alert">
              {placementError}
            </p>
          ) : null}

          {placementModules.length === 0 ? (
            <p className="status status-warning">No modules placed yet.</p>
          ) : (
            <ul style={{ listStyle: "none", padding: 0 }}>
              {placementModules.map((spec, index) => {
                const mod =
                  liveRack?.modules?.find(
                    (m) =>
                      m.module_id === spec.module_id &&
                      m.row_index === spec.row_index &&
                      m.start_hp === spec.start_hp,
                  )?.module ?? galleryModules.find((m) => m.id === spec.module_id);
                return (
                  <li
                    key={`${spec.module_id}-${spec.row_index}-${spec.start_hp}-${index}`}
                    className="panel"
                    style={{ marginBottom: "var(--space-2)", padding: "var(--space-3)" }}
                  >
                    <strong>
                      {mod ? `${mod.brand} — ${mod.name}` : `Module #${spec.module_id}`}
                    </strong>
                    <span className="muted">
                      {" "}
                      · row {spec.row_index} · HP {spec.start_hp}
                      {mod?.hp != null ? `–${spec.start_hp + mod.hp - 1}` : ""}
                    </span>
                    <button
                      type="button"
                      className="button button-quiet"
                      style={{ marginLeft: "var(--space-3)" }}
                      disabled={placementSaving}
                      onClick={() => void removePlacement(index)}
                    >
                      Remove
                    </button>
                  </li>
                );
              })}
            </ul>
          )}

          {rackCompat ? (
            <div className="panel" style={{ marginTop: "var(--space-4)" }} aria-live="polite">
              <h3 style={{ marginTop: 0 }}>Dual-gate compatibility</h3>
              <p className="muted">
                Bridge: {rackCompat.bridge_status}
                {rackCompat.catalog_slug ? ` · ${rackCompat.catalog_slug}` : ""}
              </p>
              <p>{rackCompat.message}</p>
              {rackCompat.compatibility ? (
                <>
                  <div className="gate-chip-row" aria-label="Dual-gate summary">
                    <span
                      className={`status-chip status-chip--${gateTone(rackCompat.compatibility.overall_status)}`}
                    >
                      overall: {rackCompat.compatibility.overall_status}
                    </span>
                    <span
                      className={`status-chip status-chip--${gateTone(rackCompat.compatibility.physical_fit.status)}`}
                    >
                      physical: {rackCompat.compatibility.physical_fit.status}
                    </span>
                    <span
                      className={`status-chip status-chip--${gateTone(rackCompat.compatibility.connector_availability.status)}`}
                    >
                      connectors: {rackCompat.compatibility.connector_availability.status}
                    </span>
                    {rackCompat.compatibility.power_headroom?.map((r) => (
                      <span
                        key={r.rail}
                        className={`status-chip status-chip--${gateTone(r.status)}`}
                      >
                        {r.rail}: {r.status}
                      </span>
                    ))}
                  </div>
                  <p>
                    Overall: <strong>{rackCompat.compatibility.overall_status}</strong>
                    {rackCompat.compatibility.overall_status === "incomplete"
                      ? " — soft gaps only (missing power/depth/case rails stay missing)"
                      : null}
                    {rackCompat.compatibility.overall_status === "conflict"
                      ? " — hard fail (overflow, connectors, or rail over budget)"
                      : null}
                  </p>
                  <ul>
                    <li>
                      Format: <strong>{rackCompat.compatibility.format_check.status}</strong> —{" "}
                      {rackCompat.compatibility.format_check.message}
                    </li>
                    <li>
                      Physical fit: <strong>{rackCompat.compatibility.physical_fit.status}</strong>{" "}
                      — {rackCompat.compatibility.physical_fit.message}
                    </li>
                    <li>
                      Connectors:{" "}
                      <strong>{rackCompat.compatibility.connector_availability.status}</strong>
                      {rackCompat.compatibility.connector_availability.message
                        ? ` — ${rackCompat.compatibility.connector_availability.message}`
                        : ""}
                    </li>
                    <li>
                      +5V: <strong>{rackCompat.compatibility.pos5_compatibility.status}</strong>
                      {rackCompat.compatibility.pos5_compatibility.message
                        ? ` — ${rackCompat.compatibility.pos5_compatibility.message}`
                        : ""}
                    </li>
                    <li>
                      Lid: <strong>{rackCompat.compatibility.lid_close.status}</strong>
                    </li>
                  </ul>
                  {rackCompat.compatibility.power_headroom?.length ? (
                    <>
                      <p className="eyebrow" style={{ marginBottom: 0 }}>
                        Power rails
                      </p>
                      <ul>
                        {rackCompat.compatibility.power_headroom.map((r) => (
                          <li key={r.rail}>
                            <strong>{r.rail}</strong>: {r.status}
                            {r.case_capacity_ma != null
                              ? ` · ${r.module_draw_ma}/${r.case_capacity_ma}mA`
                              : ` · draw ${r.module_draw_ma}mA (case capacity unspecified)`}
                            {r.headroom_ma != null ? ` · headroom ${r.headroom_ma}mA` : ""}
                            {r.message ? ` — ${r.message}` : ""}
                          </li>
                        ))}
                      </ul>
                    </>
                  ) : null}
                  {rackCompat.compatibility.warnings?.length ? (
                    <div className="status status-warning" role="status">
                      <p style={{ marginTop: 0 }}>
                        <strong>Soft warnings</strong> (not hard fails):
                      </p>
                      <ul style={{ marginBottom: 0 }}>
                        {Array.from(
                          new Map(
                            rackCompat.compatibility.warnings.map((w) => [w.code || w.message, w]),
                          ).values(),
                        ).map((w) => (
                          <li key={w.code || w.message}>
                            {w.code ? <code>{w.code}</code> : null}
                            {w.code ? " — " : null}
                            {w.message}
                          </li>
                        ))}
                      </ul>
                    </div>
                  ) : null}
                </>
              ) : null}
            </div>
          ) : null}
        </div>
      )}

      <div className="builder-grid">
        <article className="panel">
          <p className="eyebrow">Method 01</p>
          <h2>Manual selection</h2>
          <p className="muted">
            {liveMode
              ? "Use the placement panel above to add modules with row/HP coordinates."
              : "Create a case-bound rig first, then place modules on the edit screen."}
          </p>
          <Link className="button button-primary" to="/modules">
            Browse module gallery
          </Link>
        </article>

        <article className="panel" aria-labelledby="photo-title">
          <p className="eyebrow">Method 02 · multi-photo evidence</p>
          <h2 id="photo-title">Review rig photo(s)</h2>
          <div className="field">
            <label htmlFor="rig-photo">Rig photo</label>
            <input
              id="rig-photo"
              type="file"
              accept="image/jpeg,image/png,image/webp"
              multiple
              aria-describedby="photo-help photo-error"
              onChange={(event) => selectPhotos(event.target.files)}
            />
            <span id="photo-help" className="muted">
              JPEG, PNG, or WebP · 12 MB each · multiple angles supported.
              {activeRackId != null
                ? ` Live: upload + GET /api/racks/${activeRackId}/evidence/reconcile`
                : " Demo mode until a target rig is selected."}
            </span>
            {error ? (
              <span id="photo-error" role="alert" className="status status-danger">
                {error}
              </span>
            ) : null}
          </div>
          {evidenceState === "ready" ? (
            <div className="evidence-ready">
              <p className="status status-success">Ready to scan: {fileLabel}</p>
              <button
                className="button button-secondary"
                type="button"
                onClick={() => void detectModules()}
              >
                Detect modules
              </button>
            </div>
          ) : null}
          {evidenceState === "uploading" ? (
            <p className="status" role="status">
              Uploading {pendingFiles.length} image(s) and reconciling…
            </p>
          ) : null}
        </article>
      </div>

      {evidenceState === "review" || evidenceState === "confirmed" ? (
        <section className="panel evidence-review" aria-labelledby="review-title">
          <div>
            <p className="eyebrow">Human confirmation required</p>
            <h2 id="review-title">Review ranked detection candidates</h2>
            <p className="muted">
              Provider suggestions remain inferred until you confirm an authoritative gallery match.
              Multi-photo fusion is advisory only.
            </p>
          </div>

          {(fused.length > 0 || reconcileStatus) && (
            <div
              className="panel"
              aria-label="Multi-photo reconciliation"
              style={{ marginBottom: "1rem" }}
            >
              <h3>Multi-photo reconciliation</h3>
              <p className="muted" role="status">
                Status: {reconcileStatus ?? "—"}
                {imageCount ? ` · ${imageCount} image(s)` : ""}
                {reconcileNote ? ` · ${reconcileNote}` : ""}
              </p>
              {fused.length === 0 ? (
                <p className="muted">No fused entities yet.</p>
              ) : (
                <>
                  <div style={{ marginBottom: "0.75rem" }}>
                    <button
                      className="button button-secondary"
                      type="button"
                      onClick={confirmAllNonConflictFused}
                      disabled={evidenceState === "confirmed"}
                    >
                      Confirm all non-conflict fused
                    </button>
                    <p className="muted" style={{ marginTop: "0.5rem" }}>
                      Applies confirm only to non-conflict fusions via their representative
                      candidate. Conflicts must be resolved in the candidate list below.
                    </p>
                    {fusionFeedback ? (
                      <p
                        className="status status-success"
                        role="status"
                        style={{ marginTop: "0.5rem" }}
                      >
                        {fusionFeedback}
                      </p>
                    ) : null}
                  </div>
                  <ul style={{ listStyle: "none", padding: 0 }} aria-label="Fused module entities">
                    {fused.map((entity) => {
                      const applied = fusedApplied[entity.fuse_id];
                      const statusClass = entity.conflict
                        ? "danger"
                        : applied === "confirmed"
                          ? "success"
                          : applied === "rejected"
                            ? "danger"
                            : "warning";
                      const statusText = entity.conflict
                        ? `Conflict: ${entity.conflict_notes.join("; ") || "disagreement"}`
                        : applied
                          ? `Applied: ${applied}`
                          : `Status: ${entity.classification_status} (not confirmed)`;
                      return (
                        <li
                          key={entity.fuse_id}
                          className="detection-row"
                          style={{ marginBottom: "0.75rem" }}
                        >
                          <div>
                            <strong>
                              {entity.manufacturer || "Unknown"} · {entity.model || entity.fuse_id}
                            </strong>
                            <p className="muted">
                              Support: {entity.observation_count} observation(s) across{" "}
                              {entity.supporting_image_ids.length} image(s) · mean confidence{" "}
                              {(entity.mean_confidence * 100).toFixed(0)}%
                              {entity.representative_candidate_id
                                ? " · linked to ranked candidate"
                                : " · no representative candidate"}
                            </p>
                            <p className={`status status-${statusClass}`}>{statusText}</p>
                          </div>
                          <div
                            className="detection-actions"
                            aria-label={`Resolve fused ${entity.model || entity.fuse_id}`}
                          >
                            <button
                              className="button button-secondary"
                              type="button"
                              disabled={
                                entity.conflict ||
                                !entity.representative_candidate_id ||
                                evidenceState === "confirmed"
                              }
                              onClick={() => applyFusedDecision(entity, "confirmed")}
                            >
                              Confirm fused match
                            </button>
                            <button
                              className="button button-quiet"
                              type="button"
                              disabled={
                                !entity.representative_candidate_id || evidenceState === "confirmed"
                              }
                              onClick={() => applyFusedDecision(entity, "rejected")}
                            >
                              Reject fused
                            </button>
                            <button
                              className="button button-quiet"
                              type="button"
                              disabled={
                                !entity.representative_candidate_id || evidenceState === "confirmed"
                              }
                              onClick={() => applyFusedDecision(entity, "deferred")}
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
            </div>
          )}

          <ul className="candidate-list" aria-label="Ranked module candidates">
            {ranked.map((candidate) => (
              <li key={candidate.id} className="detection-row">
                <div>
                  <strong>
                    {candidate.manufacturer} · {candidate.label}
                  </strong>
                  <p className="muted">
                    Confidence {(candidate.confidence * 100).toFixed(0)}%
                    {candidate.alternatives.length
                      ? ` · alternatives: ${candidate.alternatives.join(", ")}`
                      : ""}
                  </p>
                  <p
                    className={`status status-${
                      candidate.status === "confirmed"
                        ? "success"
                        : candidate.status === "rejected"
                          ? "danger"
                          : "warning"
                    }`}
                  >
                    Status: {candidate.status}
                  </p>
                  {candidate.decision ? (
                    <div
                      className="status status-neutral"
                      aria-label="Decision Intelligence advisory"
                    >
                      <strong>Decision Intelligence: advisory only</strong>
                      <span>
                        {" "}
                        · {candidate.decision.disposition.replace("_", " ")}
                        {candidate.decision.confidence != null
                          ? ` · ${(candidate.decision.confidence * 100).toFixed(0)}%`
                          : ""}
                        {candidate.decision.provider ? ` · ${candidate.decision.provider}` : ""}
                      </span>
                      {candidate.decision.reasonCodes?.length ? (
                        <span className="muted">
                          {" "}
                          · {candidate.decision.reasonCodes.join(", ")}
                        </span>
                      ) : null}
                      <p className="muted" style={{ marginBottom: 0 }}>
                        This suggestion cannot confirm hardware. Use Confirm match, Reject, or Defer
                        below.
                      </p>
                    </div>
                  ) : null}
                </div>
                <div className="detection-actions" aria-label={`Resolve ${candidate.label}`}>
                  <button
                    className="button button-secondary"
                    type="button"
                    onClick={() => setStatus(candidate.id, "confirmed")}
                  >
                    Confirm match
                  </button>
                  <button
                    className="button button-quiet"
                    type="button"
                    onClick={() => setStatus(candidate.id, "rejected")}
                  >
                    Reject
                  </button>
                  <button
                    className="button button-quiet"
                    type="button"
                    onClick={() => setStatus(candidate.id, "deferred")}
                  >
                    Defer
                  </button>
                </div>
              </li>
            ))}
          </ul>

          <p className="muted" role="status">
            {confirmedCount} confirmed · {ranked.length - confirmedCount} not confirmed · all
            resolved: {allResolved ? "yes" : "no"}
          </p>

          <button
            className="button button-primary"
            type="button"
            disabled={!allResolved || confirmedCount < 1 || evidenceState === "confirmed"}
            onClick={() => void createInventoryRevision()}
          >
            Create immutable rig revision
          </button>

          {inventoryRevisionId ? (
            <p className="status status-success" role="status">
              Inventory revision ready: {inventoryRevisionId}
              {readyForGeneration ? " · ready for generation" : " · not ready for generation"}.
              {activeRackId != null ? (
                <>
                  {" "}
                  <Link to={`/rigs/${activeRackId}`}>Generate patches on this rig</Link>
                </>
              ) : null}
            </p>
          ) : null}
        </section>
      ) : null}
    </section>
  );
}
