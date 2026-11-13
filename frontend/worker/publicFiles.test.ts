// The files crawlers, link previews and browsers ask for by name: they exist, say what the
// page head says, and match the routes the app serves.
import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { PUBLIC_PAGES } from "../src/lib/pageMeta";
import { isAppRoute, isRetired } from "./routes";

const publicDir = resolve(__dirname, "../public");
const read = (name: string) => readFileSync(resolve(publicDir, name));
const indexHtml = readFileSync(resolve(__dirname, "../index.html"), "utf8");

/** Width and height from a PNG's IHDR chunk. */
function pngSize(buf: Buffer): [number, number] {
  expect(buf.subarray(1, 4).toString("latin1")).toBe("PNG");
  return [buf.readUInt32BE(16), buf.readUInt32BE(20)];
}

/** Width and height from a JPEG's start-of-frame segment. */
function jpegSize(buf: Buffer): [number, number] {
  let at = 2;
  while (at < buf.length) {
    const marker = buf[at + 1];
    if (marker >= 0xc0 && marker <= 0xc2)
      return [buf.readUInt16BE(at + 7), buf.readUInt16BE(at + 5)];
    at += 2 + buf.readUInt16BE(at + 2);
  }
  throw new Error("no start-of-frame segment");
}

/** Whether a robots.txt rule (prefix, with * for any run of characters) covers a path. */
function blocks(rule: string, path: string): boolean {
  const pattern = rule
    .split("*")
    .map((part) => part.replace(/[.+?^${}()|[\]\\]/g, "\\$&"))
    .join(".*");
  return new RegExp(`^${pattern}`).test(path);
}

const meta = (property: string) =>
  indexHtml.match(new RegExp(`<meta (?:property|name)="${property}" content="([^"]*)"`))?.[1];

describe("sitemap.xml", () => {
  it("lists exactly the public pages, as absolute URLs the app serves", () => {
    const sitemap = read("sitemap.xml").toString("utf8");
    const locs = [...sitemap.matchAll(/<loc>([^<]*)<\/loc>/g)].map((m) => m[1]);
    for (const loc of locs) expect(loc).toMatch(/^https:\/\/patch-hive\.com\//);
    const paths = locs.map((loc) => new URL(loc).pathname);
    expect(paths.sort()).toEqual(Object.keys(PUBLIC_PAGES).sort());
    for (const path of paths) expect(isAppRoute(path)).toBe(true);
  });

  it("offers no retired catalog page as a live one", () => {
    const sitemap = read("sitemap.xml").toString("utf8");
    const locs = [...sitemap.matchAll(/<loc>([^<]*)<\/loc>/g)].map((m) => new URL(m[1]).pathname);
    for (const path of [...locs, ...Object.keys(PUBLIC_PAGES)]) expect(isRetired(path)).toBe(false);
  });
});

describe("robots.txt", () => {
  const robots = read("robots.txt").toString("utf8");
  const rules = [...robots.matchAll(/^Disallow: (\S+)$/gm)].map((m) => m[1]);

  it("points to the sitemap by its absolute URL", () => {
    expect(robots).toMatch(/^Sitemap: https:\/\/patch-hive\.com\/sitemap\.xml$/m);
  });

  it("keeps crawlers out of account, admin and owner-only screens", () => {
    for (const path of [
      "/account",
      "/admin",
      "/admin/users",
      "/racks/new",
      "/racks/3/edit",
      "/rigs/new/photo",
      "/rigs/3/photo",
      "/rigs/3/reading",
      "/rigs/3/patchbook-studio",
    ]) {
      expect(isAppRoute(path)).toBe(true);
      expect(rules.some((rule) => blocks(rule, path))).toBe(true);
    }
  });

  it("lets crawlers read the public pages and public rigs and patches", () => {
    for (const path of [
      ...Object.keys(PUBLIC_PAGES),
      "/racks",
      "/racks/3",
      "/rigs/3",
      "/rigs/3/patches/4",
    ]) {
      expect(rules.filter((rule) => blocks(rule, path))).toEqual([]);
    }
  });
});

describe("icons and manifest", () => {
  it("links every icon and the manifest from index.html", () => {
    for (const href of [
      "/favicon.ico",
      "/favicon.svg",
      "/apple-touch-icon.png",
      "/site.webmanifest",
    ]) {
      expect(indexHtml).toContain(`href="${href}"`);
      expect(existsSync(resolve(publicDir, href.slice(1)))).toBe(true);
    }
  });

  it("holds 16, 32 and 48 pixel images in favicon.ico", () => {
    const ico = read("favicon.ico");
    expect(ico.readUInt16BE(0)).toBe(0); // reserved
    expect(ico.readUInt16LE(2)).toBe(1); // icon
    const count = ico.readUInt16LE(4);
    const sizes = Array.from({ length: count }, (_, i) => ico[6 + i * 16]).sort((a, b) => a - b);
    expect(sizes).toEqual([16, 32, 48]);
  });

  it("gives the touch icon and manifest icons their stated sizes", () => {
    expect(pngSize(read("apple-touch-icon.png"))).toEqual([180, 180]);
    const manifest = JSON.parse(read("site.webmanifest").toString("utf8"));
    expect(manifest.theme_color).toBe("#08090b");
    expect(manifest.start_url).toBe("/");
    const sizes = new Set<string>();
    for (const icon of manifest.icons as { src: string; sizes: string }[]) {
      const [w, h] = pngSize(read(icon.src.slice(1)));
      expect(`${w}x${h}`).toBe(icon.sizes);
      sizes.add(icon.sizes);
    }
    expect([...sizes].sort()).toEqual(["192x192", "512x512"]);
  });
});

describe("link preview", () => {
  it("names a 1200x630 image by its absolute URL, and a large card", () => {
    expect(meta("og:image")).toBe("https://patch-hive.com/og-image.jpg");
    expect(jpegSize(read("og-image.jpg"))).toEqual([1200, 630]);
    expect(meta("og:image:width")).toBe("1200");
    expect(meta("og:image:height")).toBe("630");
    expect(meta("og:image:alt")).toBeTruthy();
    expect(meta("og:type")).toBe("website");
    expect(meta("twitter:card")).toBe("summary_large_image");
  });
});
