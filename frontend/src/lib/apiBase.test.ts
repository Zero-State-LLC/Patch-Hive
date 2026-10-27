import { describe, expect, it } from "vitest";
import { accountsOpen, resolveApiBase } from "./apiBase";

describe("resolveApiBase", () => {
  it("uses the local backend in dev", () => {
    expect(resolveApiBase({ DEV: true }, "http://localhost:8000/api")).toBe(
      "http://localhost:8000/api",
    );
  });

  it("has no API in a production build without a configured URL", () => {
    expect(resolveApiBase({ DEV: false })).toBeNull();
    expect(resolveApiBase({ DEV: false, VITE_API_BASE_URL: " " })).toBeNull();
  });

  it("refuses a plain-http API in production", () => {
    expect(
      resolveApiBase({ DEV: false, VITE_API_BASE_URL: "http://localhost:8000/api" }),
    ).toBeNull();
  });

  it("takes an https API in production", () => {
    expect(
      resolveApiBase({ DEV: false, VITE_API_BASE_URL: "https://api.patch-hive.com/api" }),
    ).toBe("https://api.patch-hive.com/api");
  });
});

describe("accountsOpen", () => {
  const api = "https://api.patch-hive.com/api";

  it("stays closed in production until the operator opens it", () => {
    expect(accountsOpen({ DEV: false }, api)).toBe(false);
    expect(accountsOpen({ DEV: false, VITE_ACCOUNTS_OPEN: "false" }, api)).toBe(false);
    expect(accountsOpen({ DEV: false, VITE_ACCOUNTS_OPEN: "true" }, api)).toBe(true);
  });

  it("never opens without an API", () => {
    expect(accountsOpen({ DEV: false, VITE_ACCOUNTS_OPEN: "true" }, null)).toBe(false);
  });

  it("is open in dev", () => {
    expect(accountsOpen({ DEV: true }, "http://localhost:8000/api")).toBe(true);
  });
});
