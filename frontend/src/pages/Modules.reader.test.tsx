/**
 * The catalog answers differently for a signed-in reader (owner decision 39), so when the reader
 * changes, the page drops what it holds and asks again. Each mock answers for whoever holds the
 * token at the time of the call, as the API would.
 */
import { act, cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { useAuthStore } from "@/lib/store";
import type { CatalogModule, User } from "@/types/api";

const { catalog, catalogStats, catalogBrands, catalogCategories, materializeCatalog, listRigs } =
  vi.hoisted(() => ({
    catalog: vi.fn(),
    catalogStats: vi.fn(),
    catalogBrands: vi.fn(),
    catalogCategories: vi.fn(),
    materializeCatalog: vi.fn(),
    listRigs: vi.fn(),
  }));

vi.mock("@/lib/api", () => ({
  moduleApi: { catalog, catalogStats, catalogBrands, catalogCategories, materializeCatalog },
  canonApi: { listRigs },
}));

import ModulesPage from "./Modules";

const row = (brand: string, name: string) =>
  ({
    id: name.length,
    slug: `${brand}-${name}`.toLowerCase().replace(/\s+/g, "-"),
    brand,
    name,
    hp: 8,
    category: "VCO",
    is_available: "available",
  }) as unknown as CatalogModule;

const KNOWN = row("Maker", "Known Osc");
const LEAD = row("Lead Brand", "Lead Osc");

const signedIn = () => Boolean(useAuthStore.getState().token);
const page = (modules: CatalogModule[]) => ({
  data: { total: modules.length, skip: 0, limit: 48, modules },
});
const stats = (total: number) => ({
  data: {
    total_modules: total,
    total_brands: 1,
    total_categories: 1,
    hp_stats: { average: 8, min: 8, max: 8, known: 5, unknown: 0, coverage_pct: 100 },
    availability: { available: 5, discontinued: 0 },
  },
});

function serveByReader() {
  catalog.mockImplementation(async () => page(signedIn() ? [KNOWN, LEAD] : [KNOWN]));
  catalogStats.mockImplementation(async () => stats(signedIn() ? 2222 : 1111));
  catalogBrands.mockImplementation(async () => ({
    data: { brands: (signedIn() ? ["Maker", "Lead Brand"] : ["Maker"]).map((name) => ({ name })) },
  }));
  catalogCategories.mockImplementation(async () => ({
    data: { categories: (signedIn() ? ["VCO", "LFO"] : ["VCO"]).map((name) => ({ name })) },
  }));
}

const signIn = (token = "token") =>
  useAuthStore.getState().setAuth({ id: 1, username: "reader" } as unknown as User, token);

const renderPage = () =>
  render(
    <MemoryRouter initialEntries={["/modules"]}>
      <ModulesPage />
    </MemoryRouter>,
  );

const brandOptions = () =>
  within(screen.getByRole("combobox", { name: "Brand" }))
    .getAllByRole("option")
    .map((option) => option.textContent);

afterEach(() => {
  cleanup();
  vi.resetAllMocks();
  useAuthStore.getState().clear();
});

describe("a change of reader on the module catalog", () => {
  it("asks again on sign-out and shows only what an anonymous reader may see", async () => {
    serveByReader();
    signIn();
    renderPage();
    await screen.findByText("Lead Osc");
    await screen.findByText("2222");
    await waitFor(() => expect(brandOptions()).toContain("Lead Brand"));

    act(() => useAuthStore.getState().clear());

    await screen.findByText("1111");
    await screen.findByText(/Showing 1 of 1/);
    expect(screen.queryByText("Lead Osc")).not.toBeInTheDocument();
    expect(screen.queryByText("2222")).not.toBeInTheDocument();
    expect(brandOptions()).not.toContain("Lead Brand");
    expect(catalogStats).toHaveBeenCalledTimes(2);
    expect(catalogBrands).toHaveBeenCalledTimes(2);
    expect(catalogCategories).toHaveBeenCalledTimes(2);
  });

  it("asks again on sign-in and shows what a signed-in reader may see", async () => {
    serveByReader();
    renderPage();
    await screen.findByText("Known Osc");
    await screen.findByText("1111");
    expect(screen.queryByText("Lead Osc")).not.toBeInTheDocument();

    act(() => signIn());

    await screen.findByText("Lead Osc");
    await screen.findByText("2222");
    await waitFor(() => expect(brandOptions()).toContain("Lead Brand"));
  });

  it("keeps anonymous counts and brands when a filter changes after sign-out", async () => {
    serveByReader();
    signIn();
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("Lead Osc");
    act(() => useAuthStore.getState().clear());
    await screen.findByText("1111");

    await user.type(screen.getByRole("searchbox", { name: "Search modules" }), "osc");
    await waitFor(() => expect(catalog.mock.lastCall?.[0]).toMatchObject({ search: "osc" }));

    await screen.findByText("1111");
    expect(screen.queryByText("2222")).not.toBeInTheDocument();
    expect(screen.queryByText("Lead Osc")).not.toBeInTheDocument();
    expect(brandOptions()).not.toContain("Lead Brand");
    expect(catalogStats).toHaveBeenCalledTimes(2);
  });

  it("shows nothing from the last reader while the new answers are on their way", async () => {
    serveByReader();
    signIn();
    renderPage();
    await screen.findByText("Lead Osc");
    await screen.findByText("2222");

    catalog.mockImplementation(() => new Promise(() => {}));
    catalogStats.mockImplementation(() => new Promise(() => {}));
    act(() => useAuthStore.getState().clear());

    expect(screen.queryByText("Lead Osc")).not.toBeInTheDocument();
    expect(screen.queryByText("2222")).not.toBeInTheDocument();
    expect(brandOptions()).not.toContain("Lead Brand");
  });

  it("leaves no signed-in counts behind when the anonymous metadata fails", async () => {
    serveByReader();
    signIn();
    renderPage();
    await screen.findByText("2222");

    catalogStats.mockRejectedValue(new Error("offline"));
    catalogBrands.mockRejectedValue(new Error("offline"));
    act(() => useAuthStore.getState().clear());
    await screen.findByText(/Showing 1 of 1/);

    expect(screen.queryByText("2222")).not.toBeInTheDocument();
    expect(brandOptions()).not.toContain("Lead Brand");
  });

  it("does not ask again when a token is only renewed", async () => {
    serveByReader();
    signIn("first");
    renderPage();
    await screen.findByText("Lead Osc");
    await waitFor(() => expect(catalogStats).toHaveBeenCalledTimes(1));
    const lists = catalog.mock.calls.length;

    await act(async () => signIn("renewed"));

    expect(catalog).toHaveBeenCalledTimes(lists);
    expect(catalogStats).toHaveBeenCalledTimes(1);
    expect(screen.getByText("Lead Osc")).toBeInTheDocument();
  });

  it("falls back to the anonymous catalog, not a failure, when a renewal is refused", async () => {
    serveByReader();
    signIn("expired");
    // A refused renewal clears the session, then the request fails with its 401 (lib/api.ts).
    catalog.mockImplementationOnce(async () => {
      useAuthStore.getState().clear();
      throw Object.assign(new Error("Unauthorized"), { response: { status: 401 } });
    });
    renderPage();

    await screen.findByText("Known Osc");
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.queryByText("Lead Osc")).not.toBeInTheDocument();
  });

  it("closes the rig picker on sign-out, so the reader's rigs do not stay on screen", async () => {
    serveByReader();
    signIn();
    materializeCatalog.mockResolvedValue({
      data: { status: "exists", module_id: 7, module: { brand: "Maker", name: "Known Osc" } },
    });
    listRigs.mockResolvedValue({
      data: { rigs: [{ rig_id: 3, name: "My private rig", module_count: 0 }] },
    });
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("Known Osc");

    await user.click(screen.getAllByRole("button", { name: "Add to existing" })[0]);
    await screen.findByText(/My private rig/);

    act(() => useAuthStore.getState().clear());

    expect(screen.queryByText(/My private rig/)).not.toBeInTheDocument();
  });
});
