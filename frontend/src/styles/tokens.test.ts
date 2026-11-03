/**
 * Non-text contrast for each theme: lines and marks that carry state or signal (indicators,
 * cables, category bands, focus rings, field edges) must reach 3:1 against the surfaces they
 * sit on, after any opacity they are painted at. axe only measures text, so this guards the rest.
 */
import { describe, expect, it } from "vitest";
import source from "./tokens.css?raw";

const css = source.replace(/\/\*[\s\S]*?\*\//g, "");

function declarations(block: string): Record<string, string> {
  const out: Record<string, string> = {};
  for (const match of block.matchAll(/(--[\w-]+)\s*:\s*([^;]+);/g)) out[match[1]] = match[2].trim();
  return out;
}

function themeTokens(theme: "dark" | "light"): Record<string, string> {
  const tokens: Record<string, string> = {};
  for (const [, selector, body] of css.matchAll(/([^{}]+)\{([^{}]*)\}/g)) {
    const light = selector.includes('[data-theme="light"]');
    if (light ? theme === "light" : /(^|,)\s*(:root|\.app-shell)\s*(,|$)/.test(selector.trim())) {
      Object.assign(tokens, declarations(body));
    }
  }
  return tokens;
}

function resolve(tokens: Record<string, string>, name: string, depth = 0): string {
  const value = tokens[name];
  if (value === undefined || depth > 10) throw new Error(`unresolved ${name}`);
  const ref = value.match(/^var\((--[\w-]+)\)$/);
  return ref ? resolve(tokens, ref[1], depth + 1) : value;
}

function rgb(hex: string): [number, number, number] {
  const m = hex.match(/^#([0-9a-f]{6})$/i);
  if (!m) throw new Error(`not a hex colour: ${hex}`);
  const n = parseInt(m[1], 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

function luminance([r, g, b]: [number, number, number]): number {
  const lin = (c: number) => {
    const s = c / 255;
    return s <= 0.04045 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
}

function contrast(fg: string, bg: string, alpha = 1): number {
  const back = rgb(bg);
  const front = rgb(fg).map((c, i) => c * alpha + back[i] * (1 - alpha)) as [
    number,
    number,
    number,
  ];
  const [a, b] = [luminance(front), luminance(back)].sort((x, y) => y - x);
  return (a + 0.05) / (b + 0.05);
}

const PAPERS = ["--color-paper", "--color-paper-2", "--color-paper-3"];

/** Each mark, the surfaces it sits on, and the opacity it is painted at (styles/*.css). */
const MARKS: { token: string; on: string[]; alpha?: number }[] = [
  { token: "--color-indicator", on: PAPERS },
  { token: "--color-focus", on: PAPERS },
  { token: "--color-field-edge", on: PAPERS },
  // Patch leads are painted at 0.9 (rig.css .patch-cable__lead), over paper and faceplates.
  { token: "--cable-audio", on: [...PAPERS, "--color-plate-face"], alpha: 0.9 },
  { token: "--cable-cv", on: [...PAPERS, "--color-plate-face"], alpha: 0.9 },
  { token: "--cable-gate", on: [...PAPERS, "--color-plate-face"], alpha: 0.9 },
  // Category bands are painted at 0.85 on module faceplates (catalog.css .mockup-face::before).
  { token: "--module-source", on: ["--color-plate-face"], alpha: 0.85 },
  { token: "--module-shaper", on: ["--color-plate-face"], alpha: 0.85 },
  { token: "--module-controller", on: ["--color-plate-face"], alpha: 0.85 },
];

describe.each(["dark", "light"] as const)("%s theme non-text contrast", (theme) => {
  const tokens = themeTokens(theme);

  it.each(MARKS)("$token reaches 3:1 where it is drawn", ({ token, on, alpha }) => {
    const failing = on
      .map((bg) => ({ bg, ratio: contrast(resolve(tokens, token), resolve(tokens, bg), alpha) }))
      .filter(({ ratio }) => ratio < 3)
      .map(({ bg, ratio }) => `${bg} ${ratio.toFixed(2)}:1`);
    expect(failing).toEqual([]);
  });

  it("keeps the unlit cable visible on paper", () => {
    // Unlit is quieter than lit by design, but must still read as a line, not a hairline.
    const ratio = contrast(resolve(tokens, "--color-cable-off"), resolve(tokens, "--color-paper"));
    expect(ratio).toBeGreaterThanOrEqual(2.4);
  });
});
