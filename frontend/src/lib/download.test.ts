import { afterEach, describe, expect, it, vi } from "vitest";
import { filenameFromDisposition, saveBlob } from "./download";

describe("filenameFromDisposition", () => {
  it("reads a quoted or bare filename", () => {
    expect(filenameFromDisposition('attachment; filename="rack_7_My_Rig.pdf"', "x.pdf")).toBe(
      "rack_7_My_Rig.pdf",
    );
    expect(filenameFromDisposition("attachment; filename=rack_7.pdf", "x.pdf")).toBe("rack_7.pdf");
  });

  it("prefers the encoded filename*", () => {
    expect(filenameFromDisposition("attachment; filename*=UTF-8''Rig%20%C3%A9.pdf", "x.pdf")).toBe(
      "Rig é.pdf",
    );
  });

  it("falls back when there is no header", () => {
    expect(filenameFromDisposition(undefined, "rack_7.pdf")).toBe("rack_7.pdf");
  });
});

describe("saveBlob", () => {
  afterEach(() => vi.restoreAllMocks());

  it("clicks a temporary download link and releases the object URL", () => {
    const create = vi.fn(() => "blob:rack");
    const revoke = vi.fn();
    Object.assign(URL, { createObjectURL: create, revokeObjectURL: revoke });
    const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});

    saveBlob(new Blob(["%PDF"]), "rack_7.pdf");

    expect(create).toHaveBeenCalledOnce();
    expect(click).toHaveBeenCalledOnce();
    expect(revoke).toHaveBeenCalledWith("blob:rack");
    expect(document.querySelector("a[download]")).toBeNull();
  });
});
