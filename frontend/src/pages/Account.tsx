/**
 * User dashboard: canonical credits/exports + optional referrals + profile.
 */
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { accountApi, authApi, canonApi } from "@/lib/api";
import { useAuthStore } from "@/lib/store";
import type { CreditsSummary, UserExportRecord, ReferralSummary, User } from "@/types/api";

/** Only allow http(s) avatar URLs — blocks javascript:/data: DOM XSS vectors. */
function safeHttpUrl(value: string): string | null {
  try {
    const parsed = new URL(value);
    if (parsed.protocol !== 'https:' && parsed.protocol !== 'http:') return null;
    return parsed.toString();
  } catch {
    return null;
  }
}

export default function AccountPage() {
  const navigate = useNavigate();
  const { isAuthenticated, setAuth } = useAuthStore();
  const [credits, setCredits] = useState<CreditsSummary | null>(null);
  const [exports, setExports] = useState<UserExportRecord[]>([]);
  const [referrals, setReferrals] = useState<ReferralSummary | null>(null);
  const [profile, setProfile] = useState<User | null>(null);
  const [displayName, setDisplayName] = useState("");
  const [avatarUrl, setAvatarUrl] = useState("");
  const [saving, setSaving] = useState(false);
  const [copyStatus, setCopyStatus] = useState("");
  const [tokenBusy, setTokenBusy] = useState<string | null>(null);
  const [tokenMessage, setTokenMessage] = useState("");

  const safeAvatarUrl = useMemo(() => safeHttpUrl(avatarUrl.trim()), [avatarUrl]);

  useEffect(() => {
    if (!isAuthenticated()) {
      navigate("/login");
    }
  }, [isAuthenticated, navigate]);

  useEffect(() => {
    const loadDashboard = async () => {
      const [creditsRes, exportsRes, profileRes] = await Promise.all([
        accountApi.getCredits(),
        accountApi.getExports(),
        authApi.getMe(),
      ]);
      setCredits(creditsRes.data);
      setExports(exportsRes.data as UserExportRecord[]);
      setProfile(profileRes.data);
      setDisplayName(profileRes.data.display_name || profileRes.data.username);
      setAvatarUrl(profileRes.data.avatar_url || "");
      setAuth(profileRes.data, localStorage.getItem("auth_token") || "");

      try {
        const referralsRes = await accountApi.getReferrals();
        setReferrals(referralsRes.data);
      } catch {
        setReferrals(null);
      }
    };

    if (isAuthenticated()) {
      loadDashboard().catch(() => {
        /* keep empty dashboard on failure */
      });
    }
  }, [isAuthenticated, setAuth]);

  const handleSaveProfile = async () => {
    setSaving(true);
    try {
      const res = await authApi.updateProfile({
        display_name: displayName,
        avatar_url: avatarUrl || undefined,
      });
      setProfile(res.data);
      setAuth(res.data, localStorage.getItem("auth_token") || "");
    } finally {
      setSaving(false);
    }
  };

  const exportRows = useMemo(() => {
    return exports.map((record) => ({
      ...record,
      label: record.source === "canon" ? "Canonical export" : record.export_type,
      canRequestToken: Boolean(record.unlocked && record.source === "canon"),
    }));
  }, [exports]);

  const handleDownloadToken = async (exportId: string) => {
    setTokenBusy(exportId);
    setTokenMessage("");
    try {
      const res = await canonApi.createDownloadToken(exportId, 300);
      setTokenMessage(`Download token issued for ${exportId} (TTL ${res.data.ttl_seconds}s).`);
    } catch (error: unknown) {
      const apiError = error as { response?: { data?: { detail?: string } } };
      setTokenMessage(apiError.response?.data?.detail || "Could not issue download token.");
    } finally {
      setTokenBusy(null);
    }
  };

  const handleCopy = async () => {
    if (!referrals?.referral_link) return;
    await navigator.clipboard.writeText(referrals.referral_link);
    setCopyStatus("Copied");
    setTimeout(() => setCopyStatus(""), 2000);
  };

  return (
    <section aria-labelledby="account-title">
      <header className="workspace-header">
        <div>
          <p className="eyebrow">Account</p>
          <h1 id="account-title">Credits & profile</h1>
          <p className="muted">
            PatchHive is free to explore. You only pay when you export something you want to keep.
            Credits and export debits use the canonical ledger (<code>/api/canon/*</code>).
          </p>
        </div>
      </header>

      <div style={{ display: "grid", gap: "var(--space-5)" }}>
        <section className="panel" aria-labelledby="credits-heading">
          <p className="eyebrow">Ledger</p>
          <h2 id="credits-heading" style={{ marginTop: 0 }}>
            Credits
          </h2>
          <div className="stat-row">
            <div className="stat-block">
              <p className="muted" style={{ margin: 0 }}>
                Canonical balance
              </p>
              <h3>{credits ? credits.balance : "—"}</h3>
            </div>
          </div>
          <p
            className="muted"
            style={{ marginTop: "var(--space-4)", marginBottom: "var(--space-2)" }}
          >
            Ledger history
          </p>
          {credits?.entries.length ? (
            <div style={{ overflowX: "auto" }}>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Type</th>
                    <th>Amount</th>
                    <th>Date</th>
                    <th>Note</th>
                  </tr>
                </thead>
                <tbody>
                  {credits.entries.map((entry) => (
                    <tr key={String(entry.id)}>
                      <td>{entry.entry_type}</td>
                      <td>{entry.amount}</td>
                      <td>{new Date(entry.created_at).toLocaleString()}</td>
                      <td className="muted">{entry.description || "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="muted">No canonical credit history yet.</p>
          )}
        </section>

        <section className="panel" aria-labelledby="exports-heading">
          <p className="eyebrow">Downloads</p>
          <h2 id="exports-heading" style={{ marginTop: 0 }}>
            Exports
          </h2>
          {tokenMessage ? (
            <p className="status status-success" role="status">
              {tokenMessage}
            </p>
          ) : null}
          {exportRows.length ? (
            <div style={{ overflowX: "auto" }}>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Type</th>
                    <th>Run ID</th>
                    <th>Status</th>
                    <th>Date</th>
                    <th>Download</th>
                  </tr>
                </thead>
                <tbody>
                  {exportRows.map((record) => (
                    <tr key={String(record.id)}>
                      <td>{record.label}</td>
                      <td className="muted">{record.run_id}</td>
                      <td>{record.status || "—"}</td>
                      <td>{new Date(record.created_at).toLocaleString()}</td>
                      <td>
                        {record.canRequestToken ? (
                          <button
                            type="button"
                            className="button button-secondary"
                            onClick={() => handleDownloadToken(String(record.id))}
                            disabled={tokenBusy === String(record.id)}
                          >
                            {tokenBusy === String(record.id) ? "Issuing…" : "Issue token"}
                          </button>
                        ) : (
                          <span className="muted">{record.unlocked ? "Ready" : "Locked"}</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="muted">No canonical exports yet.</p>
          )}
        </section>

        <section className="panel" aria-labelledby="referrals-heading">
          <p className="eyebrow">Growth</p>
          <h2 id="referrals-heading" style={{ marginTop: 0 }}>
            Referrals
          </h2>
          {referrals ? (
            <>
              <p className="muted">
                You’ll receive free credits if your friend makes their first purchase.
              </p>
              <div className="toolbar" style={{ marginTop: "var(--space-3)" }}>
                <label className="field" style={{ flex: 1, minWidth: "12rem" }}>
                  Referral link
                  <input type="text" value={referrals.referral_link || ""} readOnly />
                </label>
                <button
                  type="button"
                  className="button button-primary"
                  onClick={() => void handleCopy()}
                >
                  Invite a friend
                </button>
                {copyStatus ? (
                  <span className="status status-success" role="status">
                    {copyStatus}
                  </span>
                ) : null}
              </div>
              <div className="stat-row" style={{ marginTop: "var(--space-4)" }}>
                <div className="stat-block">
                  <p className="muted" style={{ margin: 0 }}>
                    Pending
                  </p>
                  <h3>{referrals.pending_count ?? "—"}</h3>
                </div>
                <div className="stat-block">
                  <p className="muted" style={{ margin: 0 }}>
                    Earned
                  </p>
                  <h3>{referrals.earned_count ?? "—"}</h3>
                </div>
              </div>
            </>
          ) : (
            <p className="muted">
              Referrals are feature-flagged off in the default MVP (
              <code>ENABLE_LEGACY_REFERRALS=false</code>).
            </p>
          )}
        </section>

        <section className="panel" aria-labelledby="profile-heading">
          <p className="eyebrow">Identity</p>
          <h2 id="profile-heading" style={{ marginTop: 0 }}>
            Profile
          </h2>
          <div style={{ display: "grid", gap: "var(--space-4)", maxWidth: "28rem" }}>
            <label className="field">
              Display name
              <input
                type="text"
                value={displayName}
                onChange={(event) => setDisplayName(event.target.value)}
              />
            </label>
            <label className="field">
              Avatar URL
              <input
                type="url"
                value={avatarUrl}
                onChange={(event) => setAvatarUrl(event.target.value)}
                placeholder="https://"
              />
            </label>
            {safeAvatarUrl ? (
              <img
                src={safeAvatarUrl}
                alt="Avatar preview"
                referrerPolicy="no-referrer"
                width={96}
                height={96}
                style={{
                  width: "96px",
                  height: "96px",
                  borderRadius: "50%",
                  border: "1px solid var(--border)",
                  objectFit: "cover",
                }}
              />
            ) : null}
            <button
              type="button"
              className="button button-primary"
              onClick={() => void handleSaveProfile()}
              disabled={saving}
              style={{ justifySelf: "start" }}
            >
              {saving ? "Saving…" : "Save profile"}
            </button>
          </div>
          {profile ? (
            <p className="muted" style={{ marginTop: "var(--space-4)", marginBottom: 0 }}>
              Signed in as <strong>{profile.username}</strong>
            </p>
          ) : null}
        </section>
      </div>
    </section>
  );
}
