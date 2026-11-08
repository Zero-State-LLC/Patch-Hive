// Edge entry for the static SPA: canonicalize www to the apex, then serve assets.
// Missing files and unknown routes answer 404 (the SPA shell still renders its
// not-found page for unknown routes); only real client routes fall back to the shell.
// Every shell carries the head written for its page (pageHead.ts).
import { securityHeaders } from "./headers";
import { writePageHead } from "./pageHead";
import { isAppRoute, isRetired, looksLikeFile } from "./routes";

interface Env {
  ASSETS: { fetch(request: Request): Promise<Response> };
}

// Hosts that must stay out of search results.
const NOINDEX_HOSTS = new Set(["staging.patch-hive.com"]);

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const res = await serve(request, env);
    if (res.status >= 300 && res.status < 400) {
      return res; // redirects carry no page
    }
    const hostname = new URL(request.url).hostname;
    const headers = new Headers(res.headers);
    for (const [name, value] of Object.entries(securityHeaders(hostname))) {
      headers.set(name, value);
    }
    if (NOINDEX_HOSTS.has(hostname)) {
      headers.set("X-Robots-Tag", "noindex, nofollow");
    }
    return new Response(res.body, { status: res.status, statusText: res.statusText, headers });
  },
};

async function serve(request: Request, env: Env): Promise<Response> {
  const url = new URL(request.url);
  if (isRetired(url.pathname)) {
    // Straight to the apex home page, even from www: one hop, not two.
    const host = url.hostname === "www.patch-hive.com" ? "https://patch-hive.com" : url.origin;
    return Response.redirect(`${host}/`, 301);
  }
  if (url.hostname === "www.patch-hive.com") {
    url.hostname = "patch-hive.com";
    return Response.redirect(url.toString(), 301);
  }
  const res = await env.ASSETS.fetch(request);
  const html = (res.headers.get("content-type") ?? "").startsWith("text/html");
  if (!html || url.pathname.endsWith(".html")) {
    return res;
  }
  // With SPA fallback on, a missing asset comes back as the index page.
  const page = isAppRoute(url.pathname);
  if (!page && looksLikeFile(url.pathname)) {
    return new Response("Not found\n", {
      status: 404,
      headers: { "content-type": "text/plain; charset=utf-8" },
    });
  }
  return withPageHead(res, url.pathname, page ? res.status : 404);
}

// The shell with its head written for this page. Only a full body is rewritten, and the result
// is no longer the file its ETag names, so the ETag and length go with it.
async function withPageHead(res: Response, pathname: string, status: number): Promise<Response> {
  if (res.status !== 200) {
    return new Response(res.body, { status, headers: res.headers });
  }
  const headers = new Headers(res.headers);
  headers.delete("content-length");
  headers.delete("etag");
  return new Response(writePageHead(await res.text(), pathname), { status, headers });
}
