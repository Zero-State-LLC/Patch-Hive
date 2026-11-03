/**
 * User dashboard: canonical credits/exports + optional referrals + profile.
 */
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ListSkeleton, ReadoutSkeleton } from "@/components/Skeletons";
import { accountApi, authApi, canonApi } from "@/lib/api";
import { useAuthStore } from "@/lib/store";
import type { CreditsSummary, UserExportRecord, ReferralSummary, User } from "@/types/api";

/** Only allow http(s) avatar URLs — blocks javascript:/data: DOM XSS vectors. */
function safeHttpUrl(value: string): string | null {
  try {
    const parsed = new URL(value);
    if (parsed.protocol !== "https:" && parsed.protocol !== "http:") return null;
    return parsed.toString();
  } catch {
    return null;
  }
}

export default function AccountPage() {
  const navigate = useNavigate();
  const { isAuthenticated, setUser } = useAuthStore();
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
  const [loading, setLoading] = useState(() => isAuthenticated());

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
      setUser(profileRes.data);

      try {
        const referralsRes = await accountApi.getReferrals();
        setReferrals(referralsRes.data);
      } catch {
        setReferrals(null);
      }
    };

    if (isAuthenticated()) {
      setLoading(true);
      loadDashboard()
        .catch(() => {
          /* keep empty dashboard on failure */
        })
        .finally(() => setLoading(false));
    }
  }, [isAuthenticated, setUser]);

  const handleSaveProfile = async () => {
    setSaving(true);
    try {
      const res = await authApi.updateProfile({
        display_name: displayName,
        avatar_url: avatarUrl || undefined,
      });
      setProfile(res.data);
      setUser(res.data);
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
          <h1 id="account-title">Credits & profile</h1>
          <p className="muted">
            PatchHive is free to explore. You only pay when you export something you want to keep.
            Credits and export debits use the canonical ledger (<code>/api/canon/*</code>).
          </p>
        </div>
      </header>

      <div className="ops-page account-grid">
        <section className="ops-section" aria-labelledby="credits-heading">
          <h2 id="credits-heading">Credits</h2>
          <dl className="readout account-balance">
            <div>
              <dt>Canonical balance</dt>
              <dd>
                {loading ? (
                  <ReadoutSkeleton label="Loading balance…" />
                ) : credits ? (
                  credits.balance
                ) : (
                  "unknown"
                )}
              </dd>
            </div>
          </dl>
          <h3>Ledger history</h3>
          {loading ? (
            <ListSkeleton label="Loading ledger history…" rows={3} />
          ) : credits?.entries.length ? (
            <div className="ops-table-wrap">
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
                      <td className="muted">{entry.description || "unknown"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="muted">No canonical credit history yet.</p>
          )}
        </section>

        <section className="ops-section" aria-labelledby="exports-heading">
          <h2 id="exports-heading">Exports</h2>
          {tokenMessage ? (
            <p className="status status-success" role="status">
              {tokenMessage}
            </p>
          ) : null}
          {loading ? (
            <ListSkeleton label="Loading exports…" rows={3} />
          ) : exportRows.length ? (
            <div className="ops-table-wrap">
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
                      <td className="muted ops-id">{record.run_id}</td>
                      <td>{record.status || "unknown"}</td>
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

        <section className="ops-section" aria-labelledby="referrals-heading">
          <h2 id="referrals-heading">Referrals</h2>
          {referrals ? (
            <>
              <p className="muted">
                You’ll receive free credits if your friend makes their first purchase.
              </p>
              <div className="toolbar ops-referral">
                <label className="field">
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
              <dl className="readout">
                <div>
                  <dt>Pending</dt>
                  <dd>{referrals.pending_count ?? "unknown"}</dd>
                </div>
                <div>
                  <dt>Earned</dt>
                  <dd>{referrals.earned_count ?? "unknown"}</dd>
                </div>
              </dl>
            </>
          ) : (
            <p className="muted">
              Referrals are feature-flagged off in the default MVP (
              <code>ENABLE_REFERRALS=false</code>).
            </p>
          )}
        </section>

        <section className="ops-section ops-section--form" aria-labelledby="profile-heading">
          <h2 id="profile-heading">Profile</h2>
          <div className="ops-form">
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
                className="ops-avatar"
                src={safeAvatarUrl}
                alt="Avatar preview"
                referrerPolicy="no-referrer"
                width={96}
                height={96}
              />
            ) : null}
            <button
              type="button"
              className="button button-primary"
              onClick={() => void handleSaveProfile()}
              disabled={saving}
            >
              {saving ? "Saving…" : "Save profile"}
            </button>
          </div>
          {profile ? (
            <p className="muted">
              Signed in as <strong>{profile.username}</strong>
            </p>
          ) : null}
        </section>
      </div>
    </section>
  );
}
