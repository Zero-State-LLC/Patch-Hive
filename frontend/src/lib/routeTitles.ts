/**
 * Document titles per route, so tabs, history and screen readers name the screen.
 * Patterns are tried in order; a path that matches none is the not-found screen.
 */
import { matchPath } from "react-router-dom";

const HOME_TITLE = "PatchHive, by Zero State";

const ROUTE_TITLES: [pattern: string, title: string][] = [
  ["/racks/new", "New rig"],
  ["/racks/:id/edit", "Place modules"],
  ["/racks/:rigId", "Rigs"],
  ["/racks", "Rigs"],
  ["/rigs/:rigId/patchbook-studio", "Patch book style"],
  ["/rigs/:rigId/patches/:patchId", "Patch"],
  ["/rigs/:rigId", "Rig workspace"],
  ["/modules", "Modules"],
  ["/products", "Products"],
  ["/cases/:slug", "Case"],
  ["/cases", "Cases"],
  ["/patches", "Patches"],
  ["/login", "Sign in"],
  ["/account", "Account"],
  ["/admin/users", "Ops users"],
  ["/admin/modules", "Ops modules"],
  ["/admin/gallery", "Ops gallery"],
  ["/admin/runs", "Ops runs"],
  ["/admin/exports", "Ops exports"],
  ["/admin", "Ops"],
];

export function titleFor(pathname: string): string {
  if (pathname === "/") return HOME_TITLE;
  const match = ROUTE_TITLES.find(([pattern]) => matchPath(pattern, pathname));
  return `${match ? match[1] : "Not found"}, PatchHive`;
}
