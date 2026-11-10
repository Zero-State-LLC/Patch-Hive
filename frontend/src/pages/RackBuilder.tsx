import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { canonApi, caseApi, caseCatalogApi, moduleApi, rackApi } from "@/lib/api";
import { rigDetailToRack } from "@/lib/canonRigAdapter";
import CaseStep from "@/components/builder/CaseStep";
import PlacementStep, { type RackCompat } from "@/components/builder/PlacementStep";
import Toast from "@/components/Toast";
import { failureReason } from "@/lib/loadError";
import { checkSlot, moveTo, slotPhrase, type Slot } from "@/lib/placementMove";
import { firstFreeStartHp, packModulesOntoRows } from "@/lib/placementPack";
import { placementPower, railMeter, summarizePower, type RailKey } from "@/lib/powerBudget";
import { openRowWidths } from "@/lib/rigRows";
import { useAuthStore, useReaderKey } from "@/lib/store";
import { useDebouncedValue } from "@/lib/useDebouncedValue";
import { useMountedRef } from "@/lib/useMountedRef";
import { useToast } from "@/lib/useToast";
import type { Case, CatalogCaseListItem, Module, Rack, RackModuleSpec } from "@/types/api";

const BUILDER_STEPS = [
  { n: 1, label: "Case" },
  { n: 2, label: "Create rig" },
  { n: 3, label: "Place modules" },
] as const;

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

/**
 * What this page holds depends on who's reading: the module picker has more rows for a signed-in
 * reader (owner decision 39), and rigs belong to an account. Signing out stays
 * on the page, so a change of reader starts it over: nothing the last reader had stays on screen,
 * and an answer still on its way lands nowhere. A token renewal is not a change of reader.
 */
export default function RackBuilderPage() {
  return <RackBuilder key={useReaderKey()} />;
}

function RackBuilder() {
  const mounted = useMountedRef();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { id: routeId } = useParams<{ id: string }>();
  const rackId = routeId && /^\d+$/.test(routeId) ? Number(routeId) : null;
  const liveMode = rackId != null;
  const preselectedCaseId = Number(searchParams.get("case_id") || "") || null;
  const preselectedCatalogSlug = searchParams.get("catalog_slug") || null;
  const preselectedModuleId = Number(searchParams.get("module_id") || "") || null;

  // Rigs belong to the signed-in user, so creating one needs an account.
  const signedIn = useAuthStore((st) => st.isAuthenticated());
  // Bulk materialize rewrites shared catalog data; the API allows only Admin and Ops.
  const canBulkMaterialize = useAuthStore(
    (st) => st.user?.role === "Admin" || st.user?.role === "Ops",
  );

  /** C0: case-bound create on /racks/new — catalog-first with legacy materialize bridge */
  const [catalogCases, setCatalogCases] = useState<CatalogCaseListItem[]>([]);
  const [legacyCases, setLegacyCases] = useState<Case[]>([]);
  const [casesLoading, setCasesLoading] = useState(false);
  const [selectedCaseId, setSelectedCaseId] = useState<number | null>(preselectedCaseId);
  // The owner goes on with no Case (spec 009 story 36): each row is as wide as what's on it.
  const [withoutCase, setWithoutCase] = useState(false);
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
  const [catalogSyncing, setCatalogSyncing] = useState(false);
  const [moduleMaterializeNote, setModuleMaterializeNote] = useState("");
  const [modulesMaterializing, setModulesMaterializing] = useState(false);
  const [moduleQuery, setModuleQuery] = useState("");
  /** Multi-select for batch place (module ids). */
  const [batchSelectedIds, setBatchSelectedIds] = useState<number[]>([]);
  const [batchPlaceNote, setBatchPlaceNote] = useState("");
  /** Label for module_id deep-link when gallery list is not yet loaded (create flow). */
  const [preselectedLabel, setPreselectedLabel] = useState<string | null>(null);

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

  /** Per-row HP occupancy for visual usage bars. A Rig with no Case (spec 009) has open rows,
   * as wide as what's on them. */
  const rowHpUsage = useMemo(() => {
    if (!liveRack) return [] as { row: number; capacity: number; used: number; free: number }[];
    if (!liveRack.case) {
      return openRowWidths(placementModules, resolveModuleHp).map((capacity, row) => {
        const used = placementModules
          .filter((spec) => spec.row_index === row)
          .reduce((sum, spec) => sum + (resolveModuleHp(spec.module_id) ?? 0), 0);
        return { row, capacity, used, free: capacity - used, open: true };
      });
    }
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

  const builderStep = liveMode ? 3 : selectedCatalogSlug || selectedCaseId || withoutCase ? 2 : 1;

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
    if (!liveMode || addModuleId == null || !liveRack) return;
    const modHp = resolveModuleHp(addModuleId);
    if (modHp == null || modHp <= 0) return;
    const rigCase = liveRack.case;
    const capacity = !rigCase
      ? Number.POSITIVE_INFINITY
      : (rigCase.hp_per_row?.[addRow] ??
        (rigCase.rows ? Math.floor(rigCase.total_hp / rigCase.rows) : rigCase.total_hp));
    const next = nextFreeStartHp(
      addRow,
      modHp,
      placementModules,
      resolveModuleHp,
      capacity || rigCase?.total_hp || 0,
    );
    setAddStartHp(next);
    // Only when selection changes — not every keystroke of start HP
  }, [liveMode, addModuleId, addRow, placementModules, liveRack, resolveModuleHp]);

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
      if (caseId == null && !withoutCase) {
        setCreateError("Choose a Eurorack Case, or go on without one, before creating a rig.");
        setCreating(false);
        return;
      }
      const res = await rackApi.create({
        case_id: withoutCase ? null : caseId,
        name: rigName.trim() || undefined,
        modules: [],
      });
      const id = res.data.id;
      const qs = preselectedModuleId != null ? `?module_id=${preselectedModuleId}` : "";
      if (mounted.current) navigate(`/racks/${id}/edit${qs}`);
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
    if (!liveRack) return [] as number[];
    // Open rows have no end to run past; only an overlap stops a placement.
    if (!liveRack.case) {
      return openRowWidths(placementModules, resolveModuleHp).map(() => Number.POSITIVE_INFINITY);
    }
    const c = liveRack.case;
    if (c.hp_per_row?.length) return c.hp_per_row;
    const rows = c.rows || 1;
    const each = Math.floor((c.total_hp || 0) / rows) || c.total_hp || 0;
    return Array.from({ length: rows }, () => each);
  }, [liveRack, placementModules, resolveModuleHp]);

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
    setCatalogSyncing(true);
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
    } finally {
      setCatalogSyncing(false);
    }
  };

  const materializeHpKnownModules = async () => {
    setModuleMaterializeNote("");
    setModulesMaterializing(true);
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
    } finally {
      setModulesMaterializing(false);
    }
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
          <h1 id="builder-title">{liveMode ? "Module placement" : "Enter your Rig by hand"}</h1>
          {liveMode ? (
            <p className="muted builder-rig-line">
              <strong>{liveRack?.name ?? "This rig"}</strong>
              {liveRack?.case
                ? caseLine(liveRack.case)
                : liveRack
                  ? ", with no Case named, so each row is as wide as the Modules on it"
                  : ""}
              .
            </p>
          ) : (
            <p className="muted">
              Choose a Case if you know it, create the Rig, then place its Modules.
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
            loadingModules={modulesMaterializing}
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
              if (slug) {
                setSelectedCaseId(null);
                setWithoutCase(false);
              }
            }}
            selectedCaseId={selectedCaseId}
            onSelectLegacy={(id) => {
              setSelectedCaseId(id);
              if (id != null) {
                setSelectedCatalogSlug(null);
                setWithoutCase(false);
              }
            }}
            withoutCase={withoutCase}
            onWithoutCase={(without) => {
              setWithoutCase(without);
              if (without) {
                setSelectedCaseId(null);
                setSelectedCatalogSlug(null);
              }
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
            syncing={catalogSyncing}
            syncNote={batchNote}
            onSyncCatalog={() => void materializeAllEurorack()}
          />
        )}
      </div>
      <Toast toast={toast} onDismiss={dismissToast} actionDisabled={placementSaving} />
    </section>
  );
}
