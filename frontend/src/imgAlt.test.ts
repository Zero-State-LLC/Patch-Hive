/**
 * Every <img> the app renders carries alt text: words for an image that says something, alt=""
 * for one that only decorates. The app has no JSX accessibility lint plugin, so this reads the
 * source instead.
 */
import { describe, expect, it } from "vitest";

const sources = import.meta.glob(["./**/*.tsx", "!./**/*.test.tsx"], {
  query: "?raw",
  import: "default",
  eager: true,
}) as Record<string, string>;

/** Each <img …> tag in a file, read to its closing > outside any {expression} or string. */
function imgTags(source: string): string[] {
  const tags: string[] = [];
  for (const match of source.matchAll(/<img[\s/>]/g)) {
    let depth = 0;
    let quote = "";
    let end = match.index + 4;
    for (; end < source.length; end++) {
      const ch = source[end];
      if (quote) {
        if (ch === quote) quote = "";
      } else if (ch === '"' || ch === "'" || ch === "`") quote = ch;
      else if (ch === "{") depth++;
      else if (ch === "}") depth--;
      else if (ch === ">" && depth === 0) break;
    }
    tags.push(source.slice(match.index, end + 1));
  }
  return tags;
}

describe("images", () => {
  const found = Object.entries(sources).flatMap(([file, source]) =>
    imgTags(source).map((tag) => ({ file, tag })),
  );

  it("finds the app's images", () => {
    expect(found.length).toBeGreaterThan(0);
  });

  it("gives every image alt text", () => {
    const missing = found.filter(({ tag }) => !/\salt=/.test(tag));
    expect(missing).toEqual([]);
  });
});
