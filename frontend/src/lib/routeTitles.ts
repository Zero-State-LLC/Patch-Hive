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
  ["/rigs/new/photo", "Photograph your Rig"],
  ["/rigs/:rigId/photo", "Add a photo"],
  ["/rigs/:rigId/reading", "Check the reading"],
  ["/rigs/:rigId/patchbook-studio", "Patch book style"],
  ["/rigs/:rigId/patches/:patchId", "Patch"],
  ["/rigs/:rigId", "Rig workspace"],
  ["/patches", "Patches"],
  ["/login", "Sign in"],
  ["/account", "Account"],
  ["/privacy", "Privacy notice"],
  ["/admin/users", "Admin users"],
  ["/admin/modules", "Admin modules"],
  ["/admin/gallery", "Admin gallery"],
  ["/admin/runs", "Admin runs"],
  ["/admin/exports", "Admin exports"],
  ["/admin/invites", "Admin invites"],
  ["/admin/leaderboards", "Admin leaderboards"],
  ["/admin", "Admin"],
];

export function titleFor(pathname: string): string {
  if (pathname === "/") return HOME_TITLE;
  const match = ROUTE_TITLES.find(([pattern]) => matchPath(pattern, pathname));
  return `${match ? match[1] : "Not found"}, PatchHive`;
}
