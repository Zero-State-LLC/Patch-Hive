import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import worker from "./index";
import { APP_ROUTES, isAppRoute, looksLikeFile } from "./routes";

const appTsx = readFileSync(resolve(__dirname, "../src/App.tsx"), "utf8");

describe("edge routes", () => {
  it("mirrors every client route in App.tsx", () => {
    const declared = [...appTsx.matchAll(/<Route path="([^"]+)"/g)]
      .map((m) => m[1])
      .filter((p) => p !== "*");
    expect([...APP_ROUTES].sort()).toEqual(declared.sort());
  });

  it("matches client routes with parameters", () => {
    expect(isAppRoute("/cases/eurorack-104")).toBe(true);
    expect(isAppRoute("/racks/12/edit")).toBe(true);
    expect(isAppRoute("/racks/12/edit/x")).toBe(false);
    expect(isAppRoute("/privacy")).toBe(false);
  });

  it("tells files from pages", () => {
    expect(looksLikeFile("/robots.txt")).toBe(true);
    expect(looksLikeFile("/vite.svg")).toBe(true);
    expect(looksLikeFile("/cases/eurorack-104")).toBe(false);
  });
});

const shell = () =>
  new Response("<!doctype html><div id=root></div>", {
    status: 200,
    headers: { "content-type": "text/html" },
  });

const env = (asset?: Response) => ({ ASSETS: { fetch: async () => asset ?? shell() } });

describe("edge worker", () => {
  it("serves the shell with 200 for a client route", async () => {
    const res = await worker.fetch(new Request("https://patch-hive.com/modules"), env());
    expect(res.status).toBe(200);
  });

  it("answers 404 with the shell for an unknown page", async () => {
    const res = await worker.fetch(new Request("https://patch-hive.com/privacy"), env());
    expect(res.status).toBe(404);
    expect(await res.text()).toContain("id=root");
  });

  it("answers a plain 404 for a missing file", async () => {
    const res = await worker.fetch(new Request("https://patch-hive.com/vite.svg"), env());
    expect(res.status).toBe(404);
    expect(res.headers.get("content-type")).toContain("text/plain");
  });

  it("passes real files through", async () => {
    const txt = new Response("User-agent: *\n", {
      status: 200,
      headers: { "content-type": "text/plain" },
    });
    const res = await worker.fetch(new Request("https://patch-hive.com/robots.txt"), env(txt));
    expect(res.status).toBe(200);
  });

  it("redirects www to the apex", async () => {
    const res = await worker.fetch(new Request("https://www.patch-hive.com/cases"), env());
    expect(res.status).toBe(301);
    expect(res.headers.get("location")).toBe("https://patch-hive.com/cases");
  });
});
