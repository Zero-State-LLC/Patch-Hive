import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import LoadFailure from "@/components/LoadFailure";
import { photoApi } from "@/lib/api";
import type { RigPhotoAsset } from "@/lib/api";
import { formatDate } from "@/lib/format";
import { CURRENT_STATUSES } from "@/lib/reading";

/** The owner's photos of a Rig: back to a Reading still open, a new photo, and each kept photo
 * with the day it goes and a way to delete it now (spec 009 stories 30, 31 and 33). */
export default function RigPhotos({ rigId }: { rigId: number }) {
  const [photos, setPhotos] = useState<RigPhotoAsset[] | null>(null);
  const [readingOpen, setReadingOpen] = useState(false);
  const [loadError, setLoadError] = useState<unknown>(null);
  const [attempt, setAttempt] = useState(0);
  // The photo whose deletion is waiting for the owner to say yes.
  const [asking, setAsking] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState("");
  // Each step swaps the button that was pressed for another, so focus follows it: to the
  // question, back to Delete on "Keep it", and to the heading once the photo is gone.
  const confirmRef = useRef<HTMLButtonElement>(null);
  const headingRef = useRef<HTMLHeadingElement>(null);
  const deleteButtons = useRef<Record<string, HTMLButtonElement | null>>({});
  const [focusDelete, setFocusDelete] = useState<string | null>(null);

  useEffect(() => {
    if (asking) confirmRef.current?.focus();
  }, [asking]);
  useEffect(() => {
    if (focusDelete) deleteButtons.current[focusDelete]?.focus();
  }, [focusDelete]);

  useEffect(() => {
    let live = true;
    Promise.all([photoApi.photos(rigId), photoApi.readings(rigId)])
      .then(([listed, read]) => {
        if (!live) return;
        setPhotos(listed.data.assets ?? []);
        setReadingOpen((read.data.readings ?? []).some((r) => CURRENT_STATUSES.has(r.status)));
        setLoadError(null);
      })
      .catch((error: unknown) => {
        if (live) setLoadError(error);
      });
    return () => {
      live = false;
    };
  }, [rigId, attempt]);

  const remove = async (photoId: string) => {
    setDeleting(true);
    setDeleteError("");
    try {
      await photoApi.deletePhoto(rigId, photoId);
      setPhotos((kept) => (kept ?? []).filter((photo) => photo.id !== photoId));
      setAsking(null);
      headingRef.current?.focus();
    } catch {
      setDeleteError("The photo couldn't be deleted. Try again.");
    } finally {
      setDeleting(false);
    }
  };

  return (
    <section className="rig-photos" aria-labelledby="rig-photos-title">
      <h3 id="rig-photos-title" ref={headingRef} tabIndex={-1}>
        Photos
      </h3>
      <div className="toolbar">
        {readingOpen ? (
          <Link className="button button-primary" to={`/rigs/${rigId}/reading`}>
            Check the reading
          </Link>
        ) : null}
        <Link className="button button-secondary" to={`/rigs/${rigId}/photo`}>
          Take a new photo
        </Link>
      </div>
      {loadError ? (
        <LoadFailure
          what="Your photos"
          error={loadError}
          onRetry={() => setAttempt((n) => n + 1)}
        />
      ) : null}
      {photos?.length === 0 ? <p className="muted">No photo of this Rig is kept.</p> : null}
      {photos?.length ? (
        <ul className="rig-photos__list">
          {photos.map((photo) => {
            const taken = formatDate(photo.created_at);
            return (
              <li key={photo.id}>
                <span>
                  Taken {taken}, kept until {formatDate(photo.retention_expires_at)}
                </span>
                {asking === photo.id ? (
                  <span className="toolbar">
                    <button
                      ref={confirmRef}
                      className="button button-secondary"
                      type="button"
                      disabled={deleting}
                      aria-busy={deleting}
                      onClick={() => void remove(photo.id)}
                    >
                      {deleting ? "Deleting…" : "Delete it now"}
                    </button>
                    <button
                      className="button button-quiet"
                      type="button"
                      disabled={deleting}
                      onClick={() => {
                        setAsking(null);
                        setFocusDelete(photo.id);
                      }}
                    >
                      Keep it
                    </button>
                  </span>
                ) : (
                  <button
                    ref={(button) => {
                      deleteButtons.current[photo.id] = button;
                    }}
                    className="button button-quiet"
                    type="button"
                    aria-label={`Delete the photo taken ${taken}`}
                    onClick={() => {
                      setFocusDelete(null);
                      setAsking(photo.id);
                    }}
                  >
                    Delete
                  </button>
                )}
              </li>
            );
          })}
        </ul>
      ) : null}
      {deleteError ? (
        <p className="status status-danger" role="alert">
          {deleteError}
        </p>
      ) : null}
    </section>
  );
}
