/**
 * PlacementRail — the builder's editable rail. Each case row is drawn to HP scale with its
 * placed modules, the next single placement as a dashed outline, and any batch plan.
 * Clicking an empty stretch of rail, or a placed module, picks that row and start HP.
 * Blocks take their position from --start and --hp against the track's --row-hp.
 *
 * Placed modules move three ways, all snapping to whole HP: drag one along a row or onto another;
 * click or tap one, then click or tap its new spot (no dragging needed); or press Enter on one,
 * move it with the arrows (1 HP, 4 with Shift, Up and Down change rows) and press Enter again.
 * Escape puts it back and Delete removes it. Every move is checked first: a slot that overlaps
 * another module or runs off the row shows red, says why under that row, and is never offered.
 */
import { useEffect, useRef, useState } from "react";
import type {
  CSSProperties,
  KeyboardEvent,
  MouseEvent,
  PointerEvent as ReactPointerEvent,
} from "react";
import {
  nudgeSlot,
  slotPhrase,
  startUnderPointer,
  type NudgeKey,
  type Slot,
  type SlotCheck,
} from "@/lib/placementMove";
import type { RackModuleSpec } from "@/types/api";

export interface RailRow {
  row: number;
  capacity: number;
  used: number;
  free: number;
  /** A row of a Rig with no Case: drawn to a width, but with no end to fill or run past. */
  open?: boolean;
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
  /** The next single placement, drawn on its row, with whether its slot is free. */
  preview: { module: RailModule; row: number; startHp: number; check?: SlotCheck } | null;
  /** Placements a batch place would add. */
  batchPlan: RackModuleSpec[];
  onPickSlot: (row: number, startHp: number) => void;
  /** Whether a module may sit in a slot; the placement at `ignoreIndex` is the one moving. */
  checkSlot?: (slot: Slot, ignoreIndex: number) => SlotCheck;
  /** Saves a placed module's move. Without it the blocks only pick slots. */
  onMove?: (index: number, row: number, startHp: number) => void;
  onRemove?: (index: number) => void;
  /** A save is under way: nothing moves until it settles. */
  busy?: boolean;
  /** A module to focus once it is drawn, such as one Undo just put back. */
  focusRequest?: { module_id: number; row: number; start: number } | null;
}

/** The next placement while it is dragged; placed modules use their index. */
const PREVIEW = -1;
/** A press that travels less than this is a click, not a drag. */
const DRAG_THRESHOLD_PX = 4;
const ARROWS: readonly string[] = ["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"];

interface Drag extends Slot {
  index: number;
  /** Held down and dragged, picked up by a click or tap, or picked up with Enter. */
  via: "pointer" | "tap" | "keyboard";
  check: SlotCheck;
}

interface Press {
  index: number;
  pointerId: number;
  x: number;
  y: number;
  /** How far into the module, in HP, the pointer took hold of it. */
  grabHp: number;
  hp: number;
  moved: boolean;
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
  checkSlot,
  onMove,
  onRemove,
  busy = false,
  focusRequest = null,
}: PlacementRailProps) {
  const root = useRef<HTMLDivElement>(null);
  const press = useRef<Press | null>(null);
  const clickSwallowed = useRef(false);
  /** The module a keyboard drop moved, to focus again once it is drawn in its new place. */
  const refocus = useRef<{ module_id: number; row: number; start: number } | null>(null);
  const [drag, setDragState] = useState<Drag | null>(null);
  // The same drag, read by handlers that may run before React draws the last update.
  const current = useRef<Drag | null>(null);
  const setDrag = (next: Drag | null) => {
    current.current = next;
    setDragState(next);
  };
  const [said, setSaid] = useState("");

  const capacities = rows.map((r) => r.capacity);
  const canMove = Boolean(onMove && checkSlot);
  const movable = canMove && !busy;
  const free: SlotCheck = { ok: true };
  const check = (slot: Slot, index: number) =>
    checkSlot ? checkSlot(slot, index === PREVIEW ? -1 : index) : free;
  const nameAt = (index: number) => {
    const mod = index === PREVIEW ? preview?.module : moduleFor(placements[index]);
    return mod?.name || `Module #${placements[index]?.module_id ?? ""}`;
  };

  // A save that starts mid-drag ends the drag: the placements under it are about to change.
  useEffect(() => {
    if (busy) {
      press.current = null;
      setDrag(null);
    }
  }, [busy]);

  useEffect(() => {
    if (focusRequest) refocus.current = focusRequest;
  }, [focusRequest]);

  useEffect(() => {
    const target = refocus.current;
    if (!target) return;
    const block = root.current?.querySelector<HTMLElement>(
      `[data-module="${target.module_id}"][data-row="${target.row}"][data-start="${target.start}"]`,
    );
    if (block) {
      block.focus();
      refocus.current = null;
    }
  }, [placements, focusRequest]);

  // A carry that changes row keeps the ghost in view, on a case taller than the screen.
  const carriedRow = drag && drag.via !== "pointer" ? drag.row : null;
  useEffect(() => {
    if (carriedRow == null) return;
    root.current
      ?.querySelector<HTMLElement>(".rack-row-map__block--ghost")
      ?.scrollIntoView?.({ block: "nearest" });
  }, [carriedRow]);

  const begin = (index: number, slot: Slot, via: Drag["via"]) =>
    setDrag({ ...slot, index, via, check: check(slot, index) });

  const follow = (slot: Slot) => {
    const d = current.current;
    if (d) setDrag({ ...d, ...slot, check: check(slot, d.index) });
  };

  /** Drops the module where the drag left it, if that slot is free and new. */
  const drop = (d: Drag) => {
    setDrag(null);
    const name = nameAt(d.index);
    if (d.index === PREVIEW) {
      onPickSlot(d.row, d.start);
      return;
    }
    const spec = placements[d.index];
    const home = slotPhrase(spec.row_index, spec.start_hp);
    if (!d.check.ok) {
      setSaid(`${name} can't go there. ${d.check.reason} It stays at ${home}.`);
      return;
    }
    if (d.row === spec.row_index && d.start === spec.start_hp) {
      setSaid(`${name} stays at ${home}.`);
      return;
    }
    if (d.via !== "pointer") {
      refocus.current = { module_id: spec.module_id, row: d.row, start: d.start };
    }
    setSaid("");
    onMove?.(d.index, d.row, d.start);
  };

  const putBack = (d: Drag) => {
    setDrag(null);
    if (d.index === PREVIEW) return;
    const spec = placements[d.index];
    setSaid(`${nameAt(d.index)} put back at ${slotPhrase(spec.row_index, spec.start_hp)}.`);
  };

  // Escape puts back a module the pointer is carrying, or one picked up by a click or tap.
  const pointerCarrying = drag?.via === "pointer" || drag?.via === "tap";
  useEffect(() => {
    if (!pointerCarrying) return;
    const onKey = (event: globalThis.KeyboardEvent) => {
      const d = current.current;
      if (event.key !== "Escape" || !d || event.defaultPrevented) return;
      press.current = null;
      putBack(d);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- reads the drag through its ref
  }, [pointerCarrying]);

  /** The track nearest the pointer vertically, so a drag between rows still lands on one. */
  const trackNear = (clientY: number) => {
    let best: { row: number; rect: DOMRect } | null = null;
    let bestGap = Infinity;
    for (const el of root.current?.querySelectorAll<HTMLElement>("[data-rail-row]") ?? []) {
      const rect = el.getBoundingClientRect();
      const gap = Math.abs(clientY - (rect.top + rect.height / 2));
      if (gap < bestGap) {
        bestGap = gap;
        best = { row: Number(el.dataset.railRow), rect };
      }
    }
    return best;
  };

  const pointerDown = (index: number, hp: number) => (event: ReactPointerEvent<HTMLElement>) => {
    // A drag that ended without the browser's click must not swallow this press's click.
    clickSwallowed.current = false;
    if (!movable || event.button !== 0 || hp <= 0) return;
    const track = event.currentTarget.parentElement?.getBoundingClientRect();
    const capacity = Number(event.currentTarget.parentElement?.dataset.capacity ?? 0);
    const block = event.currentTarget.getBoundingClientRect();
    const grabHp =
      track && track.width > 0 ? ((event.clientX - block.left) / track.width) * capacity : 0;
    press.current = {
      index,
      pointerId: event.pointerId,
      x: event.clientX,
      y: event.clientY,
      grabHp,
      hp,
      moved: false,
    };
    event.currentTarget.setPointerCapture?.(event.pointerId);
  };

  /** The slot under the pointer for the module it holds. */
  const slotAt = (p: Press, clientX: number, clientY: number): Slot | null => {
    const near = trackNear(clientY);
    if (!near) return null;
    const capacity = capacities[near.row] ?? 0;
    return {
      row: near.row,
      start: startUnderPointer(clientX, near.rect, capacity, p.hp, p.grabHp),
      hp: p.hp,
    };
  };

  const pointerMove = (event: ReactPointerEvent<HTMLElement>) => {
    const p = press.current;
    if (!p || p.pointerId !== event.pointerId) return;
    if (!p.moved && Math.hypot(event.clientX - p.x, event.clientY - p.y) < DRAG_THRESHOLD_PX) {
      return;
    }
    const slot = slotAt(p, event.clientX, event.clientY);
    if (!slot) return;
    if (!p.moved) {
      p.moved = true;
      begin(p.index, slot, "pointer");
    } else {
      follow(slot);
    }
  };

  const pointerUp = (event: ReactPointerEvent<HTMLElement>) => {
    const p = press.current;
    if (!p || p.pointerId !== event.pointerId) return;
    press.current = null;
    const d = current.current;
    if (!p.moved || !d) return;
    // The browser follows a drag of a placed module with a click; it must not also pick a slot.
    if (p.index !== PREVIEW) clickSwallowed.current = true;
    const slot = slotAt(p, event.clientX, event.clientY) ?? d;
    drop({ ...d, ...slot, check: check(slot, d.index) });
  };

  const pointerCancel = () => {
    press.current = null;
    const d = current.current;
    if (d?.via === "pointer") putBack(d);
  };

  /** Picks a module up without dragging it, and says how to put it down. */
  const pickUp = (index: number, slot: Slot, via: "tap" | "keyboard") => {
    begin(index, slot, via);
    const where = slotPhrase(slot.row, slot.start);
    setSaid(
      via === "tap"
        ? `${nameAt(index)} picked up at ${where}. Click or tap its new spot on the rail, or the module again to put it back.`
        : `${nameAt(index)} picked up at ${where}. Arrow keys move it, Shift moves 4 HP, Up and Down change rows. Enter drops it, Escape puts it back.`,
    );
  };

  /**
   * A click or tap on a row while a module is picked up: it drops there if the slot is free,
   * and otherwise stays picked up on that slot, showing why it can't go there.
   */
  const placeCarried = (rowIndex: number, track: DOMRect, clientX: number) => {
    const d = current.current;
    if (!d || d.via === "pointer" || d.index === PREVIEW) return false;
    const capacity = capacities[rowIndex] ?? 0;
    const slot = {
      row: rowIndex,
      start: startUnderPointer(clientX, track, capacity, d.hp, d.hp / 2),
      hp: d.hp,
    };
    const result = check(slot, d.index);
    if (result.ok) {
      drop({ ...d, ...slot, check: result });
    } else {
      setDrag({ ...d, ...slot, check: result });
      setSaid(`${slotPhrase(slot.row, slot.start)}. Blocked: ${result.reason}`);
    }
    return true;
  };

  const keyDown = (index: number, slot: Slot) => (event: KeyboardEvent<HTMLButtonElement>) => {
    const carrying = drag && drag.via !== "pointer" && drag.index === index ? drag : null;
    if (event.key === "Enter") {
      if (!movable) return;
      // Enter would also click the block; here it picks the module up or drops it.
      event.preventDefault();
      if (carrying) {
        drop(carrying);
      } else {
        pickUp(index, slot, "keyboard");
      }
      return;
    }
    if (carrying && event.key === "Escape") {
      event.preventDefault();
      putBack(carrying);
      return;
    }
    if (carrying && ARROWS.includes(event.key)) {
      event.preventDefault();
      const next = nudgeSlot(carrying, event.key as NudgeKey, event.shiftKey, capacities);
      const result = check(next, index);
      setDrag({ ...carrying, ...next, check: result });
      setSaid(
        `${slotPhrase(next.row, next.start)}.${result.ok ? "" : ` Blocked: ${result.reason}`}`,
      );
      return;
    }
    if (!carrying && onRemove && !busy && (event.key === "Delete" || event.key === "Backspace")) {
      event.preventDefault();
      onRemove(index);
    }
  };

  const blocked = drag && !drag.check.ok ? drag.check.reason : null;
  const previewBlocked = !drag && preview?.check && !preview.check.ok ? preview.check.reason : null;
  /** While a module is picked up without dragging, the hint says so and how to put it down. */
  const carryHint =
    drag && drag.via !== "pointer" && drag.index !== PREVIEW
      ? drag.via === "tap"
        ? `${nameAt(drag.index)} is picked up. Click or tap its new spot, or the module again to put it back.`
        : `${nameAt(drag.index)} is picked up. Arrow keys move it, Enter drops it, Escape puts it back.`
      : null;
  /** The row whose "can't go there" line shows: the one the blocked slot is on. */
  const whyRow = blocked ? drag?.row : previewBlocked ? preview?.row : null;

  return (
    <div
      ref={root}
      className="hp-usage placement-rail"
      role="group"
      aria-label="Row HP usage"
      data-dragging={drag ? drag.via : undefined}
    >
      {rows.map((row) => {
        const pct =
          row.capacity > 0 ? Math.min(100, Math.round((row.used / row.capacity) * 100)) : 0;
        const pickEmptyRail = (e: MouseEvent<HTMLDivElement>) => {
          if (e.target !== e.currentTarget) return;
          const rect = e.currentTarget.getBoundingClientRect();
          if (placeCarried(row.row, rect, e.clientX)) return;
          const frac = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
          onPickSlot(row.row, Math.floor(frac * row.capacity));
        };
        // A module picked up by a click follows the mouse, so the ghost shows the spot first.
        const hoverCarried = (e: ReactPointerEvent<HTMLDivElement>) => {
          const d = current.current;
          if (d?.via !== "tap" || e.pointerType !== "mouse") return;
          const rect = e.currentTarget.getBoundingClientRect();
          follow({
            row: row.row,
            start: startUnderPointer(e.clientX, rect, row.capacity, d.hp, d.hp / 2),
            hp: d.hp,
          });
        };
        const canDraw = row.capacity > 0;
        // The next placement follows the pointer while it is dragged.
        const previewSlot =
          drag?.index === PREVIEW
            ? { row: drag.row, start: drag.start }
            : preview
              ? { row: preview.row, start: preview.startHp }
              : null;
        const previewState =
          drag?.index === PREVIEW
            ? drag.check.ok
              ? undefined
              : "blocked"
            : preview?.check && !preview.check.ok
              ? "blocked"
              : undefined;
        return (
          <div key={row.row} className="hp-usage__row">
            <div className="hp-usage__meta">
              <span>Row {row.row}</span>
              <span className="muted">
                {row.open
                  ? `${row.used}HP placed, no Case named`
                  : `${row.used}/${row.capacity}HP used, ${row.free} free`}
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
                data-rail-row={row.row}
                data-capacity={row.capacity}
                onClick={pickEmptyRail}
                onPointerMove={hoverCarried}
              >
                {placements.map((spec, index) => {
                  if (spec.row_index !== row.row) return null;
                  const hp = resolveHp(spec.module_id) ?? 0;
                  if (hp <= 0 || !canDraw) return null;
                  const mod = moduleFor(spec);
                  const label = mod ? `${mod.brand} ${mod.name}` : `#${spec.module_id}`;
                  const powerKnown = mod?.power_12v_ma != null;
                  const lifted = drag?.index === index;
                  return (
                    <button
                      // A new slot is a new key, so a moved or restored module slides into place.
                      key={`${spec.module_id}-${spec.row_index}-${spec.start_hp}-${index}`}
                      type="button"
                      className={`rack-row-map__block${powerKnown ? "" : " rack-row-map__block--unknown-power"}${movable ? " is-movable" : ""}`}
                      style={slotStyle(spec.start_hp, hp, index)}
                      data-module={spec.module_id}
                      data-row={spec.row_index}
                      data-start={spec.start_hp}
                      data-lifted={lifted ? "true" : undefined}
                      aria-keyshortcuts={movable ? "Enter Delete" : undefined}
                      title={`${label}, HP ${spec.start_hp} to ${spec.start_hp + hp - 1}${powerKnown ? "" : ", power unknown"}`}
                      onClick={(ev) => {
                        ev.stopPropagation();
                        if (clickSwallowed.current) {
                          clickSwallowed.current = false;
                          return;
                        }
                        // A rail that can't move modules picks this slot for the next placement.
                        if (!canMove) {
                          onPickSlot(row.row, spec.start_hp);
                          return;
                        }
                        if (!movable) return;
                        const d = current.current;
                        if (d && d.via !== "pointer" && d.index === index) {
                          putBack(d);
                          return;
                        }
                        const track = ev.currentTarget.parentElement?.getBoundingClientRect();
                        if (d && d.via !== "pointer" && track) {
                          placeCarried(row.row, track, ev.clientX);
                          return;
                        }
                        pickUp(index, { row: spec.row_index, start: spec.start_hp, hp }, "tap");
                      }}
                      onPointerDown={pointerDown(index, hp)}
                      onPointerMove={pointerMove}
                      onPointerUp={pointerUp}
                      onPointerCancel={pointerCancel}
                      onKeyDown={keyDown(index, { row: spec.row_index, start: spec.start_hp, hp })}
                      onBlur={(ev) => {
                        // Focus moving to something else puts the module back. A click on the
                        // rail itself, which is how a picked-up module is dropped, only moves
                        // focus to a page container that holds the rail, such as <main>.
                        const d = current.current;
                        const to = ev.relatedTarget as Node | null;
                        const rail = root.current;
                        if (d && d.via !== "pointer" && d.index === index && to && rail) {
                          if (!rail.contains(to) && !to.contains(rail)) putBack(d);
                        }
                      }}
                    >
                      <span className="rack-row-map__block-label">
                        {mod?.name || `#${spec.module_id}`}
                      </span>
                      <span className="rack-row-map__block-hp">{hp}HP</span>
                    </button>
                  );
                })}
                {drag && drag.index !== PREVIEW && drag.row === row.row && canDraw ? (
                  <div
                    className="rack-row-map__block rack-row-map__block--ghost"
                    style={slotStyle(drag.start, drag.hp)}
                    data-state={drag.check.ok ? undefined : "blocked"}
                    aria-hidden="true"
                  >
                    <span className="rack-row-map__block-label">{nameAt(drag.index)}</span>
                    <span className="rack-row-map__block-hp">{drag.hp}HP</span>
                  </div>
                ) : null}
                {preview && previewSlot?.row === row.row && preview.module.hp > 0 && canDraw ? (
                  <div
                    className={`rack-row-map__block rack-row-map__block--preview${movable ? " is-movable" : ""}`}
                    style={slotStyle(previewSlot.start, preview.module.hp)}
                    data-state={previewState}
                    aria-hidden="true"
                    title={`Preview: ${preview.module.brand} ${preview.module.name} at HP ${previewSlot.start}`}
                    onPointerDown={pointerDown(PREVIEW, preview.module.hp)}
                    onPointerMove={pointerMove}
                    onPointerUp={pointerUp}
                    onPointerCancel={pointerCancel}
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
            {whyRow === row.row ? (
              <p className="status status-danger placement-rail__why">
                {blocked
                  ? `Can't go there. ${blocked}`
                  : `The next placement can't go there. ${previewBlocked}`}
              </p>
            ) : null}
          </div>
        );
      })}
      {canMove && placements.length > 0 ? (
        // Always drawn, so a save never shifts what is below it; it says when one is under way.
        <p className="muted placement-rail__hint">
          {busy
            ? "Saving…"
            : (carryHint ??
              "Drag a module to move it, or click it, then click its new spot. From the keyboard: Enter, then the arrow keys. Delete removes it.")}
        </p>
      ) : null}
      <p className="visually-hidden" aria-live="polite">
        {said}
      </p>
    </div>
  );
}
