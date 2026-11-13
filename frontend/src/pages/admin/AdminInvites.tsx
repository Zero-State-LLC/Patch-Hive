import { useCallback, useEffect, useState } from "react";
import { adminApi, type AdminInvite } from "@/lib/api";
import { AdminGuard } from "./AdminGuard";
import { AdminNav } from "./AdminNav";

// Three Patch Books at the current price.
const DEFAULT_CREDITS = 9;

export default function AdminInvites() {
  const [invites, setInvites] = useState<AdminInvite[]>([]);
  const [credits, setCredits] = useState(DEFAULT_CREDITS);
  const [note, setNote] = useState("");
  const [code, setCode] = useState("");
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      const res = await adminApi.listInvites();
      setInvites(res.data.invites);
    } catch {
      setError("Could not load invites.");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const create = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setCode("");
    try {
      const res = await adminApi.createInvite(credits, note);
      setCode(res.data.code);
      setNote("");
      await load();
    } catch {
      setError("Could not create the invite.");
    }
  };

  return (
    <AdminGuard>
      <div className="admin-shell">
        <header className="workspace-header">
          <div>
            <h1>Invites</h1>
            <p className="muted">One-use codes for the closed beta. Each adds test credits.</p>
          </div>
        </header>
        <AdminNav />
        {error ? (
          <p className="status status-danger" role="alert">
            {error}
          </p>
        ) : null}
        {code ? (
          <p className="status status-success" role="status">
            New invite code: <code>{code}</code>. Copy it now, because it won&apos;t be shown again.
          </p>
        ) : null}
        <section className="ops-section">
          <h2>New invite</h2>
          <form className="toolbar ops-toolbar" onSubmit={(e) => void create(e)}>
            <label className="field">
              Credits
              <input
                type="number"
                min={1}
                max={1000}
                value={credits}
                onChange={(e) => setCredits(Number(e.target.value))}
                required
              />
            </label>
            <label className="field ops-grow">
              Who it&apos;s for
              <input value={note} maxLength={200} onChange={(e) => setNote(e.target.value)} />
            </label>
            <button type="submit" className="button button-primary">
              Create invite
            </button>
          </form>
        </section>
        <section className="ops-section">
          <h2>Invites</h2>
          {invites.length ? (
            <ul>
              {invites.map((invite) => (
                <li key={invite.id}>
                  {invite.note || `Invite ${invite.id}`}: {invite.credits} credits,{" "}
                  {invite.redeemed_at ? "used" : "not used yet"}
                </li>
              ))}
            </ul>
          ) : (
            <p className="muted">No invites yet.</p>
          )}
        </section>
      </div>
    </AdminGuard>
  );
}
