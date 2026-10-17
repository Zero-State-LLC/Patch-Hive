/**
 * Auth gate — PatchHive Cyber Hive / Zero State.
 * Sign in or create an account with accessible, token-aligned UI.
 */
import { useId, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { authApi } from "@/lib/api";
import { useAuthStore } from "@/lib/store";

type AuthMode = "signin" | "register";

export default function LoginPage() {
  const navigate = useNavigate();
  const setAuth = useAuthStore((state) => state.setAuth);
  const formId = useId();

  const [mode, setMode] = useState<AuthMode>("signin");
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setSubmitting(true);

    try {
      if (mode === "register") {
        await authApi.register({ username, email, password });
      }
      const res = await authApi.login({ username, password });
      setAuth(res.data.user, res.data.access_token);
      navigate("/racks");
    } catch (err: unknown) {
      const apiError = err as { response?: { data?: { detail?: string | { msg?: string }[] } } };
      const detail = apiError.response?.data?.detail;
      if (typeof detail === "string") {
        setError(detail);
      } else if (Array.isArray(detail)) {
        setError(detail.map((d) => d.msg || "Validation error").join(" · "));
      } else {
        setError(mode === "register" ? "Could not create account" : "Sign in failed");
      }
    } finally {
      setSubmitting(false);
    }
  };

  // Must match scripts/seed_golden_demo.py (Admin/Admin is NOT a real account).
  const fillDemoUser = () => {
    setMode("signin");
    setUsername("golden_demo");
    setPassword("demo-pass");
    setError("");
  };

  const fillDemoAdmin = () => {
    setMode("signin");
    setUsername("admin_demo");
    setPassword("admin-pass");
    setError("");
  };

  return (
    <section className="auth-page" aria-labelledby={`${formId}-title`}>
      <div className="auth-shell">
        <aside className="auth-brand panel" aria-label="Product identity">
          <div className="auth-brand-grid" aria-hidden="true" />
          <div className="auth-brand-photo" aria-hidden="true" />
          <p className="home-brand" style={{ fontSize: "clamp(2rem, 5vw, 3rem)" }}>
            PatchHive
          </p>
          <h1 id={`${formId}-title`} className="auth-brand-title">
            Enter the hive
          </h1>
          <p className="auth-brand-lede">
            Confirm modular rigs, generate hardware-constrained patches, and export provenance-bound
            PatchBooks — without inventing gear or running DSP.
          </p>
          <ul className="auth-brand-list">
            <li>Immutable rig revisions</li>
            <li>Deterministic generation seeds</li>
            <li>Credit-gated canonical exports</li>
            <li>Style Studio design recipes</li>
          </ul>
          <p className="auth-brand-foot muted">
            A Zero State product · designed and engineered for signal clarity
          </p>
        </aside>

        <div className="auth-card panel">
          <div className="auth-card-head">
            <div className="auth-mark" aria-hidden="true" />
            <div>
              <p className="eyebrow">Access</p>
              <h2 className="auth-card-title">
                {mode === "signin" ? "Sign in" : "Create account"}
              </h2>
            </div>
          </div>

          <div className="auth-tabs" role="tablist" aria-label="Authentication mode">
            <button
              type="button"
              role="tab"
              className="auth-tab"
              aria-selected={mode === "signin"}
              onClick={() => {
                setMode("signin");
                setError("");
              }}
            >
              Sign in
            </button>
            <button
              type="button"
              role="tab"
              className="auth-tab"
              aria-selected={mode === "register"}
              onClick={() => {
                setMode("register");
                setError("");
              }}
            >
              Create account
            </button>
          </div>

          <form className="auth-form" onSubmit={handleSubmit} noValidate>
            <label className="field" htmlFor={`${formId}-username`}>
              Username
              <input
                id={`${formId}-username`}
                name="username"
                type="text"
                autoComplete="username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
                minLength={2}
                disabled={submitting}
              />
            </label>

            {mode === "register" ? (
              <label className="field" htmlFor={`${formId}-email`}>
                Email
                <input
                  id={`${formId}-email`}
                  name="email"
                  type="email"
                  autoComplete="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  disabled={submitting}
                />
              </label>
            ) : null}

            <label className="field" htmlFor={`${formId}-password`}>
              Password
              <div className="auth-password-row">
                <input
                  id={`${formId}-password`}
                  name="password"
                  type={showPassword ? "text" : "password"}
                  autoComplete={mode === "signin" ? "current-password" : "new-password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  minLength={mode === "register" ? 8 : 1}
                  disabled={submitting}
                />
                <button
                  type="button"
                  className="button button-quiet auth-password-toggle"
                  onClick={() => setShowPassword((v) => !v)}
                  aria-pressed={showPassword}
                  aria-label={showPassword ? "Hide password" : "Show password"}
                >
                  {showPassword ? "Hide" : "Show"}
                </button>
              </div>
            </label>

            {error ? (
              <p className="status status-danger auth-error" role="alert">
                {error}
              </p>
            ) : null}

            <button
              type="submit"
              className="button button-primary auth-submit"
              disabled={submitting}
            >
              {submitting
                ? mode === "signin"
                  ? "Signing in…"
                  : "Creating account…"
                : mode === "signin"
                  ? "Sign in to PatchHive"
                  : "Create account & continue"}
            </button>
          </form>

          <div className="auth-demo">
            <p className="muted">Local / Docker staging demo accounts (after golden seed):</p>
            <p>
              User: <code>golden_demo</code> / <code>demo-pass</code>
            </p>
            <p>
              Admin: <code>admin_demo</code> / <code>admin-pass</code>
            </p>
            <div className="auth-demo-actions">
              <button type="button" className="button button-secondary" onClick={fillDemoUser}>
                Fill demo user
              </button>
              <button type="button" className="button button-secondary" onClick={fillDemoAdmin}>
                Fill demo admin
              </button>
            </div>
          </div>

          <p className="auth-back muted">
            <Link to="/">← Back to workspace home</Link>
          </p>
        </div>
      </div>
    </section>
  );
}
