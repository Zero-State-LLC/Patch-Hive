/**
 * Home — PatchHive brand-first fold (Cyber Hive / Zero State).
 * Spec 009: a photo of the Rig in, a Patch Book out, so the one main action is "Photograph your
 * Rig". Beside it, the product itself: a real rig on its rail with one patch's cables, then an
 * example reading of the same rig and the path from photo to book. The rig is the golden demo
 * seed, drawn by the workbench's own rail; nothing here calls the API.
 */
import { Link } from "react-router-dom";
import PatchRail from "@/components/PatchRail";
import { ACCOUNTS_OPEN } from "@/lib/apiBase";
import { DEMO_PATCH, DEMO_RIG, DEMO_RUN_PATCH_COUNT } from "@/lib/demoRig";
import { useAuthStore } from "@/lib/store";

const path = [
  {
    title: "Photograph the Rig",
    detail: "One photo of the whole Rig, or one per row for a big Case.",
  },
  {
    title: "Check the reading",
    detail: "Fix anything PatchHive got wrong. Nothing joins the Rig until you confirm it.",
  },
  {
    title: "Export the book",
    detail: "A PDF Patch Book of patches made from your Rig. Credits are spent only on export.",
  },
] as const;

const PHOTO_STEP = "/rigs/new/photo";

// An example reading of the demo rig's first Modules, in the words the Reading screen uses and
// in its order: the one to check first, then the rest by row and HP.
const EXAMPLE_WORDS = ["Sure", "Check this", "Sure"] as const;
const example = DEMO_RIG.modules
  .slice(0, EXAMPLE_WORDS.length)
  .map((placed, index) => ({
    words: EXAMPLE_WORDS[index],
    name: `${placed.module?.brand ?? ""} ${placed.module?.name ?? ""}`.trim(),
    row: placed.row_index,
    from: placed.start_hp,
    to: placed.start_hp + (placed.module?.hp ?? 0),
  }))
  .sort(
    (a, b) =>
      Number(a.words === "Sure") - Number(b.words === "Sure") || a.row - b.row || a.from - b.from,
  );

// The demo patch's own page of the book, as the export prints it: page 9 of PatchBook.pdf in the
// seeded run's pack (composition 17b4977023a6, engine 0.3.0), rendered at 1000px wide. Re-make it
// when the seed, the patch engine or the book's layout change: export the seeded run in-process
// (as backend/tests/integration/test_008_f5_live.py does), find the patch's page in the pack's
// pages/json, render that page of PatchBook.pdf, and save it as WebP.
const BOOK_PAGE = "/examples/patch-book-page.webp";
const BOOK_PAGE_ALT = `A Patch Book page titled ${DEMO_PATCH.name}: its cable diagram, the five cables in order, seven steps to play it, and a note that one Module's jack names are generic.`;

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
            <h1 className="home-headline">A photo of your Rig in. A Patch Book out.</h1>
            <div className="home-cta">
              {isAuthenticated() ? (
                <>
                  <Link className="button button-primary" to={PHOTO_STEP}>
                    Photograph your Rig
                  </Link>
                  <Link className="button button-secondary" to="/racks">
                    My Rigs
                  </Link>
                </>
              ) : (
                <Link
                  className="button button-primary"
                  to="/login"
                  state={ACCOUNTS_OPEN ? { from: PHOTO_STEP } : undefined}
                >
                  Photograph your Rig
                </Link>
              )}
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

      <section className="home-example" aria-labelledby="home-example-title">
        <h2 id="home-example-title">What you get</h2>
        <div className="home-example__parts">
          <div>
            <h3>A reading of the Rig</h3>
            <ol className="home-example__list" aria-label="An example reading">
              {example.map((item) => (
                <li key={item.name}>
                  <span
                    className={`status-chip status-chip--${item.words === "Sure" ? "success" : "warning"}`}
                  >
                    {item.words}
                  </span>{" "}
                  {item.name}, row {item.row}, HP {item.from} to {item.to}
                </li>
              ))}
            </ol>
          </div>
          <figure className="home-example__page" aria-labelledby="home-example-page">
            <img
              src={BOOK_PAGE}
              alt={BOOK_PAGE_ALT}
              width={1000}
              height={1294}
              loading="lazy"
              decoding="async"
            />
            <figcaption id="home-example-page">
              A page of this Rig&apos;s Patch Book, as the export prints it: {DEMO_PATCH.name}.
            </figcaption>
          </figure>
        </div>
      </section>

      <section className="home-path" aria-labelledby="home-path-title">
        <h2 id="home-path-title">From photo to book</h2>
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
