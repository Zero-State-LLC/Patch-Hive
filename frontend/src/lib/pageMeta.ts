/**
 * The pages anyone can open signed out, as search engines and link previews should name them.
 * One table for both sides: the app names the screen with it (routeTitles.ts), and the edge
 * worker writes it into the page it serves (worker/pageHead.ts), because crawlers and link
 * previews run no script. public/sitemap.xml lists exactly these paths; a test keeps them in step.
 * No imports: the worker bundles this file.
 */
export const SITE_ORIGIN = "https://patch-hive.com";

export interface PageMeta {
  title: string;
  description: string;
}

export const PUBLIC_PAGES: Readonly<Record<string, PageMeta>> = {
  "/": {
    title: "PatchHive, by Zero State",
    description: "Confirm a Eurorack rig and export its Patch Book, without invented inventory.",
  },
  "/patches": {
    title: "Patches, PatchHive",
    description:
      "Generated patches constrained to confirmed inventory. Exports remain the credit boundary.",
  },
  "/privacy": {
    title: "Privacy notice, PatchHive",
    description:
      "What PatchHive holds about you, where it's kept and what deleting an account does.",
  },
};

/** The public page a path names, ignoring case and a trailing slash as the router does; else null. */
export function publicPath(pathname: string): string | null {
  const path = pathname.length > 1 ? pathname.toLowerCase().replace(/\/$/, "") : pathname;
  return path in PUBLIC_PAGES ? path : null;
}
