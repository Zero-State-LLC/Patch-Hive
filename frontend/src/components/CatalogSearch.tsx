/**
 * CatalogSearch — find a catalog Module by maker and name, to fix a misread one or add one
 * the reading missed (spec 009). It asks once the typing pauses, and only the latest answer
 * may show.
 */
import { useEffect, useId, useRef, useState } from "react";
import { moduleApi } from "@/lib/api";
import { useDebouncedValue } from "@/lib/useDebouncedValue";
import type { Module } from "@/types/api";

const RESULTS = 8;

export default function CatalogSearch({ onPick }: { onPick: (module: Module) => void }) {
  const id = useId();
  const [query, setQuery] = useState("");
  const settled = useDebouncedValue(query.trim());
  const [results, setResults] = useState<Module[]>([]);
  const [state, setState] = useState<"idle" | "searching" | "done" | "error">("idle");
  const request = useRef(0);

  useEffect(() => {
    const mine = ++request.current;
    if (settled.length < 2) {
      setResults([]);
      setState("idle");
      return;
    }
    setState("searching");
    moduleApi
      .list({ q: settled, limit: RESULTS })
      .then((response) => {
        if (mine !== request.current) return;
        setResults(response.data.modules ?? []);
        setState("done");
      })
      .catch(() => {
        if (mine === request.current) setState("error");
      });
  }, [settled]);

  return (
    <div className="catalog-search">
      <label className="field" htmlFor={id}>
        Search the catalog
        <input
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
        {state === "done" && results.length === 0 ? "No Module matches that." : null}
      </p>
      {results.length > 0 ? (
        <ul className="catalog-search__results">
          {results.map((module) => (
            <li key={module.id}>
              <button
                className="button button-secondary"
                type="button"
                onClick={() => {
                  onPick(module);
                  setQuery("");
                }}
              >
                <span className="visually-hidden">Use </span>
                {module.brand} {module.name}{" "}
                <span className="catalog-search__hp">{module.hp} HP</span>
              </button>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
