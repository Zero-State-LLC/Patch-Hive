// The page head, written per page at the edge. Crawlers and link previews run no script, so
// without this every page would read to them as the home page. Only the block between the
// page-head markers in index.html changes; a shell without them is served as it is.
import { PUBLIC_PAGES, SITE_ORIGIN, publicPath } from "../src/lib/pageMeta";

const START = "<!-- page-head -->";
const END = "<!-- /page-head -->";
const INDENT = "\n    ";

const escapeHtml = (text: string) =>
  text.replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

/** A public page's own tags; any other page keeps the home page's words and names no canonical URL. */
export function pageHead(pathname: string): string {
  const path = publicPath(pathname);
  const title = escapeHtml(PUBLIC_PAGES[path ?? "/"].title);
  const description = escapeHtml(PUBLIC_PAGES[path ?? "/"].description);
  const url = path ? `${SITE_ORIGIN}${path}` : null;
  return [
    `<title>${title}</title>`,
    `<meta name="description" content="${description}" />`,
    ...(url ? [`<link rel="canonical" href="${url}" />`] : []),
    `<meta property="og:title" content="${title}" />`,
    `<meta property="og:description" content="${description}" />`,
    ...(url ? [`<meta property="og:url" content="${url}" />`] : []),
  ].join(INDENT);
}

export function writePageHead(html: string, pathname: string): string {
  const start = html.indexOf(START);
  const end = start < 0 ? -1 : html.indexOf(END, start);
  if (end < 0) return html;
  return `${html.slice(0, start + START.length)}${INDENT}${pageHead(pathname)}${INDENT}${html.slice(end)}`;
}
