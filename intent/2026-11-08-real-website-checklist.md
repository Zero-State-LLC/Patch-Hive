# Intent

## Problem

On 2026-11-08 the owner (Zero State LLC) asked that every Zero State website meet a 12-item "real website" checklist: custom 404, a call to action above the fold, a title and description per page, an Open Graph image, a full favicon set, robots.txt, sitemap.xml, alt text, loading states, a privacy policy and analytics. That request is the owner's acceptance for this work.

An audit of `patch-hive.com` against the list found these gaps:

- Crawlers and link previews run no script, so every page reads as the home page to them, and there are no Open Graph or Twitter tags, no image and no canonical URL.
- Only `favicon.svg` exists: no `favicon.ico`, no Apple touch icon, no web app manifest.
- Screens set a title but never a description.
- The sitemap leaves out `/privacy`, and robots.txt lets crawlers into owner-only screens (new rig, placement, photo, reading, Style Studio).
- Most admin screens show nothing while they load and nothing when a load fails, and their buttons can be pressed again while a change is in flight. Style Studio's saved-recipe list reads "No server recipes yet" while it loads.
- Nothing guards that every `<img>` keeps an `alt` attribute.

## Proposed outcome

- The edge worker writes each public page's title, description, canonical URL and Open Graph title, description and URL into the page it serves. Other pages keep the home page's words and name no canonical URL. The app keeps the same tags in step on every screen change.
- `index.html` carries the Open Graph and Twitter card tags, with a 1200x630 image made from existing brand assets.
- A favicon set derived from `favicon.svg`: `favicon.ico` (16, 32, 48), `apple-touch-icon.png` (180), `icon-192.png`, `icon-512.png` and `site.webmanifest`.
- The sitemap lists every public page; robots.txt keeps crawlers out of owner-only screens.
- Each admin screen shows a skeleton while it loads and a failure with Retry, and its buttons wait while a change is in flight. Style Studio shows a skeleton while saved recipes load. The catalog sync buttons on the rig builder wait while they run.
- A test fails if any `<img>` in the app has no `alt`.

Out of scope: any backend change, new product copy or claims, a new mark or logo, a new analytics tool, the privacy notice's text, server-side rendering, per-rig link previews, and deploying.

## Affected users / systems

Visitors, search engines and link previews; admins. `frontend/index.html`, `frontend/public`, `frontend/worker`, `frontend/src` (route meta, `RouteEffects`, admin screens, Style Studio, rig builder steps).

## Constraints / non-goals

Copy comes from what the pages already say. Images come from `frontend/public/favicon.svg`, `frontend/public/brand/splash/splash-hero.jpg` and the colours and faces in `design.md`. The CSP stays as it is: `default-src 'self'` already covers the manifest and icons, and the Cloudflare Web Analytics beacon is already allowed. Fail closed: if the page-head markers are missing, the worker serves the page unchanged.

## Open questions

- Should `/racks` (public rigs, signed out) or individual public rigs join the sitemap? Owner decides; this change lists only `/`, `/patches` and `/privacy`.
- A shared public rig or patch still previews with the home page's words; per-rig previews would need the worker to call the API.
- Crawlers that run no script still see an empty page body; only the head changes.

## Verified / assumed claims

| Claim | Label | Basis |
|---|---|---|
| The worker already answers 404 for paths outside `APP_ROUTES`, with the in-app not-found page | `OBSERVED` | `frontend/worker/index.ts`, `frontend/worker/routes.test.ts` |
| Signed out, the home page shows "Photograph your Rig" above the fold at 390x844 and 1440x900 | `OBSERVED` | Playwright against `vite preview` of the production build, refresh call answered 401 |
| Rigs and patches marked public can be read signed out | `OBSERVED` | `backend/racks/access.py` `readable_racks`, `backend/patches/routes.py` `list_patches` |
| The privacy notice names Cloudflare's Web Analytics script | `OBSERVED` | `frontend/src/pages/Privacy.tsx` |
| The CSP allows the analytics beacon (`script-src static.cloudflareinsights.com`, `connect-src cloudflareinsights.com`) | `OBSERVED` | `frontend/worker/headers.ts`, `frontend/worker/headers.test.ts` |
| Cloudflare serves `.webmanifest` as `application/manifest+json` | `INFERRED` | Workers static assets content types; not checked on a deploy |
| How each social network renders the preview | `NOT_COMPUTABLE` | Needs a deploy and the networks' own validators |

## Author / date

- Author: Claude Code, for the owner's request of 2026-11-08
- Date: 2026-11-08
