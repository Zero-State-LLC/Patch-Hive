/**
 * Public leaderboards for modules.
 */
import { useEffect, useState } from "react";
import { leaderboardsApi } from "@/legacy/apiClients";
import type { LeaderboardEntry } from "@/types/api";

const tableStyle: React.CSSProperties = {
  width: "100%",
  borderCollapse: "collapse",
  marginTop: "1rem",
};

export default function LeaderboardsModulesPage() {
  const [mode, setMode] = useState<"popular" | "trending">("popular");
  const [entries, setEntries] = useState<LeaderboardEntry[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      const res =
        mode === "popular"
          ? await leaderboardsApi.getPopularModules()
          : await leaderboardsApi.getTrendingModules(30);
      setEntries(res.data);
      setLoading(false);
    };
    load();
  }, [mode]);

  return (
    <div style={{ maxWidth: "900px", margin: "0 auto" }}>
      <h2>Module Leaderboards</h2>
      <p style={{ color: "var(--text-muted)" }}>
        Aggregate-only counts of module appearances across public rigs.
      </p>
      <div style={{ display: "flex", gap: "1rem", marginTop: "1rem" }}>
        <button
          onClick={() => setMode("popular")}
          style={{
            background: mode === "popular" ? "var(--success)" : "var(--surface-raised)",
            color: mode === "popular" ? "var(--action-contrast)" : "var(--text-secondary)",
            border: "1px solid var(--border)",
            padding: "0.5rem 1rem",
            borderRadius: "4px",
            cursor: "pointer",
            fontWeight: "bold",
          }}
        >
          Popular
        </button>
        <button
          onClick={() => setMode("trending")}
          style={{
            background: mode === "trending" ? "var(--success)" : "var(--surface-raised)",
            color: mode === "trending" ? "var(--action-contrast)" : "var(--text-secondary)",
            border: "1px solid var(--border)",
            padding: "0.5rem 1rem",
            borderRadius: "4px",
            cursor: "pointer",
            fontWeight: "bold",
          }}
        >
          Trending (30d)
        </button>
      </div>

      {loading ? (
        <p style={{ color: "var(--text-muted)", marginTop: "1rem" }}>Loading…</p>
      ) : (
        <table style={tableStyle}>
          <thead style={{ textAlign: "left", color: "var(--text-muted)" }}>
            <tr>
              <th style={{ padding: "0.5rem" }}>Rank</th>
              <th style={{ padding: "0.5rem" }}>Module</th>
              <th style={{ padding: "0.5rem" }}>Manufacturer</th>
              <th style={{ padding: "0.5rem" }}>Count</th>
            </tr>
          </thead>
          <tbody>
            {entries.map((entry) => (
              <tr
                key={`${entry.rank}-${entry.module_name}`}
                style={{ borderTop: "1px solid var(--surface-raised)" }}
              >
                <td style={{ padding: "0.5rem" }}>{entry.rank}</td>
                <td style={{ padding: "0.5rem" }}>{entry.module_name}</td>
                <td style={{ padding: "0.5rem", color: "var(--text-muted)" }}>
                  {entry.manufacturer}
                </td>
                <td style={{ padding: "0.5rem" }}>{entry.count}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
