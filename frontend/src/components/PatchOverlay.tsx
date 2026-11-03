/**
 * PatchOverlay — the user's own notes, favorite and tried marks on a patch. Generated patches
 * never change; this is a separate, personal layer saved per patch. The fields stay closed until
 * the saved notes have loaded, so a slow or failed load can never be saved over them.
 */
import { useEffect, useState } from "react";
import { canonApi, legacyPatchRef } from "@/lib/api";

interface OverlayState {
  notes: string;
  favorite: boolean;
  tried: boolean;
}

type LoadState = "loading" | "ready" | "signed-out" | "error";

const EMPTY: OverlayState = { notes: "", favorite: false, tried: false };

function statusOf(error: unknown): number | undefined {
  return (error as { response?: { status?: number } })?.response?.status;
}

/** headingLevel fits the heading into the page's outline: 2 on its own page, 3 under a patch name. */
export default function PatchOverlay({
  patchId,
  headingLevel = 3,
}: {
  patchId: number;
  headingLevel?: 2 | 3;
}) {
  const Heading = headingLevel === 2 ? "h2" : "h3";
  const [overlay, setOverlay] = useState<OverlayState>(EMPTY);
  const [load, setLoad] = useState<LoadState>("loading");
  const [attempt, setAttempt] = useState(0);
  const [status, setStatus] = useState("");

  useEffect(() => {
    let current = true;
    setOverlay(EMPTY);
    setLoad("loading");
    setStatus("");
    canonApi
      .getOverlay(legacyPatchRef(patchId))
      .then((response) => {
        if (!current) return;
        setOverlay({
          notes: response.data.notes ?? "",
          favorite: response.data.favorite,
          tried: response.data.tried,
        });
        setLoad("ready");
      })
      .catch((error: unknown) => {
        if (!current) return;
        const code = statusOf(error);
        // Nothing saved yet is an empty overlay; anything else must not be saved over.
        if (code === 404) setLoad("ready");
        else if (code === 401 || code === 403) setLoad("signed-out");
        else setLoad("error");
      });
    return () => {
      current = false;
    };
  }, [patchId, attempt]);

  const save = async () => {
    setStatus("Saving…");
    try {
      await canonApi.upsertOverlay(legacyPatchRef(patchId), overlay);
      setStatus("Saved. Your notes stay separate from the generated patch.");
    } catch (error) {
      const code = statusOf(error);
      setStatus(
        code === 401 || code === 403
          ? "Sign in to save your notes."
          : "Couldn't save your notes. Try again.",
      );
    }
  };

  const ready = load === "ready";

  return (
    <div
      className="panel patch-notes"
      aria-label="Personal patch overlay"
      aria-busy={load === "loading"}
    >
      <Heading>Your notes</Heading>
      {load === "signed-out" ? (
        <p className="muted">Sign in to keep your own notes on this patch.</p>
      ) : load === "error" ? (
        <div className="screen-state-actions">
          <p className="status status-warning" role="status">
            Couldn&apos;t load your notes.
          </p>
          <button
            className="button button-secondary"
            type="button"
            onClick={() => setAttempt((n) => n + 1)}
          >
            Retry
          </button>
        </div>
      ) : (
        <>
          <label className="field">
            Notes
            <textarea
              value={overlay.notes}
              onChange={(event) => setOverlay((o) => ({ ...o, notes: event.target.value }))}
              rows={4}
              disabled={!ready}
            />
          </label>
          <label className="check-row">
            <input
              type="checkbox"
              checked={overlay.favorite}
              onChange={(event) => setOverlay((o) => ({ ...o, favorite: event.target.checked }))}
              disabled={!ready}
            />
            Favorite
          </label>
          <label className="check-row">
            <input
              type="checkbox"
              checked={overlay.tried}
              onChange={(event) => setOverlay((o) => ({ ...o, tried: event.target.checked }))}
              disabled={!ready}
            />
            Tried
          </label>
          <div className="page-hero-actions">
            <button
              className="button button-secondary"
              type="button"
              onClick={() => void save()}
              disabled={!ready}
            >
              Save notes
            </button>
          </div>
          {status ? (
            <p role="status" className="status">
              {status}
            </p>
          ) : null}
        </>
      )}
    </div>
  );
}
