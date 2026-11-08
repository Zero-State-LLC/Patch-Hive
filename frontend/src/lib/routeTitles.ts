/**
 * Document titles and descriptions per route, so tabs, history, screen readers and search results
 * name the screen. The public pages take theirs from pageMeta.ts, which the edge worker also
 * writes into the page it serves; only they name a canonical URL. Other patterns are tried in
 * order; a path that matches none is the not-found screen.
 */
import { matchPath } from "react-router-dom";
import { PUBLIC_PAGES, SITE_ORIGIN, publicPath } from "./pageMeta";

const ROUTE_TITLES: [pattern: string, title: string, description: string][] = [
  ["/racks/new", "New rig", "Choose a case, create the rig, then place its modules."],
  ["/racks/:id/edit", "Place modules", "Choose a case, create the rig, then place its modules."],
  ["/racks/:rigId", "Rigs", "Rig-centric workspace. Each rig carries runs and patch libraries."],
  ["/racks", "Rigs", "Rig-centric workspace. Each rig carries runs and patch libraries."],
  [
    "/rigs/new/photo",
    "Photograph your Rig",
    "PatchHive reads every Module in the photo. Nothing joins your Rig until you confirm it.",
  ],
  [
    "/rigs/:rigId/photo",
    "Add a photo",
    "PatchHive reads every Module in the photo. Nothing joins your Rig until you confirm it.",
  ],
  [
    "/rigs/:rigId/reading",
    "Check the reading",
    "Fix anything PatchHive got wrong, then confirm. Nothing joins your Rig until you do.",
  ],
  [
    "/rigs/:rigId/patchbook-studio",
    "Patch book style",
    "Deterministic publishing instrument, presentation only. Canonical patch data is never mutated.",
  ],
  [
    "/rigs/:rigId/patches/:patchId",
    "Patch",
    "One patch on its rig's rail, with its cable table and your notes.",
  ],
  ["/rigs/:rigId", "Rig workspace", "Pick a revision, review its runs, keep notes on its patches."],
  ["/login", "Sign in", "Confirm your rig, generate patches it can play, and export the book."],
  [
    "/account",
    "Account",
    "PatchHive is free to explore. You only pay when you export something you want to keep.",
  ],
  ["/admin/users", "Admin users", "Role changes and credit grants require an audit reason."],
  [
    "/admin/modules",
    "Admin modules",
    "Deprecate, tombstone, or merge catalog modules. No hard deletes.",
  ],
  ["/admin/gallery", "Admin gallery", "Approve or confirm gallery inventory evidence."],
  ["/admin/runs", "Admin runs", "Generation runs bound to rig revisions and seeds."],
  [
    "/admin/exports",
    "Admin exports",
    "Grant, revoke or clear export access, each change logged with a reason.",
  ],
  [
    "/admin/leaderboards",
    "Admin leaderboards",
    "Community ranking surfaces when feature flags allow.",
  ],
  ["/admin", "Admin", "Users, catalog, gallery, runs and exports. Each change logs a reason."],
];

const NOT_FOUND_DESCRIPTION =
  "The route you requested has been disconnected or never existed in this hive.";

export interface RouteMeta {
  title: string;
  description: string;
  /** The page's canonical URL; only public pages name one. */
  canonical: string | null;
}

export function metaFor(pathname: string): RouteMeta {
  const page = publicPath(pathname);
  if (page) return { ...PUBLIC_PAGES[page], canonical: `${SITE_ORIGIN}${page}` };
  const match = ROUTE_TITLES.find(([pattern]) => matchPath(pattern, pathname));
  return {
    title: `${match ? match[1] : "Not found"}, PatchHive`,
    description: match ? match[2] : NOT_FOUND_DESCRIPTION,
    canonical: null,
  };
}

export function titleFor(pathname: string): string {
  return metaFor(pathname).title;
}
