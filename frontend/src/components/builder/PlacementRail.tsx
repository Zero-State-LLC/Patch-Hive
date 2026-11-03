/**
 * PlacementRail — the builder's editable rail. Each case row is drawn to HP scale with its
 * placed modules, the next single placement as a dashed outline, and any batch plan.
 * Clicking an empty stretch of rail, or a placed module, picks that row and start HP.
 * Blocks take their position from --start and --hp against the track's --row-hp.
 */
import type { CSSProperties, MouseEvent } from "react";
import type { RackModuleSpec } from "@/types/api";

export interface RailRow {
  row: number;
  capacity: number;
  used: number;
  free: number;
}

/** What a block needs to draw a module: its name, its width, and whether it states +12V draw. */
export interface RailModule {
  brand: string;
  name: string;
  hp: number;
  power_12v_ma?: number | null;
}

interface PlacementRailProps {
  rows: RailRow[];
  placements: RackModuleSpec[];
  /** The module a placement refers to; undefined while the gallery is still loading. */
  moduleFor: (spec: RackModuleSpec) => RailModule | undefined;
  resolveHp: (moduleId: number) => number | null;
  /** The next single placement, drawn on its row. */
  preview: { module: RailModule; row: number; startHp: number } | null;
  /** Placements a batch place would add. */
  batchPlan: RackModuleSpec[];
  onPickSlot: (row: number, startHp: number) => void;
}

function rowTone(pct: number): string {
  return pct >= 100 ? "danger" : pct >= 85 ? "warning" : pct > 0 ? "success" : "neutral";
}

function slotStyle(start: number, hp: number, index?: number): CSSProperties {
  return { "--start": start, "--hp": hp, "--i": index } as CSSProperties;
}

export default function PlacementRail({
  rows,
  placements,
  moduleFor,
  resolveHp,
  preview,
  batchPlan,
  onPickSlot,
}: PlacementRailProps) {
  return (
    <div className="hp-usage placement-rail" role="group" aria-label="Row HP usage">
      {rows.map((row) => {
        const pct =
          row.capacity > 0 ? Math.min(100, Math.round((row.used / row.capacity) * 100)) : 0;
        const pickEmptyRail = (e: MouseEvent<HTMLDivElement>) => {
          if (e.target !== e.currentTarget) return;
          const rect = e.currentTarget.getBoundingClientRect();
          const frac = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
          onPickSlot(row.row, Math.floor(frac * row.capacity));
        };
        const canDraw = row.capacity > 0;
        return (
          <div key={row.row} className="hp-usage__row">
            <div className="hp-usage__meta">
              <span>Row {row.row}</span>
              <span className="muted">
                {row.used}/{row.capacity}HP used, {row.free} free
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
                className={`usage-bar__fill usage-bar__fill--${rowTone(pct)}`}
                style={{ "--fill": pct / 100 } as CSSProperties}
              />
            </div>
            <div
              className="rack-row-map"
              role="group"
              aria-label={`Row ${row.row} layout, ${row.capacity} HP`}
            >
              <div
                className="rack-row-map__track"
                style={{ "--row-hp": row.capacity } as CSSProperties}
                onClick={pickEmptyRail}
              >
                {placements.map((spec, index) => {
                  if (spec.row_index !== row.row) return null;
                  const hp = resolveHp(spec.module_id) ?? 0;
                  if (hp <= 0 || !canDraw) return null;
                  const mod = moduleFor(spec);
                  const label = mod ? `${mod.brand} ${mod.name}` : `#${spec.module_id}`;
                  const powerKnown = mod?.power_12v_ma != null;
                  return (
                    <button
                      key={`${spec.module_id}-${spec.start_hp}-${index}`}
                      type="button"
                      className={`rack-row-map__block${powerKnown ? "" : " rack-row-map__block--unknown-power"}`}
                      style={slotStyle(spec.start_hp, hp, index)}
                      title={`${label}, HP ${spec.start_hp} to ${spec.start_hp + hp - 1}${powerKnown ? "" : ", power unknown"}`}
                      onClick={(ev) => {
                        ev.stopPropagation();
                        onPickSlot(row.row, spec.start_hp);
                      }}
                    >
                      <span className="rack-row-map__block-label">
                        {mod?.name || `#${spec.module_id}`}
                      </span>
                      <span className="rack-row-map__block-hp">{hp}HP</span>
                    </button>
                  );
                })}
                {preview && preview.row === row.row && preview.module.hp > 0 && canDraw ? (
                  <div
                    className="rack-row-map__block rack-row-map__block--preview"
                    style={slotStyle(preview.startHp, preview.module.hp)}
                    aria-hidden="true"
                    title={`Preview: ${preview.module.brand} ${preview.module.name} at HP ${preview.startHp}`}
                  >
                    <span className="rack-row-map__block-label">{preview.module.name}</span>
                    <span className="rack-row-map__block-hp">{preview.module.hp}HP</span>
                  </div>
                ) : null}
                {batchPlan.map((spec) => {
                  if (spec.row_index !== row.row) return null;
                  const hp = resolveHp(spec.module_id) ?? 0;
                  if (hp <= 0 || !canDraw) return null;
                  const mod = moduleFor(spec);
                  return (
                    <div
                      key={`batch-preview-${spec.module_id}-${spec.start_hp}`}
                      className="rack-row-map__block rack-row-map__block--preview rack-row-map__block--batch"
                      style={slotStyle(spec.start_hp, hp)}
                      aria-hidden="true"
                      title={`Batch plan: ${mod ? `${mod.brand} ${mod.name}` : `#${spec.module_id}`} at HP ${spec.start_hp}`}
                    >
                      <span className="rack-row-map__block-label">
                        {mod?.name || `#${spec.module_id}`}
                      </span>
                      <span className="rack-row-map__block-hp">{hp}HP</span>
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
  );
}
