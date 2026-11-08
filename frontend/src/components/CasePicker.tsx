/**
 * CasePicker — name the Rig's Case from the catalog, if the owner knows it (spec 009 story 23).
 * Its rows then set each row's width, and confirming refuses a Module past a row's end. Without
 * one, each row is as wide as the Modules on it. It asks once the typing pauses, and only the
 * latest answer may show.
 */
import { useEffect, useId, useRef, useState } from "react";
import { caseApi } from "@/lib/api";
import { useDebouncedValue } from "@/lib/useDebouncedValue";
import type { Case } from "@/types/api";

const RESULTS = 8;

/** "84 HP" or "rows of 104 + 104 HP", as a Case states its rows. */
const caseRows = (c: Pick<Case, "hp_per_row" | "total_hp">) =>
  c.hp_per_row?.length > 1 ? `rows of ${c.hp_per_row.join(" + ")} HP` : `${c.total_hp} HP`;

export default function CasePicker({
  current,
  chosen,
  onChoose,
}: {
  /** The Case the Rig has now, if any. */
  current: Pick<Case, "brand" | "name" | "hp_per_row" | "total_hp"> | null;
  chosen: Case | null;
  onChoose: (chosen: Case | null) => void;
}) {
  const id = useId();
  const [searching, setSearching] = useState(false);
  const [query, setQuery] = useState("");
  const settled = useDebouncedValue(query.trim());
  const [results, setResults] = useState<Case[]>([]);
  const [state, setState] = useState<"idle" | "searching" | "done" | "error">("idle");
  const request = useRef(0);
  // Each step swaps out the control that was pressed, so focus follows: into the search when it
  // opens, and back to the button that opens it once a Case is chosen or the search is closed.
  const searchRef = useRef<HTMLInputElement>(null);
  const openRef = useRef<HTMLButtonElement>(null);
  const opened = useRef(false);

  useEffect(() => {
    if (searching) searchRef.current?.focus();
    else if (opened.current) openRef.current?.focus();
    opened.current = searching;
  }, [searching]);

  useEffect(() => {
    const mine = ++request.current;
    if (settled.length < 2) {
      setResults([]);
      setState("idle");
      return;
    }
    setState("searching");
    caseApi
      .list({ q: settled, limit: RESULTS, format_family: "Eurorack" })
      .then((response) => {
        if (mine !== request.current) return;
        setResults(response.data.cases ?? []);
        setState("done");
      })
      .catch(() => {
        if (mine === request.current) setState("error");
      });
  }, [settled]);

  const shown = chosen ?? current;
  return (
    <section className="case-picker" aria-labelledby={`${id}-title`}>
      <h3 id={`${id}-title`}>Your Case</h3>
      <p className="muted" role="status">
        {shown
          ? `${shown.brand} ${shown.name}, ${caseRows(shown)}.`
          : "No Case named, so each row is as wide as the Modules on it."}
      </p>
      {!searching ? (
        <div className="toolbar">
          <button
            ref={openRef}
            className="button button-quiet"
            type="button"
            onClick={() => setSearching(true)}
          >
            {shown ? "Name a different Case" : "Name your Case"}
          </button>
          {chosen ? (
            <button className="button button-quiet" type="button" onClick={() => onChoose(null)}>
              {current ? "Keep the Rig's Case" : "Go on without one"}
            </button>
          ) : null}
        </div>
      ) : (
        <div className="catalog-search">
          <label className="field" htmlFor={id}>
            Search Cases
            <input
              ref={searchRef}
              id={id}
              type="search"
              maxLength={100}
              value={query}
              placeholder="Maker and name"
              autoComplete="off"
              onChange={(event) => setQuery(event.target.value)}
            />
          </label>
          <p className="muted catalog-search__state" role="status">
            {state === "searching" ? "Searching…" : null}
            {state === "error" ? "The catalog didn't answer. Try again." : null}
            {state === "done" && results.length === 0 ? "No Case matches that." : null}
          </p>
          {results.length > 0 ? (
            <ul className="catalog-search__results">
              {results.map((c) => (
                <li key={c.id}>
                  <button
                    className="button button-secondary"
                    type="button"
                    onClick={() => {
                      onChoose(c);
                      setQuery("");
                      setSearching(false);
                    }}
                  >
                    <span className="visually-hidden">Use </span>
                    {c.brand} {c.name} <span className="catalog-search__hp">{caseRows(c)}</span>
                  </button>
                </li>
              ))}
            </ul>
          ) : null}
          <button
            className="button button-quiet"
            type="button"
            onClick={() => {
              setQuery("");
              setSearching(false);
            }}
          >
            Cancel
          </button>
        </div>
      )}
    </section>
  );
}
