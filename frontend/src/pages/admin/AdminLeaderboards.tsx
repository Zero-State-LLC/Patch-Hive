import { useEffect, useState } from "react";
import LoadFailure from "@/components/LoadFailure";
import { ListSkeleton } from "@/components/Skeletons";
import { adminApi } from "@/lib/api";
import type { AdminLeaderboardEntry } from "@/types/admin";
import { AdminGuard } from "./AdminGuard";
import { AdminNav } from "./AdminNav";

function LeaderboardTable({
  title,
  board,
  onRetry,
}: {
  title: string;
  board: Board;
  onRetry: () => void;
}) {
  const { entries, error } = board;
  return (
    <section className="ops-section">
      <h2>{title}</h2>
      {error ? (
        <LoadFailure what={title} error={error} onRetry={onRetry} />
      ) : entries.length ? (
        <div className="ops-table-wrap">
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
        </div>
      ) : (
        <p className="muted">No entries.</p>
      )}
    </section>
  );
}

interface Board {
  entries: AdminLeaderboardEntry[];
  error: unknown;
}

const NOT_LOADED: Board = { entries: [], error: null };

export default function AdminLeaderboards() {
  const [boards, setBoards] = useState<Board[] | null>(null);
  const [attempt, setAttempt] = useState(0);

  // Each board loads on its own, so one that is switched off or fails leaves the others.
  useEffect(() => {
    let current = true;
    setBoards(null);
    void Promise.allSettled([
      adminApi.popularModules(),
      adminApi.trendingModules(14),
      adminApi.exportedCategories(),
    ]).then((results) => {
      if (!current) return;
      setBoards(
        results.map((r) =>
          r.status === "fulfilled"
            ? { entries: r.value.data, error: null }
            : { entries: [], error: r.reason },
        ),
      );
    });
    return () => {
      current = false;
    };
  }, [attempt]);

  const retry = () => setAttempt((n) => n + 1);
  const titles = ["Popular modules", "Trending modules (14 days)", "Exported categories"];

  return (
    <AdminGuard>
      <div className="admin-shell">
        <header className="workspace-header">
          <div>
            <h1>Leaderboards</h1>
            <p className="muted">Community ranking surfaces when feature flags allow.</p>
          </div>
        </header>
        <AdminNav />
        <div className="ops-stack">
          {titles.map((title, i) =>
            boards ? (
              <LeaderboardTable
                key={title}
                title={title}
                board={boards[i] ?? NOT_LOADED}
                onRetry={retry}
              />
            ) : (
              <section key={title} className="ops-section">
                <h2>{title}</h2>
                <ListSkeleton label={`Loading ${title.toLowerCase()}…`} rows={3} />
              </section>
            ),
          )}
        </div>
      </div>
    </AdminGuard>
  );
}
