/**
 * CaseStep — builder steps 1 and 2 on /racks/new: choose a Eurorack case, then name and
 * create the empty rig. The create controls appear once a case is chosen.
 */
import { Link } from "react-router-dom";
import LoadFailure from "@/components/LoadFailure";
import { ACCOUNTS_OPEN } from "@/lib/apiBase";
import type { Case, CatalogCaseListItem } from "@/types/api";

interface CaseStepProps {
  step: 1 | 2;
  caseQuery: string;
  onCaseQuery: (q: string) => void;
  casesLoading: boolean;
  /** Why the case lists didn't load, if neither did. */
  casesError: unknown;
  onRetryCases: () => void;
  catalogCases: CatalogCaseListItem[];
  legacyCases: Case[];
  selectedCatalogSlug: string | null;
  onSelectCatalog: (slug: string | null) => void;
  selectedCaseId: number | null;
  onSelectLegacy: (id: number | null) => void;
  /** The owner goes on with no Case, so each row is as wide as what's on it (spec 009). */
  withoutCase: boolean;
  onWithoutCase: (without: boolean) => void;
  selectedCatalogCase: CatalogCaseListItem | null;
  selectedLegacyCase: Case | null;
  compatNote: string | null;
  rigName: string;
  onRigName: (name: string) => void;
  signedIn: boolean;
  creating: boolean;
  onCreate: () => void;
  error: string;
  /** Admin and Ops only: copy every Eurorack catalog case into placement cases. */
  canSyncCatalog: boolean;
  syncing: boolean;
  syncNote: string;
  onSyncCatalog: () => void;
}

function rows(n: number): string {
  return `${n} row${n === 1 ? "" : "s"}`;
}

function casePowerSummary(c: Case): string {
  const parts: string[] = [];
  if (c.power_12v_ma != null) parts.push(`+12 ${c.power_12v_ma}mA`);
  if (c.power_neg12v_ma != null) parts.push(`−12 ${c.power_neg12v_ma}mA`);
  if (c.power_5v_ma != null) parts.push(`+5 ${c.power_5v_ma}mA`);
  if (parts.length) return parts.join(", ");
  if (c.powered === false || c.meta?.powered === false) return "Unpowered";
  return "Power unspecified (placement will not enforce rails)";
}

export default function CaseStep({
  step,
  caseQuery,
  onCaseQuery,
  casesLoading,
  casesError,
  onRetryCases,
  catalogCases,
  legacyCases,
  selectedCatalogSlug,
  onSelectCatalog,
  selectedCaseId,
  onSelectLegacy,
  withoutCase,
  onWithoutCase,
  selectedCatalogCase,
  selectedLegacyCase,
  compatNote,
  rigName,
  onRigName,
  signedIn,
  creating,
  onCreate,
  error,
  canSyncCatalog,
  syncing,
  syncNote,
  onSyncCatalog,
}: CaseStepProps) {
  const catalogRevision = selectedCatalogCase?.primary_revision;
  return (
    <>
      <section className="builder-step" aria-labelledby="case-step-title">
        <div className="builder-step__head">
          <h2 id="case-step-title">Choose a case, if you know it</h2>
          <p className="muted">
            Only Eurorack cases take placements. Without one, each row is as wide as the Modules on
            it.
          </p>
        </div>

        <div className="panel">
          <div className="toolbar builder-toolbar">
            <label className="field">
              Search cases
              <input
                type="search"
                value={caseQuery}
                placeholder="Manufacturer or model…"
                onChange={(e) => onCaseQuery(e.target.value)}
              />
            </label>
            <label className="field field--wide">
              Catalog case (preferred)
              <select
                value={selectedCatalogSlug ?? ""}
                onChange={(e) => onSelectCatalog(e.target.value || null)}
                disabled={casesLoading}
                aria-required={catalogCases.length > 0}
              >
                <option value="">
                  {casesLoading
                    ? "Loading…"
                    : catalogCases.length
                      ? "Select from normalized catalog…"
                      : "No catalog cases (use legacy below)"}
                </option>
                {catalogCases.map((c) => {
                  const cap = c.primary_revision?.capacity_value;
                  const unit = c.primary_revision?.capacity_unit || "hp";
                  return (
                    <option key={c.slug} value={c.slug}>
                      {c.manufacturer} {c.model}
                      {cap != null ? ` (${cap} ${unit})` : ""}
                    </option>
                  );
                })}
              </select>
            </label>
            <label className="field field--wide">
              Legacy case (fallback)
              <select
                value={selectedCaseId ?? ""}
                onChange={(e) => onSelectLegacy(e.target.value ? Number(e.target.value) : null)}
                disabled={casesLoading}
              >
                <option value="">
                  {casesLoading
                    ? "Loading…"
                    : catalogCases.length > 0
                      ? "Optional legacy override…"
                      : "Select legacy Eurorack case…"}
                </option>
                {legacyCases.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.brand} {c.name} ({c.total_hp}HP, {rows(c.rows)})
                  </option>
                ))}
              </select>
            </label>
          </div>

          <label className="case-optional" htmlFor="case-optional">
            <input
              id="case-optional"
              type="checkbox"
              checked={withoutCase}
              onChange={(e) => onWithoutCase(e.target.checked)}
            />
            <span>Go on without a Case</span>
          </label>

          {selectedCatalogCase ? (
            <div className="stat-row case-summary">
              <div className="stat-block">
                <p className="muted">Layout</p>
                <h3>
                  {catalogRevision?.capacity_value ?? "unknown"}{" "}
                  {catalogRevision?.capacity_unit || "hp"}
                  {catalogRevision?.row_count != null ? `, ${rows(catalogRevision.row_count)}` : ""}
                </h3>
              </div>
              <div className="stat-block">
                <p className="muted">Power</p>
                <h3>
                  {selectedCatalogCase.powered === false
                    ? "Unpowered"
                    : selectedCatalogCase.powered === true
                      ? "Powered (rails as the catalog states them)"
                      : "Power unspecified"}
                </h3>
              </div>
            </div>
          ) : null}
          {selectedLegacyCase && !selectedCatalogCase ? (
            <div className="stat-row case-summary">
              <div className="stat-block">
                <p className="muted">Layout</p>
                <h3>
                  {selectedLegacyCase.hp_per_row?.join(" + ") || selectedLegacyCase.total_hp} HP
                </h3>
              </div>
              <div className="stat-block">
                <p className="muted">Power</p>
                <h3>{casePowerSummary(selectedLegacyCase)}</h3>
              </div>
            </div>
          ) : null}
          {compatNote ? <p className="muted builder-note">{compatNote}</p> : null}
          {!casesLoading && casesError ? (
            <LoadFailure what="The case list" error={casesError} onRetry={onRetryCases} />
          ) : !casesLoading && catalogCases.length === 0 && legacyCases.length === 0 ? (
            <p className="status status-warning">
              No Eurorack cases available.
              {import.meta.env.DEV ? (
                <>
                  {" "}
                  Import <code>data/cases/seed-v1.json</code> via the catalog populator.
                </>
              ) : null}
            </p>
          ) : null}

          {canSyncCatalog ? (
            <>
              <hr className="section-rule" />
              <div className="builder-admin">
                <button
                  type="button"
                  className="button button-quiet"
                  onClick={onSyncCatalog}
                  disabled={syncing}
                >
                  {syncing ? "Syncing…" : "Sync all Eurorack catalog cases"}
                </button>
                <p className="muted builder-note" role={syncNote ? "status" : undefined}>
                  {syncNote || "Copies catalog cases into placement cases. Safe to run again."}
                </p>
              </div>
            </>
          ) : null}
        </div>
      </section>

      {step >= 2 ? (
        <section className="builder-step" aria-labelledby="create-step-title">
          <div className="builder-step__head">
            <h2 id="create-step-title">Create the rig</h2>
            <p className="muted">Placement opens once the rig exists.</p>
          </div>
          <div className="panel">
            <div className="toolbar builder-toolbar">
              <label className="field">
                Rig name (optional)
                <input
                  type="text"
                  value={rigName}
                  onChange={(e) => onRigName(e.target.value)}
                  placeholder="Auto-named if empty"
                />
              </label>
              <button
                type="button"
                className="button button-primary"
                onClick={onCreate}
                disabled={!signedIn || creating}
              >
                {creating ? "Creating…" : "Create empty rig"}
              </button>
            </div>
            {!signedIn ? (
              <p className="muted" role="note">
                {ACCOUNTS_OPEN ? (
                  <>
                    Rigs are saved to your account. <Link to="/login">Sign in</Link> to create one.
                  </>
                ) : (
                  "Rigs are saved to your account. Accounts open when the PatchHive service goes live."
                )}
              </p>
            ) : null}
            {error ? (
              <p className="status status-danger" role="alert">
                {error}
              </p>
            ) : null}
          </div>
        </section>
      ) : null}
    </>
  );
}
