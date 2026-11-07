/**
 * RigRail — read-only drawing of a rig's placed modules on its case rows, to HP scale.
 * Draws a case's rows only when it states its HP per row; nothing is guessed. A rig with no
 * Case (spec 009) is drawn as wide as its modules reach, with no capacity to fill.
 */
import type { CSSProperties } from "react";
import { rigRowWidths } from "@/lib/rigRows";
import type { Rack } from "@/types/api";

/** What the rail draws from a rig: its name, its case's rows and the modules placed on them. */
export type RailRack = Pick<Rack, "name" | "case" | "modules">;

export default function RigRail({ rack }: { rack: RailRack }) {
  const rows = rigRowWidths(rack.case, rack.modules);
  if (rows.length === 0) return null;

  const placed = rack.modules.filter((m) => (m.module?.hp ?? 0) > 0);
  const counted = `${rack.name}: ${placed.length} module${placed.length === 1 ? "" : "s"} on ${rows.length} row${rows.length === 1 ? "" : "s"}`;
  const summary = rack.case
    ? `${counted} of ${rows.join(" and ")} HP`
    : `${counted}, no Case named`;

  return (
    <div className="rig-rail" role="img" aria-label={summary}>
      {rows.map((capacity, rowIndex) => {
        const inRow = placed.filter((m) => m.row_index === rowIndex);
        const used = inRow.reduce((sum, m) => sum + (m.module?.hp ?? 0), 0);
        const fill = capacity > 0 ? Math.min(1, used / capacity) : 0;
        const tone =
          fill >= 1 ? "danger" : fill >= 0.85 ? "warning" : fill > 0 ? "success" : "neutral";
        return (
          <div key={rowIndex} className="rack-row-map" aria-hidden="true">
            {rack.case ? (
              <div className="usage-bar">
                <div
                  className={`usage-bar__fill usage-bar__fill--${tone}`}
                  style={{ "--fill": fill } as CSSProperties}
                />
              </div>
            ) : null}
            <div className="rack-row-map__track" style={{ "--row-hp": capacity } as CSSProperties}>
              {inRow.map((m, i) => {
                const hp = m.module?.hp ?? 0;
                const powerKnown = m.module?.power_12v_ma != null;
                return (
                  <div
                    key={m.id}
                    className={`rack-row-map__block${powerKnown ? "" : " rack-row-map__block--unknown-power"}`}
                    style={
                      {
                        left: `${(m.start_hp / capacity) * 100}%`,
                        width: `${(hp / capacity) * 100}%`,
                        "--i": i,
                      } as CSSProperties
                    }
                    title={`${m.module?.brand ?? ""} ${m.module?.name ?? ""}, ${hp} HP at ${m.start_hp}`}
                  >
                    <span className="rack-row-map__block-label">{m.module?.name}</span>
                    <span className="rack-row-map__block-hp">{hp}HP</span>
                  </div>
                );
              })}
            </div>
            <div className="rack-row-map__scale">
              <span>Row {rowIndex}</span>
              <span>{rack.case ? `${used}/${capacity} HP` : `${used} HP`}</span>
            </div>
          </div>
        );
      })}
    </div>
  );
}
