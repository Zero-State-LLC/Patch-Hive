/**
 * Photo: where the photo journey starts (spec 009). Short guidance, the photo and the rows it
 * covers, and the owner's choice to let the reading service see it (decision 61). Where photo
 * reading is closed the screen says so and offers manual entry, and never takes the upload.
 *
 * Rows count from 0, as the rail and the placement editor count them.
 */
import { useEffect, useState, type FormEvent } from "react";
import { Link, useLocation, useNavigate, useParams, useSearchParams } from "react-router-dom";
import LoadFailure from "@/components/LoadFailure";
import { ListSkeleton } from "@/components/Skeletons";
import { photoApi, type PhotoReadingCapability } from "@/lib/api";
import { failureReason } from "@/lib/loadError";
import { apiCode, photoRefusal, readingReason } from "@/lib/reading";
import { useAuthStore, useReaderKey } from "@/lib/store";

export default function RigPhotoPage() {
  return <RigPhoto key={useReaderKey()} />;
}

function RigPhoto() {
  const { rigId } = useParams();
  const [params] = useSearchParams();
  const replaces = params.get("replaces") ?? undefined;
  const navigate = useNavigate();
  const location = useLocation();
  const signedIn = useAuthStore((s) => s.isAuthenticated());
  const [capability, setCapability] = useState<PhotoReadingCapability | null>(null);
  const [loadError, setLoadError] = useState<unknown>(null);
  const [attempt, setAttempt] = useState(0);
  const [file, setFile] = useState<File | null>(null);
  const [firstRow, setFirstRow] = useState(0);
  const [lastRow, setLastRow] = useState(0);
  const [consent, setConsent] = useState(false);
  const [sending, setSending] = useState(false);
  const [refusal, setRefusal] = useState("");

  useEffect(() => {
    if (!signedIn) {
      navigate("/login", { replace: true, state: { from: location.pathname + location.search } });
    }
  }, [signedIn, navigate, location.pathname, location.search]);

  useEffect(() => {
    let live = true;
    setLoadError(null);
    photoApi
      .capability()
      .then((response) => live && setCapability(response.data))
      .catch((error: unknown) => live && setLoadError(error));
    return () => {
      live = false;
    };
  }, [attempt]);

  const rowsValid = firstRow >= 0 && lastRow >= firstRow;
  const ready = Boolean(file) && consent && rowsValid && !sending;

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!file || !ready) return;
    setSending(true);
    setRefusal("");
    const rows = firstRow === lastRow ? `${firstRow}` : `${firstRow}-${lastRow}`;
    try {
      const response = await photoApi.start(file, {
        rows,
        consent,
        rigId: rigId ? Number(rigId) : undefined,
        replacesReadingId: replaces,
      });
      navigate(`/rigs/${response.data.rig_id}/reading`);
    } catch (error: unknown) {
      const code = apiCode(error);
      setRefusal(code ? photoRefusal(code) : failureReason(error));
      setSending(false);
    }
  };

  const title = replaces ? "Retake the photo" : rigId ? "Add a photo" : "Photograph your Rig";

  return (
    <section className="photo-step" aria-labelledby="photo-title">
      <header className="workspace-header">
        <div>
          <h1 id="photo-title">{title}</h1>
          <p className="muted">
            PatchHive reads every Module in the photo. Nothing joins your Rig until you confirm it.
          </p>
        </div>
      </header>

      {capability === null && !loadError ? (
        <ListSkeleton label="Checking photo reading…" rows={2} />
      ) : null}
      {loadError ? (
        <LoadFailure
          what="Photo reading"
          error={loadError}
          onRetry={() => setAttempt((n) => n + 1)}
        />
      ) : null}

      {capability && !capability.available ? (
        <div className="panel photo-closed">
          <p className="empty-title">Photo reading isn&apos;t open on this site yet.</p>
          <p className="muted">
            {readingReason(capability.reason)} You can still enter your Rig by hand and get a Patch
            Book.
          </p>
          <Link className="button button-primary" to="/racks/new">
            Enter your Rig by hand
          </Link>
        </div>
      ) : null}

      {capability?.available ? (
        <form className="panel photo-form" onSubmit={(event) => void submit(event)}>
          <p className="photo-guidance">
            Take the whole Rig, straight on, in even light. For a big Case, take one photo per row.
          </p>

          <label className="field" htmlFor="rig-photo">
            Photo of your Rig
            <input
              id="rig-photo"
              type="file"
              accept="image/jpeg,image/png,image/webp"
              capture="environment"
              onChange={(event) => setFile(event.target.files?.[0] ?? null)}
            />
          </label>

          <fieldset className="photo-rows">
            <legend>Rows this photo covers</legend>
            <p className="muted">Row 0 is the top row of the Case.</p>
            <label className="field field--num" htmlFor="photo-first-row">
              First row
              <input
                id="photo-first-row"
                type="number"
                min={0}
                value={firstRow}
                onChange={(event) => {
                  const row = Number(event.target.value);
                  setFirstRow(row);
                  if (lastRow < row) setLastRow(row);
                }}
              />
            </label>
            <label className="field field--num" htmlFor="photo-last-row">
              Last row
              <input
                id="photo-last-row"
                type="number"
                min={firstRow}
                value={lastRow}
                onChange={(event) => setLastRow(Number(event.target.value))}
              />
            </label>
          </fieldset>

          <label className="photo-consent" htmlFor="photo-consent">
            <input
              id="photo-consent"
              type="checkbox"
              checked={consent}
              onChange={(event) => setConsent(event.target.checked)}
            />
            <span>Let the reading service see this photo, so it can read the Modules in it.</span>
          </label>
          <p className="muted">
            Your photo stays private. It is kept for 30 days and then deleted, and you can delete it
            sooner.
          </p>

          {refusal ? (
            <p className="status status-danger" role="alert">
              {refusal}
            </p>
          ) : null}

          <div className="toolbar">
            <button
              className="button button-primary"
              type="submit"
              disabled={!ready}
              aria-busy={sending}
            >
              {sending ? "Reading the photo…" : "Read this photo"}
            </button>
            <Link className="button button-secondary" to="/racks/new">
              Enter your Rig by hand instead
            </Link>
          </div>
        </form>
      ) : null}
    </section>
  );
}
