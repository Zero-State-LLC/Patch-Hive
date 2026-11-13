import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import worker from "./index";
import { pageHead, writePageHead } from "./pageHead";

const indexHtml = readFileSync(resolve(__dirname, "../index.html"), "utf8");
const squash = (html: string) => html.replace(/\s+/g, " ").trim();
const block = (html: string) =>
  squash(html.slice(html.indexOf("<!-- page-head -->") + 18, html.indexOf("<!-- /page-head -->")));

const SHELL = `<!doctype html><html><head>
    <!-- page-head -->
    <title>old</title>
    <!-- /page-head -->
    <meta property="og:type" content="website" />
  </head><body><div id=root></div></body></html>`;

const env = (body = SHELL, extra: Record<string, string> = {}) => ({
  ASSETS: {
    fetch: async () =>
      new Response(body, {
        status: 200,
        headers: { "content-type": "text/html", etag: '"shell"', ...extra },
      }),
  },
});

describe("page head", () => {
  it("is what index.html already says for the home page", () => {
    expect(block(indexHtml)).toBe(squash(pageHead("/")));
  });

  it("names no canonical URL for a retired catalog page", () => {
    for (const path of ["/modules", "/products", "/cases", "/cases/eurorack-104"]) {
      expect(pageHead(path)).not.toMatch(/rel="canonical"|og:url/);
    }
  });

  it("names each public page, with its canonical URL", () => {
    const head = pageHead("/privacy");
    expect(head).toContain("<title>Privacy notice, PatchHive</title>");
    expect(head).toContain('<link rel="canonical" href="https://patch-hive.com/privacy" />');
    expect(head).toContain('<meta property="og:url" content="https://patch-hive.com/privacy" />');
    expect(head).toContain('<meta property="og:title" content="Privacy notice, PatchHive" />');
    // The router ignores case and a trailing slash, and the canonical URL is the plain path.
    expect(pageHead("/Patches/")).toContain('href="https://patch-hive.com/patches"');
  });

  it("keeps the home page's words, and names no canonical URL, for any other page", () => {
    for (const path of ["/account", "/rigs/7", "/no-such-page"]) {
      const head = pageHead(path);
      expect(head).toContain("<title>PatchHive, by Zero State</title>");
      expect(head).not.toContain("canonical");
      expect(head).not.toContain("og:url");
    }
  });

  it("writes well-formed attributes", () => {
    expect(pageHead("/privacy")).toContain("content=\"What PatchHive holds about you, where it's");
    expect(pageHead("/privacy")).not.toMatch(/content="[^"]*"[^ />]/);
  });

  it("changes only the marked block, and leaves a shell without one as it is", () => {
    const written = writePageHead(SHELL, "/patches");
    expect(written).toContain("<title>Patches, PatchHive</title>");
    expect(written).not.toContain("<title>old</title>");
    expect(written).toContain('<meta property="og:type" content="website" />');
    expect(writePageHead("<html><title>x</title></html>", "/patches")).toBe(
      "<html><title>x</title></html>",
    );
  });
});

describe("edge worker page head", () => {
  it("serves each public page with its own head, and drops the shell's ETag", async () => {
    const res = await worker.fetch(new Request("https://patch-hive.com/privacy"), env());
    expect(res.status).toBe(200);
    expect(res.headers.get("etag")).toBeNull();
    const html = await res.text();
    expect(html).toContain("<title>Privacy notice, PatchHive</title>");
    expect(html).toContain('href="https://patch-hive.com/privacy"');
  });

  it("names no canonical URL on a signed-in screen or an unknown page", async () => {
    const account = await worker.fetch(new Request("https://patch-hive.com/account"), env());
    expect(account.status).toBe(200);
    expect(await account.text()).not.toContain("canonical");

    const missing = await worker.fetch(new Request("https://patch-hive.com/no-such-page"), env());
    expect(missing.status).toBe(404);
    const html = await missing.text();
    expect(html).toContain("id=root");
    expect(html).not.toContain("canonical");
  });

  it("serves the real index.html with the home page's head", async () => {
    const res = await worker.fetch(new Request("https://patch-hive.com/"), env(indexHtml));
    expect(block(await res.text())).toBe(block(indexHtml));
  });
});
