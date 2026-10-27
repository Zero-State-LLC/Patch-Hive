// Edge entry for the static SPA: canonicalize www to the apex, then serve assets.
// Missing files and unknown routes answer 404 (the SPA shell still renders its
// not-found page for unknown routes); only real client routes fall back to the shell.
import { isAppRoute, looksLikeFile } from "./routes";

interface Env {
  ASSETS: { fetch(request: Request): Promise<Response> };
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);
    if (url.hostname === "www.patch-hive.com") {
      url.hostname = "patch-hive.com";
      return Response.redirect(url.toString(), 301);
    }
    const res = await env.ASSETS.fetch(request);
    const html = (res.headers.get("content-type") ?? "").startsWith("text/html");
    // With SPA fallback on, a missing asset comes back as the index page.
    if (!html || url.pathname.endsWith(".html") || isAppRoute(url.pathname)) {
      return res;
    }
    if (looksLikeFile(url.pathname)) {
      return new Response("Not found\n", {
        status: 404,
        headers: { "content-type": "text/plain; charset=utf-8" },
      });
    }
    return new Response(res.body, { status: 404, headers: res.headers });
  },
};
