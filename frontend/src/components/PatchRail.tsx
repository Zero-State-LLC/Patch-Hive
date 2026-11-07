/**
 * PatchRail — a patch's cables drawn over the rig's rail, plugged into the modules where they sit.
 * Connections name catalog module ids (RackModule.module_id); there is no jack position data,
 * so each cable plugs in at the top centre of its faceplate, under the module name. The cable
 * table is the readable form.
 */
import { useLayoutEffect, useMemo, useRef, useState } from "react";
import type { CSSProperties } from "react";
import RigRail, { type RailRack } from "@/components/RigRail";
import { rigRowWidths } from "@/lib/rigRows";
import type { Connection, Patch, RackModule } from "@/types/api";

/** What the rail draws from a patch: its cables, named and keyed by the patch. */
export type RailPatch = Pick<Patch, "id" | "name" | "connections">;

type Point = { x: number; y: number };

interface Endpoint {
  placement: RackModule | null;
  ambiguous: boolean;
}

interface CableRow {
  index: number;
  connection: Connection;
  from: Endpoint;
  to: Endpoint;
}

/** Below the 12px top rail and the module name, where a jack row would sit. */
const PLUG_Y = 34;
/** Each further cable on the same faceplate plugs in this far below the last. */
const PLUG_STEP = 10;

const SIGNALS = new Set(["audio", "cv", "gate", "trigger", "clock"]);

function signalOf(cableType: string): string {
  const type = (cableType || "").toLowerCase();
  return SIGNALS.has(type) ? type : "unknown";
}

/** A cable hangs between two plugs; the sag grows with the span. */
function cablePath(a: Point, b: Point): string {
  const span = Math.abs(b.x - a.x);
  const sag = Math.min(90, 34 + span * 0.2);
  if (span < 1) {
    // Both ends on one faceplate (feedback): a small loop below the jacks.
    return `M ${a.x} ${a.y} C ${a.x - 22} ${a.y + sag}, ${b.x + 22} ${b.y + sag}, ${b.x} ${b.y}`;
  }
  return `M ${a.x} ${a.y} C ${a.x} ${a.y + sag}, ${b.x} ${b.y + sag}, ${b.x} ${b.y}`;
}

/** An end that is not on this rig's rail: a short lead hanging loose from the plugged end. */
function stubPath(a: Point): string {
  return `M ${a.x} ${a.y} C ${a.x} ${a.y + 30}, ${a.x + 18} ${a.y + 42}, ${a.x + 30} ${a.y + 46}`;
}

function ModuleCell({
  id,
  placement,
  port,
}: {
  id: number;
  placement: RackModule | null;
  port: string;
}) {
  const m = placement?.module;
  return (
    <td>
      {m ? (
        <>
          <span className="patch-rail__brand">{m.brand} </span>
          {m.name}
        </>
      ) : (
        `Module #${id}`
      )}
      <span className="patch-rail__port">{port}</span>
    </td>
  );
}

export default function PatchRail({
  rack,
  patch,
  table = true,
}: {
  rack: RailRack;
  patch: RailPatch;
  /** The cable table under the rail; off where the rail is shown, not worked (the home page). */
  table?: boolean;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ width: 0, height: 0 });
  const [plugs, setPlugs] = useState<Map<number, Point>>(new Map());
  const [selected, setSelected] = useState<number | null>(null);
  // A picked cable belongs to its patch: switching patches clears it, whoever renders this.
  const [selectedFor, setSelectedFor] = useState(patch.id);
  if (selectedFor !== patch.id) {
    setSelectedFor(patch.id);
    setSelected(null);
  }

  const rows = useMemo(() => rigRowWidths(rack.case, rack.modules), [rack.case, rack.modules]);

  // First placement of each catalog module, by row then start HP; note modules placed twice.
  const { byModule, duplicated } = useMemo(() => {
    const placed = rack.modules
      .filter((m) => (m.module?.hp ?? 0) > 0)
      .slice()
      .sort((a, b) => a.row_index - b.row_index || a.start_hp - b.start_hp);
    const first = new Map<number, RackModule>();
    const twice = new Set<number>();
    for (const m of placed) {
      if (first.has(m.module_id)) twice.add(m.module_id);
      else first.set(m.module_id, m);
    }
    return { byModule: first, duplicated: twice };
  }, [rack.modules]);

  const cables = useMemo<CableRow[]>(
    () =>
      patch.connections.map((connection, index) => ({
        index,
        connection,
        from: {
          placement: byModule.get(connection.from_module_id) ?? null,
          ambiguous: duplicated.has(connection.from_module_id),
        },
        to: {
          placement: byModule.get(connection.to_module_id) ?? null,
          ambiguous: duplicated.has(connection.to_module_id),
        },
      })),
    [patch.connections, byModule, duplicated],
  );

  // Measure each row's track so plugs land on the faceplates as laid out.
  useLayoutEffect(() => {
    const container = containerRef.current;
    if (!container || rows.length === 0) return;

    const measure = () => {
      const box = container.getBoundingClientRect();
      const tracks = Array.from(
        container.querySelectorAll<HTMLElement>(".rack-row-map__track"),
      ).map((el) => el.getBoundingClientRect());
      const next = new Map<number, Point>();
      for (const placement of byModule.values()) {
        const track = tracks[placement.row_index];
        const capacity = rows[placement.row_index];
        const hp = placement.module?.hp ?? 0;
        if (!track || !capacity) continue;
        next.set(placement.id, {
          x: track.left - box.left + ((placement.start_hp + hp / 2) / capacity) * track.width,
          y: track.top - box.top + PLUG_Y,
        });
      }
      setPlugs(next);
      setSize({ width: box.width, height: box.height });
    };

    measure();
    if (typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(measure);
    observer.observe(container);
    return () => observer.disconnect();
  }, [byModule, rows]);

  // Each cable's two plugs; a faceplate with several cables stacks its jacks downward.
  const leads = useMemo(() => {
    const used = new Map<number, number>();
    const plugAt = (placement: RackModule | null): Point | undefined => {
      const base = placement ? plugs.get(placement.id) : undefined;
      if (!base || !placement) return undefined;
      const n = used.get(placement.id) ?? 0;
      used.set(placement.id, n + 1);
      return { x: base.x, y: base.y + n * PLUG_STEP };
    };
    return cables
      .map((cable) => ({ cable, a: plugAt(cable.from.placement), b: plugAt(cable.to.placement) }))
      .filter((lead) => lead.a || lead.b);
  }, [cables, plugs]);

  const drawn = cables.filter((c) => c.from.placement || c.to.placement).length;
  const summary = `${patch.name}: ${patch.connections.length} cable${
    patch.connections.length === 1 ? "" : "s"
  }, ${drawn} drawn on the rail`;

  return (
    <div className="patch-rail">
      {rows.length > 0 ? (
        <div className="patch-rail__stage" ref={containerRef}>
          <RigRail rack={rack} />
          <svg
            className="patch-rail__cables"
            viewBox={`0 0 ${size.width || 1} ${size.height || 1}`}
            aria-hidden="true"
            key={patch.id}
          >
            {leads.map(({ cable, a, b }) => {
              const signal = signalOf(cable.connection.cable_type);
              const d = a && b ? cablePath(a, b) : stubPath((a ?? b) as Point);
              const solid = signal === "audio" || signal === "unknown";
              const state =
                selected === null ? "" : selected === cable.index ? " is-selected" : " is-dimmed";
              return (
                <g
                  key={cable.index}
                  className={`patch-cable patch-cable--${signal}${state}`}
                  style={{ "--i": cable.index } as CSSProperties}
                >
                  <path
                    className={`patch-cable__lead${solid ? " patch-cable__lead--solid" : ""}`}
                    d={d}
                    pathLength={solid ? 1 : undefined}
                  />
                  {a ? (
                    <circle
                      className="patch-cable__plug patch-cable__plug--out"
                      cx={a.x}
                      cy={a.y}
                      r={4}
                    />
                  ) : null}
                  {b ? <circle className="patch-cable__plug" cx={b.x} cy={b.y} r={4} /> : null}
                </g>
              );
            })}
          </svg>
        </div>
      ) : (
        <p className="muted">
          {rack.case
            ? "This rig\u2019s case does not state HP per row, so its rail cannot be drawn."
            : "This rig has no Case and no placed modules yet, so its rail cannot be drawn."}{" "}
          The cables are listed below.
        </p>
      )}

      {!table ? null : cables.length === 0 ? (
        <p className="muted">This patch has no cables yet.</p>
      ) : (
        <div className="patch-rail__table">
          {rows.length > 0 ? (
            <p className="patch-rail__key muted">Filled plugs are outputs; rings are inputs.</p>
          ) : null}
          <table className="data-table">
            <caption className="visually-hidden">{summary}</caption>
            <thead>
              <tr>
                <th scope="col">Cable</th>
                <th scope="col">From</th>
                <th scope="col">To</th>
                <th scope="col" className="patch-rail__signal">
                  Signal
                </th>
              </tr>
            </thead>
            <tbody>
              {cables.map((cable) => {
                const signal = signalOf(cable.connection.cable_type);
                const notes = [
                  !cable.from.placement || !cable.to.placement ? "an end is not on this rig" : "",
                  cable.from.ambiguous || cable.to.ambiguous
                    ? "module placed twice; drawn at its first position"
                    : "",
                ].filter(Boolean);
                return (
                  <tr key={cable.index} className={selected === cable.index ? "is-selected" : ""}>
                    <th scope="row">
                      <button
                        type="button"
                        className="patch-rail__pick"
                        aria-pressed={selected === cable.index}
                        onClick={() => setSelected((s) => (s === cable.index ? null : cable.index))}
                      >
                        <span className={`cable-swatch cable-${signal}`} aria-hidden="true" />
                        Cable {cable.index + 1}
                      </button>
                      {notes.length ? (
                        <span className="patch-rail__note">{notes.join(", ")}</span>
                      ) : null}
                    </th>
                    <ModuleCell
                      id={cable.connection.from_module_id}
                      placement={cable.from.placement}
                      port={cable.connection.from_port}
                    />
                    <ModuleCell
                      id={cable.connection.to_module_id}
                      placement={cable.to.placement}
                      port={cable.connection.to_port}
                    />
                    <td className="patch-rail__signal">
                      {signal === "unknown" ? cable.connection.cable_type || "unknown" : signal}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
