/**
 * Home — PatchHive brand-first fold (Cyber Hive / Zero State).
 * Hallmark: the brand beside the product itself, a real rig on its rail with one patch's cables,
 * then the path from rig to book. The rig is the golden demo seed, drawn by the workbench's own
 * rail; nothing here calls the API.
 */
import { Link } from "react-router-dom";
import PatchRail from "@/components/PatchRail";
import { ACCOUNTS_OPEN } from "@/lib/apiBase";
import { DEMO_PATCH, DEMO_RIG, DEMO_RUN_PATCH_COUNT } from "@/lib/demoRig";
import { useAuthStore } from "@/lib/store";

const path = [
  {
    title: "Confirm the rig",
    detail: "Place modules by hand or from a photo. Nothing joins the rig until you confirm it.",
  },
  {
    title: "Generate patches",
    detail: "Patches use only the modules you confirmed. The same rig gives the same patches.",
  },
  {
    title: "Export the book",
    detail: "A PDF patch book of your patches. Credits are spent only on export.",
  },
] as const;

const SIGNAL_NAMES = { audio: "Audio", cv: "CV", gate: "Gate" } as const;
const signals = (Object.keys(SIGNAL_NAMES) as (keyof typeof SIGNAL_NAMES)[]).filter((signal) =>
  DEMO_PATCH.connections.some((c) => c.cable_type === signal),
);

export default function Home() {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);

  return (
    <div className="home">
      <section className="home-hero" aria-labelledby="home-brand">
        <div className="home-hero__content">
          <div className="home-hero__copy">
            <p className="home-brand" id="home-brand">
              PatchHive
            </p>
            <h1 className="home-headline">Confirm the rig. Export the book.</h1>
            <div className="home-cta">
              {isAuthenticated() ? (
                <Link className="button button-primary" to="/racks">
                  Open rigs
                </Link>
              ) : ACCOUNTS_OPEN ? (
                <Link className="button button-primary" to="/login">
                  Sign in
                </Link>
              ) : null}
              <Link
                className={`button ${ACCOUNTS_OPEN ? "button-secondary" : "button-primary"}`}
                to="/modules?hp=known"
              >
                Placeable modules
              </Link>
            </div>
          </div>

          <figure className="home-rig">
            <PatchRail rack={DEMO_RIG} patch={DEMO_PATCH} table={false} />
            <figcaption className="home-rig__caption">
              <p>
                <strong>{DEMO_PATCH.name}</strong>: {DEMO_PATCH.description}, one of{" "}
                {DEMO_RUN_PATCH_COUNT} patches generated for this rig.
              </p>
              <ul className="home-rig__key" aria-label="Cable key">
                {signals.map((signal) => (
                  <li key={signal}>
                    <span className={`cable-swatch cable-${signal}`} aria-hidden="true" />
                    {SIGNAL_NAMES[signal]}
                  </li>
                ))}
              </ul>
            </figcaption>
          </figure>
        </div>
      </section>

      <section className="home-path" aria-labelledby="home-path-title">
        <h2 id="home-path-title">From rig to book</h2>
        <ol className="signal-chain">
          {path.map((step) => (
            <li key={step.title} className="signal-chain__stage" data-state="done">
              <span className="signal-chain__jack" aria-hidden="true" />
              <strong className="signal-chain__title">{step.title}</strong>
              <span className="signal-chain__detail">{step.detail}</span>
            </li>
          ))}
        </ol>
      </section>
    </div>
  );
}
