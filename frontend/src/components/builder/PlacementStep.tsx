/**
 * PlacementStep — builder step 3 on /racks/:id/edit: the rig's rail with the form that places
 * onto it, its power, batch placement, the placed list, and the dual-gate compatibility result.
 */
import type { ComponentProps } from "react";
import { Link } from "react-router-dom";
import { RailSkeleton } from "@/components/Skeletons";
import type { PackResult } from "@/lib/placementPack";
import type { PowerSummary } from "@/lib/powerBudget";
import type { CompatibilityResponse, Module, Rack, RackModule, RackModuleSpec } from "@/types/api";
import PlacementRail from "./PlacementRail";
import PowerMeters from "./PowerMeters";

/** A placed module as the rig returns it, or the gallery record while the rig reloads. */
export type PlacedModule = NonNullable<RackModule["module"]> | Module;

export interface RackCompat {
  bridge_status: string;
  message: string;
  catalog_slug?: string | null;
  compatibility?: CompatibilityResponse | null;
}

export interface AddPlacementForm {
  query: string;
  onQuery: (q: string) => void;
  moduleId: number | null;
  onModule: (id: number | null) => void;
  row: number;
  onRow: (row: number) => void;
  startHp: number;
  onStartHp: (hp: number) => void;
  /** Why the next placement's slot can't take it, if it can't. */
  blocked: string | null;
  onAdd: () => void;
}

export interface BatchPlaceForm {
  selectedIds: number[];
  onToggle: (id: number) => void;
  onSelectAll: () => void;
  onClear: () => void;
  onPlace: () => void;
  plan: PackResult | null;
  note: string;
}

interface PlacementStepProps {
  rack: Rack | null;
  loading: boolean;
  /** The module the gallery sent here (module_id), shown until it is placed. */
  preselected: { label: string; hp: number | null } | null;
  rail: ComponentProps<typeof PlacementRail>;
  powerSummary: PowerSummary;
  /** Gallery modules matching the filter, placeable ones first. */
  modules: Module[];
  add: AddPlacementForm;
  batch: BatchPlaceForm;
  placements: RackModuleSpec[];
  moduleFor: (spec: RackModuleSpec) => PlacedModule | undefined;
  saving: boolean;
  error: string;
  onChoosePowerConfig: (index: number, powerConfigId: number | null) => void;
  onRemove: (index: number) => void;
  compat: RackCompat | null;
  /** Admin and Ops only: load full records for every catalog module with known HP. */
  canLoadModules: boolean;
  onLoadModules: () => void;
  loadNote: string;
}

const BATCH_LIST_LIMIT = 80;

/** What an overall verdict means, beside the verdict itself. */
const OVERALL_MEANS: Record<string, string> = {
  incomplete: "Soft gaps only: missing power, depth or case rails stay missing.",
  conflict: "Hard fail: overflow, connectors, or a rail over budget.",
};

/** Map dual-gate status to chip tone. */
function gateTone(status?: string | null): "success" | "warning" | "danger" | "neutral" {
  if (!status) return "neutral";
  const s = status.toLowerCase();
  if (s === "verified" || s === "ok" || s === "pass") return "success";
  if (s === "incomplete" || s === "warning" || s === "unknown") return "warning";
  if (s === "conflict" || s === "fail" || s === "error") return "danger";
  return "neutral";
}

function moduleOption(m: Module): string {
  return `${m.brand} ${m.name} (${m.hp}HP${m.power_12v_ma != null ? `, +12 ${m.power_12v_ma}mA` : ", power unknown"}${m.depth_mm != null ? `, ${m.depth_mm}mm` : ", depth unknown"})`;
}

export default function PlacementStep({
  rack,
  loading,
  preselected,
  rail,
  powerSummary,
  modules,
  add,
  batch,
  placements,
  moduleFor,
  saving,
  error,
  onChoosePowerConfig,
  onRemove,
  compat,
  canLoadModules,
  onLoadModules,
  loadNote,
}: PlacementStepProps) {
  const rackCase = rack?.case;
  const retired = (rack?.modules ?? []).filter((m) => m.module?.status === "tombstoned");
  const gates = compat?.compatibility;

  return (
    <div className="builder-step">
      {preselected ? (
        <div className="module-preselect-banner" role="status">
          <p>
            Preselected from gallery: <strong>{preselected.label}</strong>
            {preselected.hp != null ? ` (${preselected.hp}HP)` : ""}. Start HP snaps to the first
            free gap on the selected row.
          </p>
        </div>
      ) : null}

      <div className="panel">
        <p className="muted">
          Pick a module, a row and a start HP, or click an empty stretch of rail. Every save is
          checked against the case.
        </p>

        {loading && !rack ? <RailSkeleton label="Loading rig for placement…" /> : null}
        {rail.rows.length > 0 ? <PlacementRail {...rail} /> : null}

        <div className="toolbar builder-toolbar">
          <label className="field">
            Filter modules
            <input
              type="search"
              value={add.query}
              placeholder="Brand, name, id…"
              aria-label="Filter placeable modules"
              onChange={(e) => add.onQuery(e.target.value)}
            />
          </label>
          <label className="field field--wide">
            Module
            <select
              value={add.moduleId ?? ""}
              onChange={(e) => add.onModule(e.target.value ? Number(e.target.value) : null)}
              aria-label="Select module to place"
            >
              <option value="">Select module…</option>
              {modules.map((m) => (
                <option key={m.id} value={m.id}>
                  {moduleOption(m)}
                </option>
              ))}
            </select>
          </label>
          <label className="field field--num">
            Row
            <input
              type="number"
              min={0}
              value={add.row}
              aria-label="Row index"
              onChange={(e) => add.onRow(Number(e.target.value) || 0)}
            />
          </label>
          <label className="field field--num">
            Start HP
            <input
              type="number"
              min={0}
              value={add.startHp}
              aria-label="Start HP"
              title="Auto-fills to first free gap when you pick a module or row; override freely"
              onChange={(e) => add.onStartHp(Number(e.target.value) || 0)}
            />
          </label>
          <button
            type="button"
            className="button button-primary"
            disabled={saving || add.moduleId == null || add.blocked != null}
            title={add.blocked ?? undefined}
            onClick={add.onAdd}
          >
            {saving ? "Saving…" : "Add placement"}
          </button>
        </div>
        {add.moduleId != null ? (
          <p className="muted builder-note">
            Start HP suggests the first free gap ({add.startHp}) on row {add.row}. Override it for a
            specific slot.
          </p>
        ) : null}
        {error ? (
          <p className="status status-danger" role="alert">
            {error}
          </p>
        ) : null}

        {placements.length > 0 || rackCase ? (
          <PowerMeters summary={powerSummary} caseRails={rackCase} />
        ) : null}

        {retired.length > 0 ? (
          <div className="status status-warning builder-retired" role="status">
            <p>
              {retired.length === 1
                ? "One placed module is"
                : `${retired.length} placed modules are`}{" "}
              retired from the catalog. They stay in this rack; check each one.
            </p>
            <ul>
              {retired.map((m) => (
                <li key={m.id}>
                  {m.module?.brand} {m.module?.name}: {m.module?.tombstone_reason ?? "retired"}
                  {m.module?.alternatives?.length
                    ? `. Consider ${m.module.alternatives.map((a) => `${a.brand} ${a.name}`).join(", ")}.`
                    : "."}
                </li>
              ))}
            </ul>
          </div>
        ) : null}

        <div className="toolbar">
          {canLoadModules ? (
            <button type="button" className="button button-secondary" onClick={onLoadModules}>
              Materialize HP-known modules
            </button>
          ) : null}
          <Link className="button button-quiet" to="/modules?hp=known">
            Browse placeable catalog
          </Link>
        </div>
        {loadNote ? (
          <p className="status" role="status">
            {loadNote}
          </p>
        ) : null}
      </div>

      <div className="panel batch-place-panel" aria-labelledby="batch-place-title">
        <h2 id="batch-place-title">Batch place</h2>
        <p className="muted">
          Select several gallery modules, then pack them left to right starting at row {add.row}.
          Unknown HP is skipped, never invented. One save applies the whole pack.
        </p>
        <div className="toolbar">
          <button
            type="button"
            className="button button-quiet"
            onClick={batch.onSelectAll}
            disabled={!modules.length}
          >
            Select filtered ({modules.length})
          </button>
          <button
            type="button"
            className="button button-quiet"
            onClick={batch.onClear}
            disabled={!batch.selectedIds.length}
          >
            Clear selection
          </button>
          <button
            type="button"
            className="button button-primary"
            disabled={saving || !batch.selectedIds.length}
            onClick={batch.onPlace}
          >
            {saving ? "Saving…" : `Place ${batch.selectedIds.length || 0} selected`}
          </button>
        </div>
        {batch.plan && batch.selectedIds.length > 0 ? (
          <p className="muted builder-note" role="status">
            Plan: <strong>{batch.plan.added.length}</strong> will pack
            {batch.plan.unplaced.length ? `, ${batch.plan.unplaced.length} will not fit` : ""}
            {batch.plan.added.length
              ? `, starting at row ${batch.plan.added[0].row_index}, HP ${batch.plan.added[0].start_hp}`
              : ""}
          </p>
        ) : null}
        {batch.note ? (
          <p className="status status-success" role="status">
            {batch.note}
          </p>
        ) : null}
        <ul className="batch-module-list" aria-label="Batch module selection">
          {modules.slice(0, BATCH_LIST_LIMIT).map((m) => {
            const checked = batch.selectedIds.includes(m.id);
            const already = placements.some((p) => p.module_id === m.id);
            return (
              <li key={m.id}>
                <label className={`batch-module-list__item${checked ? " is-selected" : ""}`}>
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={() => batch.onToggle(m.id)}
                    aria-label={`Select ${m.brand} ${m.name} for batch`}
                  />
                  <span>
                    <strong>
                      {m.brand} {m.name}
                    </strong>
                    <span className="muted">
                      {" "}
                      {m.hp}HP
                      {m.power_12v_ma != null ? `, +12 ${m.power_12v_ma}mA` : ", power unknown"}
                      {already ? ", already on rig" : ""}
                    </span>
                  </span>
                </label>
              </li>
            );
          })}
        </ul>
        {modules.length > BATCH_LIST_LIMIT ? (
          <p className="muted builder-note">
            Showing the first {BATCH_LIST_LIMIT} of {modules.length} filtered. Narrow the filter to
            batch more precisely.
          </p>
        ) : null}
        {!modules.length ? <p className="muted">No modules match the filter.</p> : null}
      </div>

      <div className="panel" aria-labelledby="placed-title">
        <h2 id="placed-title">Placed modules</h2>
        {placements.length === 0 ? (
          <p className="muted">No modules placed yet.</p>
        ) : (
          <ul className="placement-list" aria-label="Placed modules">
            {placements.map((spec, index) => {
              const mod = moduleFor(spec);
              return (
                <li key={`${spec.module_id}-${spec.row_index}-${spec.start_hp}-${index}`}>
                  <span>
                    <strong>
                      {mod ? `${mod.brand} ${mod.name}` : `Module #${spec.module_id}`}
                    </strong>{" "}
                    <span className="muted">
                      row {spec.row_index}, HP {spec.start_hp}
                      {mod?.hp != null ? ` to ${spec.start_hp + mod.hp - 1}` : ""}
                    </span>
                  </span>
                  {mod && "power_configs" in mod && mod.power_configs?.length ? (
                    <label className="field placement-list__config">
                      Jumper setting
                      <select
                        value={spec.power_config_id ?? ""}
                        disabled={saving}
                        aria-label={`Jumper setting for ${mod.brand} ${mod.name}`}
                        onChange={(e) =>
                          onChoosePowerConfig(index, e.target.value ? Number(e.target.value) : null)
                        }
                      >
                        <option value="">Not chosen (jumper-dependent draw unknown)</option>
                        {mod.power_configs.map((c) => (
                          <option key={c.id} value={c.id}>
                            {c.label}: +12 {c.power_12v_ma ?? "?"}, −12 {c.power_neg12v_ma ?? "?"},
                            +5 {c.power_5v_ma ?? "?"} mA
                          </option>
                        ))}
                      </select>
                    </label>
                  ) : null}
                  <button
                    type="button"
                    className="button button-quiet"
                    disabled={saving}
                    onClick={() => onRemove(index)}
                  >
                    Remove
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </div>

      {compat ? (
        <div className="panel" aria-labelledby="compat-title" aria-live="polite">
          <h2 id="compat-title">Dual-gate compatibility</h2>
          <p className="muted">
            Bridge: {compat.bridge_status}
            {compat.catalog_slug ? ` (${compat.catalog_slug})` : ""}. {compat.message}
          </p>
          {gates ? (
            <>
              <div className="gate-chip-row" role="group" aria-label="Dual-gate summary">
                <span className={`status-chip status-chip--${gateTone(gates.overall_status)}`}>
                  overall: {gates.overall_status}
                </span>
                {OVERALL_MEANS[gates.overall_status] ? (
                  <span className="muted builder-note">{OVERALL_MEANS[gates.overall_status]}</span>
                ) : null}
              </div>
              <table className="data-table builder-gate-table">
                <thead>
                  <tr>
                    <th scope="col">Check</th>
                    <th scope="col">State</th>
                    <th scope="col">Note</th>
                  </tr>
                </thead>
                <tbody>
                  {[
                    { check: "Format", gate: gates.format_check },
                    { check: "Physical fit", gate: gates.physical_fit },
                    { check: "Connectors", gate: gates.connector_availability },
                    { check: "+5V", gate: gates.pos5_compatibility },
                    { check: "Lid", gate: { status: gates.lid_close.status, message: "" } },
                  ].map(({ check, gate }) => (
                    <tr key={check}>
                      <th scope="row">{check}</th>
                      <td>
                        <span className={`status status-${gateTone(gate.status)}`}>
                          {gate.status}
                        </span>
                      </td>
                      <td>{gate.message && gate.message !== gate.status ? gate.message : ""}</td>
                    </tr>
                  ))}
                  {gates.power_headroom?.map((r) => (
                    <tr key={r.rail}>
                      <th scope="row">{r.rail} rail</th>
                      <td>
                        <span className={`status status-${gateTone(r.status)}`}>{r.status}</span>
                      </td>
                      <td>
                        {r.case_capacity_ma != null
                          ? `${r.module_draw_ma}/${r.case_capacity_ma}mA`
                          : `Draw ${r.module_draw_ma}mA, case capacity unspecified`}
                        {r.headroom_ma != null && !r.unknown_draw_count
                          ? `, headroom ${r.headroom_ma}mA`
                          : ""}
                        {r.message ? `. ${r.message}` : ""}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {gates.warnings?.length ? (
                <div className="status status-warning builder-warnings" role="status">
                  <p>
                    <strong>Soft warnings</strong> (not hard fails):
                  </p>
                  <ul>
                    {Array.from(
                      new Map(gates.warnings.map((w) => [w.code || w.message, w])).values(),
                    ).map((w) => (
                      <li key={w.code || w.message}>
                        {w.code ? <code>{w.code}</code> : null}
                        {w.code ? ": " : null}
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
  );
}
