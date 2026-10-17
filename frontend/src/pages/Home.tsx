/**
 * Home — PatchHive brand-first fold (Cyber Hive / Zero State).
 * Hallmark: full-bleed hero, no feature-card grid, brand as hero signal.
 */
import { Link } from "react-router-dom";
import { useAuthStore } from "@/lib/store";

const laws = [
  "Vision output is evidence only — never silent inventory truth",
  "Immutable rig revisions and deterministic generation seeds",
  "Signal types describe ports and cables, not DSP",
  "Credits debit only at the canonical export boundary",
] as const;

export default function Home() {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);

  return (
    <div className="home">
      <section className="home-hero" aria-labelledby="home-brand">
        <div className="home-hero__media" aria-hidden="true" />
        <div className="home-hero__veil" aria-hidden="true" />
        <div className="home-hero__content">
          <p className="home-brand" id="home-brand">
            PatchHive
          </p>
          <h1 className="home-headline">Confirm the rig. Export the book.</h1>
          <p className="home-lede">
            Eurorack patch documentation without invented inventory, audio simulation, or hardware
            control.
          </p>
          <div className="home-cta">
            {isAuthenticated() ? (
              <Link className="button button-primary" to="/racks">
                Open rigs
              </Link>
            ) : (
              <Link className="button button-primary" to="/login">
                Sign in
              </Link>
            )}
            <Link className="button button-secondary" to="/modules?hp=known">
              Placeable modules
            </Link>
            <Link className="button button-quiet" to="/racks/new">
              New rig
            </Link>
          </div>
        </div>
      </section>

      <section className="home-laws" aria-labelledby="home-laws-title">
        <p className="eyebrow">Product law</p>
        <h2 id="home-laws-title">Boundaries that stay hard</h2>
        <ol className="home-laws__list">
          {laws.map((law) => (
            <li key={law}>{law}</li>
          ))}
        </ol>
      </section>
    </div>
  );
}
