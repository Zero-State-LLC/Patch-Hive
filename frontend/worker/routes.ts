// Client routes the SPA renders (mirrors <Routes> in src/App.tsx; a test keeps them in step).
// Anything else gets a real 404 so the site never answers every path with 200.
export const APP_ROUTES = [
  "/",
  "/modules",
  "/cases",
  "/cases/:slug",
  "/racks",
  "/racks/new",
  "/racks/:id/edit",
  "/rigs/:rigId",
  "/rigs/:rigId/patchbook-studio",
  "/patches",
  "/products",
  "/login",
  "/account",
  "/admin",
  "/admin/users",
  "/admin/modules",
  "/admin/gallery",
  "/admin/runs",
  "/admin/exports",
] as const;

const MATCHERS = APP_ROUTES.map(
  (route) => new RegExp(`^${route.replace(/:[A-Za-z]+/g, "[^/]+")}/?$`),
);

export function isAppRoute(pathname: string): boolean {
  return MATCHERS.some((re) => re.test(pathname));
}

// A path whose last segment has an extension asks for a file, never a page.
export function looksLikeFile(pathname: string): boolean {
  return /\.[A-Za-z0-9]+$/.test(pathname.split("/").pop() ?? "");
}
