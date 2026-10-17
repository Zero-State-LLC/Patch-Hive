/**
 * PatchBook Style Studio MVP — weighted recipe controls + preview + export.
 * Presentation only; never mutates patch topology.
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { canonApi } from "@/lib/api";
import {
  ALL_INFLUENCE_IDS,
  ARTISTIC_MODES,
  DEFAULT_STYLE_WEIGHTS,
  defaultRequestStyleRecipe,
  type PatchBookMode,
  type RequestStyleRecipe,
  type StyleWeights,
  type TemplateFamilyId,
} from "@/types/patchbookDesign";

type ServerRecipe = {
  id: string;
  name: string;
  notes: string | null;
  style_recipe: Record<string, unknown>;
  recipe_hash: string;
  is_shared?: boolean;
  created_at: string;
  updated_at: string;
};

const WEIGHT_KEYS = Object.keys(DEFAULT_STYLE_WEIGHTS) as Array<keyof StyleWeights>;

const MODES: PatchBookMode[] = [
  "professional",
  "editorial",
  "collector",
  "educational",
  "technical_archive",
  "symbolic",
  "abstract",
  "surreal",
  "gallery",
];

const FAMILIES: TemplateFamilyId[] = [
  "signal_manual",
  "hive_systems_atlas",
  "open_state",
  "modular_field_notes",
  "oscilloscope_journal",
  "circuit_archive",
  "museum_of_signal",
  "patent_future",
  "patch_cartography",
  "sonic_brutalism",
  "ritual_machine",
  "impossible_instrument",
];

const FAMILY_ALGORITHM: Record<TemplateFamilyId, string> = {
  signal_manual: "orthogonal_schematic",
  hive_systems_atlas: "hex_cell_map",
  open_state: "open_asymmetric_sparse",
  modular_field_notes: "notebook_checklist",
  oscilloscope_journal: "crt_bezel_frame",
  circuit_archive: "title_block_engineering",
  museum_of_signal: "gallery_plate_mat",
  patent_future: "figure_claims_two_col",
  patch_cartography: "seeded_force_cartography",
  sonic_brutalism: "brutalist_blocks",
  ritual_machine: "radial_seal_frame",
  impossible_instrument: "open_form_generative",
};

type BridgeFields = {
  source_run_id: string;
  source_rig_revision_id: string;
  artifact_manifest_hash: string;
};

export default function PatchBookStyleStudioPage() {
  const { rigId } = useParams<{ rigId: string }>();
  const [search] = useSearchParams();
  const bridge: BridgeFields | null = useMemo(() => {
    const source_run_id = search.get("source_run_id") || "";
    const source_rig_revision_id = search.get("source_rig_revision_id") || "";
    const artifact_manifest_hash = search.get("artifact_manifest_hash") || "";
    if (!source_run_id || !source_rig_revision_id || artifact_manifest_hash.length !== 64) {
      return null;
    }
    return { source_run_id, source_rig_revision_id, artifact_manifest_hash };
  }, [search]);

  const [recipe, setRecipe] = useState<RequestStyleRecipe>(() => defaultRequestStyleRecipe(384290));
  const [status, setStatus] = useState("");
  const [previewing, setPreviewing] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [preview, setPreview] = useState<{
    resolved_recipe: Record<string, unknown>;
    resolution_events: Array<{ code: string; message: string; field?: string | null }>;
    style_recipe_hash: string;
    library_content_hash: string;
    load_path: string;
    page_summaries: Array<{
      position: number;
      title: string;
      intent: string;
      edge_count: number;
      steps: Array<{ phase: string; instruction: string }>;
    }>;
  } | null>(null);
  const [serverLibrary, setServerLibrary] = useState<ServerRecipe[]>([]);
  const [recipeName, setRecipeName] = useState("");
  const [libraryBusy, setLibraryBusy] = useState(false);
  const [lastExportId, setLastExportId] = useState<string | null>(null);
  const [downloading, setDownloading] = useState(false);

  const artistic = ARTISTIC_MODES.includes(recipe.mode);

  const downloadArtifact = async (exportId: string, artifact: "pdf" | "zip") => {
    setDownloading(true);
    try {
      const tokenResp = await canonApi.createDownloadToken(exportId, 300);
      const url = canonApi.exportArtifactUrl(exportId, artifact, tokenResp.data.token);
      const auth = localStorage.getItem("auth_token");
      const res = await fetch(url, {
        headers: auth ? { Authorization: `Bearer ${auth}` } : {},
      });
      if (!res.ok) {
        setStatus(`Download failed (${res.status})`);
        return;
      }
      const blob = await res.blob();
      const objectUrl = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = objectUrl;
      a.download = artifact === "zip" ? `patchbook-${exportId}.zip` : `patchbook-${exportId}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(objectUrl);
      setStatus(`Downloaded ${artifact} for ${exportId}`);
    } catch {
      setStatus("Download failed — is fulfillment enabled and export succeeded?");
    } finally {
      setDownloading(false);
    }
  };

  const refreshServerLibrary = useCallback(async () => {
    try {
      const res = await canonApi.listStyleRecipes();
      setServerLibrary(res.data);
    } catch {
      // Library endpoints may 401 when signed out — keep empty
      setServerLibrary([]);
    }
  }, []);

  useEffect(() => {
    void refreshServerLibrary();
  }, [refreshServerLibrary]);

  const setWeight = (key: keyof StyleWeights, value: number) => {
    setRecipe((r) => ({
      ...r,
      weights: { ...r.weights, [key]: value },
    }));
  };

  const buildRequestBody = useCallback((): RequestStyleRecipe => {
    const next = { ...recipe };
    if (ARTISTIC_MODES.includes(next.mode)) {
      next.constraints = {
        ...next.constraints,
        artistic_disclosure_acknowledged: true,
        canonical_appendix_required: true,
        book_profile: "publication",
      };
    }
    return next;
  }, [recipe]);

  const handlePreview = async () => {
    if (!bridge) {
      setStatus("Missing run bridge fields. Open Style Studio from a ready export run.");
      return;
    }
    setPreviewing(true);
    setStatus("");
    try {
      const res = await canonApi.previewExport({
        source_run_id: bridge.source_run_id,
        source_rig_revision_id: bridge.source_rig_revision_id,
        artifact_manifest_hash: bridge.artifact_manifest_hash,
        style_recipe: buildRequestBody(),
        max_pages: 3,
      });
      setPreview(res.data);
      setStatus(
        `Preview ok · path=${res.data.load_path} · recipe ${res.data.style_recipe_hash.slice(0, 12)}…`,
      );
    } catch (error: unknown) {
      const apiError = error as { response?: { data?: { detail?: string } } };
      setStatus(apiError.response?.data?.detail || "Preview failed");
      setPreview(null);
    } finally {
      setPreviewing(false);
    }
  };

  const handleExport = async () => {
    if (!bridge) return;
    setExporting(true);
    setStatus("");
    try {
      const created = await canonApi.createExport({
        source_run_id: bridge.source_run_id,
        source_rig_revision_id: bridge.source_rig_revision_id,
        artifact_manifest_hash: bridge.artifact_manifest_hash,
        formats: ["pdf", "json"],
        license: "personal",
        idempotency_key: `studio-${bridge.source_run_id}-${crypto.randomUUID()}`,
        style_recipe: buildRequestBody(),
      });
      setLastExportId(created.data.export_id);
      setStatus(
        `Export ${created.data.export_id} · ${created.data.status}` +
          (created.data.composition_hash
            ? ` · composition ${created.data.composition_hash.slice(0, 12)}…`
            : ""),
      );
      if (created.data.status === "succeeded") {
        // Auto-offer download path in status; user clicks buttons below
      }
    } catch (error: unknown) {
      const apiError = error as { response?: { data?: { detail?: string }; status?: number } };
      if (apiError.response?.status === 402) {
        setStatus("INSUFFICIENT_CREDITS — no debit recorded.");
      } else {
        setStatus(apiError.response?.data?.detail || "Export failed");
      }
    } finally {
      setExporting(false);
    }
  };

  const randomizeSeed = () => {
    setRecipe((r) => ({
      ...r,
      seed: Math.floor(Math.random() * 2_147_483_647),
    }));
  };

  return (
    <section aria-labelledby="studio-title" className="style-studio">
      <header className="workspace-header">
        <div>
          <p className="eyebrow">PatchBook Design Engine</p>
          <h1 id="studio-title">Style Studio</h1>
          <p className="muted">
            Deterministic publishing instrument — presentation only. Canonical patch data is never
            mutated.
          </p>
          {rigId ? (
            <p>
              <Link to={`/rigs/${rigId}`}>← Back to rig</Link>
            </p>
          ) : null}
        </div>
      </header>

      {!bridge ? (
        <div className="panel status status-warning" role="status">
          Open Style Studio from a rig export run with bridge fields, or append{" "}
          <code>source_run_id</code>, <code>source_rig_revision_id</code>, and{" "}
          <code>artifact_manifest_hash</code> query params.
        </div>
      ) : (
        <p className="muted panel">
          Run <code>{bridge.source_run_id}</code> · revision{" "}
          <code>{bridge.source_rig_revision_id.slice(0, 20)}…</code>
        </p>
      )}

      {artistic ? (
        <div className="panel status status-warning" role="alert">
          This mode prioritizes visual interpretation over complete technical readability. A
          canonical technical appendix will remain available.
        </div>
      ) : null}

      <div className="style-studio-grid">
        <div className="panel">
          <h2>Mode &amp; family</h2>
          <label className="field">
            Mode
            <select
              value={recipe.mode}
              onChange={(e) => setRecipe((r) => ({ ...r, mode: e.target.value as PatchBookMode }))}
            >
              {MODES.map((m) => (
                <option key={m} value={m}>
                  {m}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            Template family
            <select
              value={recipe.template_family}
              onChange={(e) =>
                setRecipe((r) => ({
                  ...r,
                  template_family: e.target.value as TemplateFamilyId,
                }))
              }
            >
              {FAMILIES.map((f) => (
                <option key={f} value={f}>
                  {f}
                </option>
              ))}
            </select>
          </label>
          <p className="muted" style={{ fontSize: "0.85rem" }}>
            Layout algorithm: <code>{FAMILY_ALGORITHM[recipe.template_family]}</code>
          </p>
          <label className="field">
            Seed
            <div style={{ display: "flex", gap: "0.5rem" }}>
              <input
                type="number"
                min={0}
                max={2147483647}
                value={recipe.seed}
                onChange={(e) => setRecipe((r) => ({ ...r, seed: Number(e.target.value) || 0 }))}
              />
              <button className="button button-secondary" type="button" onClick={randomizeSeed}>
                Randomize
              </button>
            </div>
          </label>
          <label className="field">
            Notes
            <input
              type="text"
              maxLength={500}
              value={recipe.notes || ""}
              onChange={(e) => setRecipe((r) => ({ ...r, notes: e.target.value }))}
            />
          </label>
        </div>

        <div className="panel">
          <h2>Master weights</h2>
          <div className="weight-sliders">
            {WEIGHT_KEYS.map((key) => (
              <label key={key} className="field weight-row">
                <span>
                  {key.replace(/_/g, " ")} <strong>{recipe.weights[key]}</strong>
                </span>
                <input
                  type="range"
                  min={0}
                  max={100}
                  value={recipe.weights[key]}
                  onChange={(e) => setWeight(key, Number(e.target.value))}
                />
              </label>
            ))}
          </div>
          <button
            className="button button-quiet"
            type="button"
            onClick={() => setRecipe((r) => ({ ...r, weights: { ...DEFAULT_STYLE_WEIGHTS } }))}
          >
            Reset weights
          </button>
        </div>
      </div>

      <div className="panel" style={{ marginTop: "1rem" }}>
        <h2>Influence mixer</h2>
        <p className="muted">
          All 32 style vectors (0–100). Engine normalizes competing groups; conflicts appear in
          preview resolution events.
        </p>
        <div className="weight-sliders influence-grid">
          {ALL_INFLUENCE_IDS.map((key) => {
            const value = recipe.influences[key] ?? 0;
            return (
              <label key={key} className="field weight-row">
                <span>
                  {key.replace(/_/g, " ")} <strong>{value}</strong>
                </span>
                <input
                  type="range"
                  min={0}
                  max={100}
                  value={value}
                  onChange={(e) => {
                    const next = Number(e.target.value);
                    setRecipe((r) => {
                      const influences = { ...r.influences };
                      if (next <= 0) {
                        delete influences[key];
                      } else {
                        influences[key] = next;
                      }
                      return { ...r, influences };
                    });
                  }}
                />
              </label>
            );
          })}
        </div>
        <button
          className="button button-quiet"
          type="button"
          onClick={() =>
            setRecipe((r) => ({
              ...r,
              influences: {
                engineering: 92,
                swiss: 65,
                scientific: 55,
                cyber_hive: 24,
              },
            }))
          }
        >
          Reset influences
        </button>
      </div>

      <div className="panel" style={{ marginTop: "1rem" }}>
        <h2>Recipe library</h2>
        <p className="muted">
          Server-backed library for your account (max 40). Export/preview can reference a recipe by
          id so the sealed debit snapshot matches the library entry.
        </p>
        <div style={{ display: "flex", flexWrap: "wrap", gap: "0.5rem", alignItems: "center" }}>
          <input
            type="text"
            placeholder="Recipe name"
            value={recipeName}
            maxLength={80}
            onChange={(e) => setRecipeName(e.target.value)}
            style={{ minWidth: "12rem" }}
          />
          <button
            className="button button-secondary"
            type="button"
            disabled={libraryBusy || !recipeName.trim()}
            onClick={() => {
              void (async () => {
                setLibraryBusy(true);
                try {
                  const created = await canonApi.createStyleRecipe({
                    name: recipeName.trim(),
                    style_recipe: buildRequestBody() as unknown as Record<string, unknown>,
                  });
                  setRecipeName("");
                  await refreshServerLibrary();
                  setStatus(`Saved server recipe “${created.data.name}” (${created.data.id})`);
                } catch (error: unknown) {
                  const apiError = error as { response?: { data?: { detail?: string } } };
                  setStatus(apiError.response?.data?.detail || "Save recipe failed");
                } finally {
                  setLibraryBusy(false);
                }
              })();
            }}
          >
            Save to account
          </button>
        </div>
        {serverLibrary.length === 0 ? (
          <p className="muted" style={{ marginTop: "0.75rem" }}>
            No server recipes yet (sign in required).
          </p>
        ) : (
          <ul style={{ marginTop: "0.75rem", paddingLeft: "1.1rem" }}>
            {serverLibrary.map((entry) => {
              const loaded = entry.style_recipe as unknown as RequestStyleRecipe;
              return (
                <li key={entry.id} style={{ marginBottom: "0.4rem" }}>
                  <strong>{entry.name}</strong>{" "}
                  <span className="muted">
                    · {String(loaded.mode || "?")} / {String(loaded.template_family || "?")} ·{" "}
                    <code>{entry.recipe_hash.slice(0, 10)}…</code>
                  </span>{" "}
                  <button
                    className="button button-quiet"
                    type="button"
                    onClick={() => {
                      setRecipe(loaded);
                      setStatus(`Loaded “${entry.name}”`);
                    }}
                  >
                    Load
                  </button>{" "}
                  <button
                    className="button button-quiet"
                    type="button"
                    onClick={() => {
                      void (async () => {
                        if (!bridge) {
                          setStatus("Need bridge fields to export by recipe id");
                          return;
                        }
                        setExporting(true);
                        try {
                          const created = await canonApi.createExport({
                            source_run_id: bridge.source_run_id,
                            source_rig_revision_id: bridge.source_rig_revision_id,
                            artifact_manifest_hash: bridge.artifact_manifest_hash,
                            formats: ["pdf", "json"],
                            license: "personal",
                            idempotency_key: `studio-lib-${entry.id}-${crypto.randomUUID()}`,
                            style_recipe_id: entry.id,
                          });
                          setStatus(
                            `Export ${created.data.export_id} · ${created.data.status}` +
                              (created.data.style_recipe_id
                                ? ` · recipe ${created.data.style_recipe_id}`
                                : ""),
                          );
                        } catch (error: unknown) {
                          const apiError = error as {
                            response?: { data?: { detail?: string }; status?: number };
                          };
                          setStatus(
                            apiError.response?.status === 402
                              ? "INSUFFICIENT_CREDITS"
                              : apiError.response?.data?.detail || "Export failed",
                          );
                        } finally {
                          setExporting(false);
                        }
                      })();
                    }}
                  >
                    Export with id
                  </button>{" "}
                  <button
                    className="button button-quiet"
                    type="button"
                    disabled={libraryBusy}
                    onClick={() => {
                      void (async () => {
                        setLibraryBusy(true);
                        try {
                          await canonApi.updateStyleRecipe(entry.id, {
                            is_shared: !entry.is_shared,
                          });
                          await refreshServerLibrary();
                          setStatus(
                            entry.is_shared
                              ? `“${entry.name}” is private again`
                              : `“${entry.name}” shared (readable via /style-recipes/shared/{id})`,
                          );
                        } catch {
                          setStatus("Share toggle failed");
                        } finally {
                          setLibraryBusy(false);
                        }
                      })();
                    }}
                  >
                    {entry.is_shared ? "Unshare" : "Share"}
                  </button>{" "}
                  <button
                    className="button button-quiet"
                    type="button"
                    disabled={libraryBusy}
                    onClick={() => {
                      void (async () => {
                        setLibraryBusy(true);
                        try {
                          await canonApi.deleteStyleRecipe(entry.id);
                          await refreshServerLibrary();
                          setStatus(`Deleted “${entry.name}”`);
                        } catch {
                          setStatus("Delete failed");
                        } finally {
                          setLibraryBusy(false);
                        }
                      })();
                    }}
                  >
                    Delete
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </div>

      <div className="panel" style={{ marginTop: "1rem" }}>
        <div style={{ display: "flex", flexWrap: "wrap", gap: "0.5rem" }}>
          <button
            className="button button-secondary"
            type="button"
            disabled={!bridge || previewing}
            onClick={() => void handlePreview()}
          >
            {previewing ? "Previewing…" : "Preview (free)"}
          </button>
          <button
            className="button button-primary"
            type="button"
            disabled={!bridge || exporting}
            onClick={() => void handleExport()}
          >
            {exporting ? "Exporting…" : "Export with recipe"}
          </button>
        </div>
        {status ? (
          <p role="status" className="status" style={{ marginTop: "0.75rem" }}>
            {status}
          </p>
        ) : null}
        {lastExportId ? (
          <div style={{ display: "flex", flexWrap: "wrap", gap: "0.5rem", marginTop: "0.75rem" }}>
            <button
              className="button button-secondary"
              type="button"
              disabled={downloading}
              onClick={() => void downloadArtifact(lastExportId, "pdf")}
            >
              {downloading ? "Downloading…" : "Download PDF"}
            </button>
            <button
              className="button button-quiet"
              type="button"
              disabled={downloading}
              onClick={() => void downloadArtifact(lastExportId, "zip")}
            >
              Download ZIP pack
            </button>
          </div>
        ) : null}
      </div>

      {preview ? (
        <div className="panel" style={{ marginTop: "1rem" }}>
          <h2>Preview</h2>
          <p className="muted">
            load_path=<code>{preview.load_path}</code> · library{" "}
            <code>{preview.library_content_hash.slice(0, 16)}…</code>
          </p>
          {preview.resolution_events.length > 0 ? (
            <div aria-label="Constraint resolution events">
              <h3>Resolved conflicts</h3>
              <ul>
                {preview.resolution_events.map((ev) => (
                  <li key={ev.code + (ev.field || "")}>
                    <code>{ev.code}</code> — {ev.message}
                  </li>
                ))}
              </ul>
            </div>
          ) : (
            <p className="muted">No constraint clamps on this recipe.</p>
          )}
          <h3>Pages</h3>
          {preview.page_summaries.map((page) => (
            <article key={page.position} className="panel" style={{ marginBottom: "0.75rem" }}>
              <h4>
                {page.position + 1}. {page.title}
              </h4>
              <p>{page.intent}</p>
              <p className="muted">{page.edge_count} cables</p>
              <ol>
                {page.steps.map((s, i) => (
                  <li key={i}>
                    [{s.phase}] {s.instruction}
                  </li>
                ))}
              </ol>
            </article>
          ))}
        </div>
      ) : null}
    </section>
  );
}
