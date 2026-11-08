/**
 * Reading: where every correction happens (spec 009). Each photo with numbered boxes, beside
 * the same Sightings as a text list that works by keyboard and screen reader, the Modules
 * PatchHive is unsure of first. The owner picks a close match, searches the catalog, says
 * "not a Module", leaves one out, adds one, and corrects the layout, then confirms the whole
 * Rig in one step. Nothing joins the Rig until then.
 *
 * Rows and HP count from 0, as the rail and the placement editor count them.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import CatalogSearch from "@/components/CatalogSearch";
import LoadFailure from "@/components/LoadFailure";
import RigRail, { type RailRack } from "@/components/RigRail";
import { ListSkeleton } from "@/components/Skeletons";
import { canonApi, photoApi, type PhotoReading, type Sighting } from "@/lib/api";
import { rigDetailToRack } from "@/lib/canonRigAdapter";
import { failureReason } from "@/lib/loadError";
import {
  type AddedModule,
  type Decision,
  apiCode,
  apiModules,
  clashes,
  confirmBody,
  CURRENT_STATUSES,
  dispositionTone,
  dispositionWords,
  initialDecision,
  isDecided,
  moduleLabel,
  namePlaced,
  orderSightings,
  pastCase,
  photoRefusal,
  readingReason,
  refusalWords,
} from "@/lib/reading";
import { useReaderKey } from "@/lib/store";
import type { Module, Rack } from "@/types/api";

// A Reading still being read is asked about again after this long.
const REFRESH_MS = 2000;

export default function RigReadingPage() {
  return <RigReading key={useReaderKey()} />;
}

function RigReading() {
  const rigId = Number(useParams().rigId);
  const navigate = useNavigate();
  const [readings, setReadings] = useState<PhotoReading[] | null>(null);
  const [loadError, setLoadError] = useState<unknown>(null);
  const [decisions, setDecisions] = useState<Record<string, Decision>>({});
  const [added, setAdded] = useState<AddedModule[]>([]);
  const [correcting, setCorrecting] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [refusal, setRefusal] = useState("");
  const [retrying, setRetrying] = useState<string | null>(null);
  const [retryError, setRetryError] = useState<{ readingId: string; text: string } | null>(null);
  // The Rig as it is now: its Case, and the Placements on rows no current photo covers.
  const [rig, setRig] = useState<Rack | null>(null);
  // What the owner had decided before leaving a Sighting out, so "Keep it" brings it back.
  const setAside = useRef<Record<string, Decision>>({});
  const live = useRef(true);

  const load = useCallback(async () => {
    try {
      const [response, detail] = await Promise.all([
        photoApi.readings(rigId),
        canonApi.getRig(rigId),
      ]);
      if (!live.current) return;
      const all = response.data.readings ?? [];
      setReadings(all);
      setRig(rigDetailToRack(detail.data));
      setLoadError(null);
      // Decisions follow the list's order, so a confirmation sends them in the order shown.
      setDecisions((made) => {
        const next: Record<string, Decision> = {};
        for (const reading of all.filter((r) => r.status === "read")) {
          for (const s of orderSightings(reading.sightings)) {
            const start = made[s.sighting_id] ?? initialDecision(s);
            if (start) next[s.sighting_id] = start;
          }
        }
        return next;
      });
    } catch (error: unknown) {
      if (live.current) setLoadError(error);
    }
  }, [rigId]);

  useEffect(() => {
    live.current = true;
    void load();
    return () => {
      live.current = false;
    };
  }, [load]);

  const current = useMemo(
    () => (readings ?? []).filter((r) => CURRENT_STATUSES.has(r.status)),
    [readings],
  );
  const stillReading = current.some((r) => r.status === "reading");

  useEffect(() => {
    if (!stillReading) return;
    const timer = window.setTimeout(() => void load(), REFRESH_MS);
    return () => window.clearTimeout(timer);
  }, [stillReading, readings, load]);

  const decide = (sightingId: string, decision: Decision) => {
    const before = decisions[sightingId];
    if ((decision.kind === "leave_out" || decision.kind === "not_a_module") && before) {
      if (before.kind === "keep" || before.kind === "undecided") {
        setAside.current[sightingId] = before;
      }
    }
    setDecisions((made) => ({ ...made, [sightingId]: decision }));
  };
  const restore = (s: Sighting) =>
    decide(
      s.sighting_id,
      setAside.current[s.sighting_id] ??
        initialDecision(s) ?? { kind: "undecided", row: s.row_index, startHp: s.start_hp },
    );

  const { body, undecided } = confirmBody(decisions, added);
  // A photo of some rows says nothing about the others: their Placements stay (T031).
  const covered = new Set(
    current.flatMap((r) =>
      Array.from({ length: r.last_row - r.first_row + 1 }, (_, i) => r.first_row + i),
    ),
  );
  const kept = (rig?.modules ?? [])
    .filter((m) => m.module && !covered.has(m.row_index))
    .map((m) => ({
      key: `kept-${m.id}`,
      row: m.row_index,
      startHp: m.start_hp,
      hp: m.module?.hp ?? 0,
      label: moduleLabel(m.module?.brand ?? null, m.module?.name ?? null),
      moduleId: m.module_id,
    }));
  const placed = [
    ...Object.entries(decisions).flatMap(([key, d]) =>
      d.kind === "keep"
        ? [{ key, row: d.row, startHp: d.startHp, hp: d.hp, label: d.label, moduleId: d.moduleId }]
        : [],
    ),
    ...added.map((a, i) => ({ key: `added-${i}`, ...a })),
    ...kept,
  ];
  const clashing = clashes(placed);
  const past = pastCase(placed, rig?.case?.hp_per_row);
  const flagged = new Set([...clashing, ...past]);
  const waiting = current.filter((r) => r.status !== "read");
  const canConfirm =
    current.length > 0 &&
    waiting.length === 0 &&
    undecided.length === 0 &&
    clashing.size === 0 &&
    past.size === 0;

  const preview: RailRack = {
    name: "Your Rig as it will be confirmed",
    case: rig?.case,
    modules: placed.map((p, i) => ({
      id: i + 1,
      module_id: p.moduleId,
      row_index: p.row,
      start_hp: p.startHp,
      module: { id: p.moduleId, brand: "", name: p.label, hp: p.hp, module_type: "" },
    })),
  };

  const retry = async (readingId: string) => {
    setRetrying(readingId);
    setRetryError(null);
    try {
      await photoApi.retry(rigId, readingId);
      await load();
    } catch (error: unknown) {
      const code = apiCode(error);
      setRetryError({ readingId, text: code ? photoRefusal(code) : failureReason(error) });
    } finally {
      setRetrying(null);
    }
  };

  const confirm = async () => {
    if (!canConfirm) return;
    setConfirming(true);
    setRefusal("");
    try {
      await photoApi.confirm(rigId, body);
      navigate(`/rigs/${rigId}`);
    } catch (error: unknown) {
      const code = apiCode(error);
      const named = apiModules(error)
        .map((id) => placed.find((p) => p.moduleId === id)?.label)
        .filter(Boolean);
      setRefusal(
        code
          ? `${refusalWords(code)}${named.length ? ` ${named.join(", ")}.` : ""}`
          : failureReason(error),
      );
      setConfirming(false);
      // Another photo replaced one of these: show the owner the reading as it is now.
      if (code === "READINGS_CHANGED") void load();
    }
  };

  return (
    <section className="reading-step" aria-labelledby="reading-title">
      <header className="workspace-header">
        <div>
          <h1 id="reading-title">Check the reading</h1>
          <p className="muted">
            Fix anything PatchHive got wrong, then confirm. Nothing joins your Rig until you do.
          </p>
        </div>
        <div className="header-actions toolbar">
          <button
            className="button button-secondary"
            type="button"
            aria-pressed={correcting}
            onClick={() => setCorrecting((on) => !on)}
          >
            Correct the layout
          </button>
          <Link className="button button-secondary" to={`/rigs/${rigId}/photo`}>
            Add a photo of another row
          </Link>
        </div>
      </header>

      {readings === null && !loadError ? (
        <ListSkeleton label="Loading the reading…" rows={4} />
      ) : null}
      {loadError ? (
        <LoadFailure what="This Rig's reading" error={loadError} onRetry={() => void load()} />
      ) : null}

      {readings !== null && current.length === 0 ? (
        <div className="panel">
          <p className="empty-title">Every photo of this Rig is confirmed.</p>
          <p className="muted">
            Take a new photo when the Rig changes; earlier books stay as they were.
          </p>
          <div className="toolbar">
            <Link className="button button-primary" to={`/rigs/${rigId}`}>
              Open the Rig
            </Link>
            <Link className="button button-secondary" to={`/rigs/${rigId}/photo`}>
              Take a new photo
            </Link>
          </div>
        </div>
      ) : null}

      {current.map((reading) => (
        <ReadingSection
          key={reading.reading_id}
          rigId={rigId}
          reading={reading}
          decisions={decisions}
          clashing={flagged}
          correcting={correcting}
          retrying={retrying === reading.reading_id}
          retryError={retryError?.readingId === reading.reading_id ? retryError.text : null}
          onRetry={() => void retry(reading.reading_id)}
          onDecide={decide}
          onRestore={restore}
        />
      ))}

      {current.length > 0 ? (
        <>
          <AddModule onAdd={(module) => setAdded((list) => [...list, module])} />
          {added.length > 0 ? (
            <ul className="added-list" aria-label="Modules you added">
              {added.map((a, i) => (
                <li
                  key={`${a.moduleId}-${i}`}
                  className={flagged.has(`added-${i}`) ? "is-clashing" : undefined}
                >
                  <span>
                    {a.label}, row {a.row}, HP {a.startHp} to {a.startHp + a.hp}
                  </span>
                  <button
                    className="button button-secondary"
                    type="button"
                    onClick={() => setAdded((list) => list.filter((_, j) => j !== i))}
                  >
                    Remove
                  </button>
                </li>
              ))}
            </ul>
          ) : null}

          <div className="panel reading-confirm">
            {placed.length > 0 ? (
              <>
                <p className="muted">Your Rig as it will be confirmed</p>
                <RigRail rack={preview} />
              </>
            ) : null}
            {kept.length > 0 ? (
              <ul className="kept-list" aria-label="Placements on other rows">
                {kept.map((k) => (
                  <li key={k.key} className="muted">
                    {k.label} stays on row {k.row}, HP {k.startHp} to {k.startHp + k.hp}
                  </li>
                ))}
              </ul>
            ) : null}
            {clashing.size > 0 ? (
              <p className="status status-danger" role="alert">
                These overlap in a row: {namePlaced(placed, clashing)}. Move them apart before
                confirming.
              </p>
            ) : null}
            {past.size > 0 ? (
              <p className="status status-danger" role="alert">
                These sit past the end of a row of the Case: {namePlaced(placed, past)}. Move them
                before confirming.
              </p>
            ) : null}
            {undecided.length > 0 ? (
              <p className="status status-warning" role="status">
                {undecided.length} still to decide: choose a Module for each, or leave it out.
              </p>
            ) : null}
            {refusal ? (
              <p className="status status-danger" role="alert">
                {refusal}
              </p>
            ) : null}
            <button
              className="button button-primary"
              type="button"
              disabled={!canConfirm || confirming}
              aria-busy={confirming}
              onClick={() => void confirm()}
            >
              {confirming ? "Confirming…" : "Confirm the Rig"}
            </button>
          </div>
        </>
      ) : null}
    </section>
  );
}

function ReadingSection({
  rigId,
  reading,
  decisions,
  clashing,
  correcting,
  retrying,
  retryError,
  onRetry,
  onDecide,
  onRestore,
}: {
  rigId: number;
  reading: PhotoReading;
  decisions: Record<string, Decision>;
  clashing: Set<string>;
  correcting: boolean;
  retrying: boolean;
  retryError: string | null;
  onRetry: () => void;
  onDecide: (sightingId: string, decision: Decision) => void;
  onRestore: (sighting: Sighting) => void;
}) {
  const rows =
    reading.first_row === reading.last_row
      ? `row ${reading.first_row}`
      : `rows ${reading.first_row} to ${reading.last_row}`;
  const ordered = orderSightings(reading.sightings);
  const retake = (
    <Link
      className="button button-secondary"
      to={`/rigs/${rigId}/photo?replaces=${encodeURIComponent(reading.reading_id)}`}
    >
      Retake
    </Link>
  );

  return (
    <article className="panel reading" aria-label={`Photo of ${rows}`}>
      <header className="reading__head">
        <h2>Photo of {rows}</h2>
        {reading.status === "read" ? retake : null}
      </header>

      {reading.status === "reading" ? (
        <p className="status status-neutral" role="status">
          Reading your photo…
        </p>
      ) : null}

      {reading.status === "failed" ? (
        <div className="reading__failed" role="alert">
          <p className="status status-danger">{readingReason(reading.reason_code)}</p>
          {retryError ? <p className="status status-danger">{retryError}</p> : null}
          <div className="toolbar">
            <button
              className="button button-primary"
              type="button"
              disabled={retrying}
              aria-busy={retrying}
              onClick={onRetry}
            >
              {retrying ? "Retrying…" : "Retry"}
            </button>
            {retake}
          </div>
        </div>
      ) : null}

      {reading.status === "read" ? (
        <div className="reading__body">
          <ReadingPhoto rigId={rigId} reading={reading} ordered={ordered} />
          <ol className="sightings">
            {ordered.map((s, index) => (
              <SightingItem
                key={s.sighting_id}
                number={index + 1}
                sighting={s}
                decision={decisions[s.sighting_id]}
                clashing={clashing.has(s.sighting_id)}
                correcting={correcting}
                onDecide={(decision) => onDecide(s.sighting_id, decision)}
                onRestore={() => onRestore(s)}
              />
            ))}
          </ol>
        </div>
      ) : null}
    </article>
  );
}

/** The owner's photo, fetched with their session and shown from memory, boxes numbered as the list. */
function ReadingPhoto({
  rigId,
  reading,
  ordered,
}: {
  rigId: number;
  reading: PhotoReading;
  ordered: Sighting[];
}) {
  const [url, setUrl] = useState<string | null>(null);
  const [gone, setGone] = useState(false);

  useEffect(() => {
    let made: string | null = null;
    let live = true;
    photoApi
      .photo(rigId, reading.photo_id)
      .then((response) => {
        if (!live) return;
        made = URL.createObjectURL(response.data);
        setUrl(made);
      })
      .catch(() => live && setGone(true));
    return () => {
      live = false;
      if (made) URL.revokeObjectURL(made);
    };
  }, [rigId, reading.photo_id]);

  if (gone) {
    return (
      <p className="muted reading-photo__gone">
        This photo is no longer kept. The list still holds its reading.
      </p>
    );
  }
  if (!url) return <div className="reading-photo reading-photo--loading" aria-hidden="true" />;
  return (
    <figure className="reading-photo">
      <img src={url} alt="" />
      {ordered.map((s, index) => (
        <span
          key={s.sighting_id}
          className="reading-photo__box"
          data-tone={dispositionTone(s)}
          aria-hidden="true"
          style={{
            left: `${s.box.x * 100}%`,
            top: `${s.box.y * 100}%`,
            width: `${s.box.w * 100}%`,
            height: `${s.box.h * 100}%`,
          }}
        >
          <span className="reading-photo__number">{index + 1}</span>
        </span>
      ))}
      <figcaption className="visually-hidden">
        Your photo, with {ordered.length} numbered boxes. The list beside it holds the same things
        in text.
      </figcaption>
    </figure>
  );
}

function SightingItem({
  number,
  sighting,
  decision,
  clashing,
  correcting,
  onDecide,
  onRestore,
}: {
  number: number;
  sighting: Sighting;
  decision: Decision | undefined;
  clashing: boolean;
  correcting: boolean;
  onDecide: (decision: Decision) => void;
  onRestore: () => void;
}) {
  const words = dispositionWords(sighting);
  const tone = dispositionTone(sighting);
  const position =
    decision && "row" in decision
      ? decision
      : { row: sighting.row_index, startHp: sighting.start_hp };
  const hp = decision?.kind === "keep" ? decision.hp : sighting.hp;
  const keep = (module: {
    module_id: number;
    brand: string | null;
    name: string | null;
    hp: number | null;
  }) =>
    onDecide({
      kind: "keep",
      moduleId: module.module_id,
      label: moduleLabel(module.brand, module.name),
      hp: module.hp ?? sighting.hp,
      row: position.row,
      startHp: position.startHp,
    });
  const out = decision?.kind === "leave_out" || decision?.kind === "not_a_module";
  // With nothing to choose from, the search is the way to name it; otherwise it waits to be asked.
  const [searching, setSearching] = useState(sighting.candidates.length === 0);

  return (
    <li className={`sighting${clashing ? " is-clashing" : ""}${out ? " is-out" : ""}`}>
      <span className="sighting__number">{number}</span>
      <div className="sighting__body">
        <p className="sighting__head">
          <span className={`status-chip status-chip--${tone}`}>{words}</span>
          <strong>{label(sighting, decision)}</strong>
        </p>
        <p className="muted">
          Row {position.row}, HP {position.startHp} to {position.startHp + hp}
        </p>

        {isDecided(sighting) && !out ? (
          <>
            {sighting.candidates.length > 0 ? (
              <fieldset className="sighting__choices">
                <legend className="visually-hidden">Closest matches for {number}</legend>
                {[...sighting.candidates]
                  .sort((a, b) => b.score - a.score)
                  .map((c) => (
                    <label key={c.module_id} className="sighting__choice">
                      <input
                        type="radio"
                        name={`choice-${sighting.sighting_id}`}
                        checked={decision?.kind === "keep" && decision.moduleId === c.module_id}
                        onChange={() => keep(c)}
                      />
                      {moduleLabel(c.brand, c.name)}
                    </label>
                  ))}
              </fieldset>
            ) : null}
            {searching ? (
              <CatalogSearch
                onPick={(module: Module) =>
                  keep({
                    module_id: module.id,
                    brand: module.brand,
                    name: module.name,
                    hp: module.hp,
                  })
                }
              />
            ) : null}
            {correcting ? (
              <div className="toolbar sighting__layout">
                <PositionFields
                  row={position.row}
                  startHp={position.startHp}
                  onChange={(row, startHp) =>
                    onDecide(
                      decision?.kind === "keep"
                        ? { ...decision, row, startHp }
                        : { kind: "undecided", row, startHp },
                    )
                  }
                />
              </div>
            ) : null}
          </>
        ) : null}

        {isDecided(sighting) ? (
          <div className="toolbar sighting__actions">
            {out ? (
              <button className="button button-secondary" type="button" onClick={onRestore}>
                Keep it
              </button>
            ) : (
              <>
                {searching ? null : (
                  <button
                    className="button button-secondary"
                    type="button"
                    onClick={() => setSearching(true)}
                  >
                    Find another Module
                  </button>
                )}
                <button
                  className="button button-secondary"
                  type="button"
                  onClick={() => onDecide({ kind: "leave_out" })}
                >
                  Leave out
                </button>
                <button
                  className="button button-secondary"
                  type="button"
                  onClick={() => onDecide({ kind: "not_a_module" })}
                >
                  Not a Module
                </button>
              </>
            )}
          </div>
        ) : null}
      </div>
    </li>
  );
}

function label(sighting: Sighting, decision: Decision | undefined): string {
  if (sighting.kind === "blank_panel") return "Empty HP";
  if (sighting.kind === "not_eurorack") return "Not part of the Rig";
  if (decision?.kind === "keep") return decision.label;
  if (decision?.kind === "leave_out") return "Left out of the Rig";
  if (decision?.kind === "not_a_module") return "Not a Module";
  return "Choose a Module";
}

function PositionFields({
  row,
  startHp,
  onChange,
}: {
  row: number;
  startHp: number;
  onChange: (row: number, startHp: number) => void;
}) {
  return (
    <>
      <label className="field field--num">
        Row
        <input
          type="number"
          min={0}
          value={row}
          onChange={(event) => onChange(Math.max(0, Number(event.target.value)), startHp)}
        />
      </label>
      <label className="field field--num">
        Start HP
        <input
          type="number"
          min={0}
          value={startHp}
          onChange={(event) => onChange(row, Math.max(0, Number(event.target.value)))}
        />
      </label>
    </>
  );
}

/** A Module the reading missed, at a position the owner chooses. */
function AddModule({ onAdd }: { onAdd: (module: AddedModule) => void }) {
  const [chosen, setChosen] = useState<Module | null>(null);
  const [row, setRow] = useState(0);
  const [startHp, setStartHp] = useState(0);

  return (
    <section className="panel add-module" aria-labelledby="add-module-title">
      <h2 id="add-module-title">Add a Module</h2>
      <p className="muted">For a Module the reading missed.</p>
      <CatalogSearch onPick={setChosen} />
      {chosen ? (
        <p>
          Adding{" "}
          <strong>
            {chosen.brand} {chosen.name}
          </strong>
          , {chosen.hp} HP.
        </p>
      ) : null}
      <div className="toolbar">
        <PositionFields
          row={row}
          startHp={startHp}
          onChange={(r, s) => (setRow(r), setStartHp(s))}
        />
        <button
          className="button button-primary"
          type="button"
          disabled={!chosen}
          onClick={() => {
            if (!chosen) return;
            onAdd({
              moduleId: chosen.id,
              label: `${chosen.brand} ${chosen.name}`,
              hp: chosen.hp,
              row,
              startHp,
            });
            setChosen(null);
          }}
        >
          Add to the Rig
        </button>
      </div>
    </section>
  );
}
