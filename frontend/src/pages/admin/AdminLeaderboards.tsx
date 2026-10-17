import { useEffect, useState } from "react";
import { adminApi } from "@/lib/api";
import type { AdminLeaderboardEntry } from "@/types/admin";
import { AdminGuard } from "./AdminGuard";
import { AdminNav } from "./AdminNav";

function LeaderboardTable({ title, entries }: { title: string; entries: AdminLeaderboardEntry[] }) {
  return (
    <section className="panel">
      <p className="eyebrow">Ranking</p>
      <h2 style={{ marginTop: 0 }}>{title}</h2>
      {entries.length ? (
        <table className="data-table">
          <thead>
            <tr>
              <th>Label</th>
              <th>Count</th>
            </tr>
          </thead>
          <tbody>
            {entries.map((entry) => (
              <tr key={entry.label}>
                <td>{entry.label}</td>
                <td>{entry.count}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <p className="muted">No entries.</p>
      )}
    </section>
  );
}

export default function AdminLeaderboards() {
  const [popular, setPopular] = useState<AdminLeaderboardEntry[]>([]);
  const [trending, setTrending] = useState<AdminLeaderboardEntry[]>([]);
  const [exported, setExported] = useState<AdminLeaderboardEntry[]>([]);

  useEffect(() => {
    const fetchData = async () => {
      const [popularRes, trendingRes, exportedRes] = await Promise.all([
        adminApi.popularModules(),
        adminApi.trendingModules(14),
        adminApi.exportedCategories(),
      ]);
      setPopular(popularRes.data);
      setTrending(trendingRes.data);
      setExported(exportedRes.data);
    };
    void fetchData();
  }, []);

  return (
    <AdminGuard>
      <div className="admin-shell">
        <header className="workspace-header">
          <div>
            <p className="eyebrow">Ops</p>
            <h1>Leaderboards</h1>
            <p className="muted">Community ranking surfaces when feature flags allow.</p>
          </div>
        </header>
        <AdminNav />
        <div style={{ display: "grid", gap: "var(--space-5)" }}>
          <LeaderboardTable title="Popular modules" entries={popular} />
          <LeaderboardTable title="Trending modules (14 days)" entries={trending} />
          <LeaderboardTable title="Exported categories" entries={exported} />
        </div>
      </div>
    </AdminGuard>
  );
}
