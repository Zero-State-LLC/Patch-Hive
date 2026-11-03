/**
 * RigRail — read-only drawing of a rig's placed modules on its case rows, to HP scale.
 * Draws only when the case states its HP per row; nothing is guessed.
 */
import type { CSSProperties } from "react";
import type { Rack } from "@/types/api";

export default function RigRail({ rack }: { rack: Rack }) {
  const rows = rack.case?.hp_per_row ?? [];
  if (rows.length === 0) return null;

  const placed = rack.modules.filter((m) => (m.module?.hp ?? 0) > 0);
  const summary = `${rack.name}: ${placed.length} module${placed.length === 1 ? "" : "s"} on ${rows.length} row${rows.length === 1 ? "" : "s"} of ${rows.join(" and ")} HP`;

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
            <div className="usage-bar">
              <div
                className={`usage-bar__fill usage-bar__fill--${tone}`}
                style={{ "--fill": fill } as CSSProperties}
              />
            </div>
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
              <span>
                {used}/{capacity} HP
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );
}
