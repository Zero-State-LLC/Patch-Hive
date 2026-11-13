// Client routes the SPA renders (mirrors <Routes> in src/App.tsx; a test keeps them in step).
// Anything else gets a real 404 so the site never answers every path with 200.
export const APP_ROUTES = [
  "/",
  "/racks",
  "/racks/new",
  "/racks/:id/edit",
  "/racks/:rigId",
  "/rigs/new/photo",
  "/rigs/:rigId/photo",
  "/rigs/:rigId/reading",
  "/rigs/:rigId",
  "/rigs/:rigId/patchbook-studio",
  "/rigs/:rigId/patches/:patchId",
  "/patches",
  "/login",
  "/account",
  "/privacy",
  "/admin",
  "/admin/users",
  "/admin/invites",
  "/admin/modules",
  "/admin/gallery",
  "/admin/runs",
  "/admin/exports",
  "/admin/leaderboards",
] as const;

// The catalog pages left the public routes (spec 009, decision 58). An old link to one lands
// on the home page, for good, so it still leads somewhere useful.
export const RETIRED_ROUTES = ["/modules", "/products", "/cases", "/cases/:slug"] as const;

const matchers = (routes: readonly string[]) =>
  routes.map((route) => new RegExp(`^${route.replace(/:[A-Za-z]+/g, "[^/]+")}/?$`));
const MATCHERS = matchers(APP_ROUTES);
const RETIRED = matchers(RETIRED_ROUTES);

export function isAppRoute(pathname: string): boolean {
  return MATCHERS.some((re) => re.test(pathname));
}

export function isRetired(pathname: string): boolean {
  return RETIRED.some((re) => re.test(pathname));
}

// A path whose last segment has an extension asks for a file, never a page.
export function looksLikeFile(pathname: string): boolean {
  return /\.[A-Za-z0-9]+$/.test(pathname.split("/").pop() ?? "");
}
