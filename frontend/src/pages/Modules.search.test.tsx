/**
 * The module search asks once the typing pauses, cancels the request it replaces, and never lets
 * a slow earlier answer replace the latest one. Stats, brands and categories are fetched once.
 */
import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { CatalogModule } from "@/types/api";

const { catalog, catalogStats, catalogBrands, catalogCategories } = vi.hoisted(() => ({
  catalog: vi.fn(),
  catalogStats: vi.fn(),
  catalogBrands: vi.fn(),
  catalogCategories: vi.fn(),
}));

vi.mock("@/lib/api", () => ({
  moduleApi: { catalog, catalogStats, catalogBrands, catalogCategories },
  canonApi: { listRigs: vi.fn() },
}));

import ModulesPage from "./Modules";

const row = (id: number, name: string) =>
  ({
    id,
    slug: `sim-co-${name.toLowerCase()}`,
    brand: "Sim Co",
    name,
    hp: 8,
    category: "VCO",
    is_available: "available",
  }) as unknown as CatalogModule;

const page = (modules: CatalogModule[]) => ({
  data: { total: modules.length, skip: 0, limit: 48, modules },
});

interface Pending {
  search?: string;
  signal?: AbortSignal;
  resolve: (value: ReturnType<typeof page>) => void;
}

/** Each catalog request waits until the test answers it, as a slow network would. */
function holdRequests() {
  const pending: Pending[] = [];
  catalog.mockImplementation(
    (params: { search?: string }, config?: { signal?: AbortSignal }) =>
      new Promise((resolve) => {
        pending.push({ search: params.search, signal: config?.signal, resolve });
      }),
  );
  return pending;
}

function renderPage(categories: string[] = ["VCO"]) {
  catalogStats.mockResolvedValue({
    data: {
      total_modules: 2,
      total_brands: 1,
      total_categories: 1,
      hp_stats: { average: 8, min: 8, max: 8, known: 2, unknown: 0, coverage_pct: 100 },
      availability: { available: 2, discontinued: 0 },
    },
  });
  catalogBrands.mockResolvedValue({ data: { total: 1, brands: [{ name: "Sim Co" }] } });
  catalogCategories.mockResolvedValue({
    data: { total: categories.length, categories: categories.map((name) => ({ name })) },
  });
  return render(
    <MemoryRouter initialEntries={["/modules"]}>
      <ModulesPage />
    </MemoryRouter>,
  );
}

afterEach(() => {
  vi.clearAllMocks();
});

describe("module search", () => {
  it("asks once per pause, not once per keystroke", async () => {
    const pending = holdRequests();
    const user = userEvent.setup();
    renderPage();
    await waitFor(() => expect(pending).toHaveLength(1));
    act(() => pending[0].resolve(page([row(1, "Oscillator"), row(2, "Filter")])));
    await screen.findByText(/Showing 2 of 2/);

    await user.type(screen.getByRole("searchbox", { name: "Search modules" }), "filter");

    await waitFor(() => expect(pending).toHaveLength(2));
    expect(pending[1].search).toBe("filter");
    expect(pending.map((p) => p.search)).not.toContain("f");
  });

  it("cancels the request it replaces and keeps the latest answer", async () => {
    const pending = holdRequests();
    const user = userEvent.setup();
    renderPage();
    await waitFor(() => expect(pending).toHaveLength(1));
    const box = screen.getByRole("searchbox", { name: "Search modules" });

    await user.type(box, "osc");
    await waitFor(() => expect(pending).toHaveLength(2));
    expect(pending[0].signal?.aborted).toBe(true);

    // The newest answer arrives first, then the slow first one; the first is ignored.
    act(() => pending[1].resolve(page([row(1, "Oscillator")])));
    await screen.findByText(/Showing 1 of 1/);
    act(() => pending[0].resolve(page([row(1, "Oscillator"), row(2, "Filter")])));

    await act(async () => {});
    expect(screen.getByText(/Showing 1 of 1/)).toBeInTheDocument();
    expect(screen.queryByText(/Showing 2 of 2/)).not.toBeInTheDocument();
  });

  it("offers whatever categories the catalog holds, VIDEO and SYSTEM included", async () => {
    const pending = holdRequests();
    const user = userEvent.setup();
    renderPage(["VCO", "VIDEO", "SYSTEM"]);
    await waitFor(() => expect(pending).toHaveLength(1));
    act(() => pending[0].resolve(page([row(1, "Oscillator")])));
    await screen.findByText(/Showing 1 of 1/);

    const filter = screen.getByRole("combobox", { name: "Category" });
    await screen.findByRole("option", { name: "VIDEO" });
    expect(screen.getByRole("option", { name: "SYSTEM" })).toBeInTheDocument();

    await user.selectOptions(filter, "SYSTEM");
    await waitFor(() => expect(pending).toHaveLength(2));
    expect(catalog.mock.calls[1][0]).toMatchObject({ category: "SYSTEM" });
  });

  it("fetches stats, brands and categories once, however the list changes", async () => {
    const pending = holdRequests();
    const user = userEvent.setup();
    renderPage();
    await waitFor(() => expect(pending).toHaveLength(1));
    act(() => pending[0].resolve(page([row(1, "Oscillator")])));

    await user.type(screen.getByRole("searchbox", { name: "Search modules" }), "vco");
    await waitFor(() => expect(pending).toHaveLength(2));

    expect(catalogStats).toHaveBeenCalledTimes(1);
    expect(catalogBrands).toHaveBeenCalledTimes(1);
    expect(catalogCategories).toHaveBeenCalledTimes(1);
  });

  it("shows a failure with Retry, never an empty catalog", async () => {
    catalog.mockRejectedValueOnce(Object.assign(new Error("offline"), { code: "ERR_NETWORK" }));
    catalog.mockResolvedValue(page([row(1, "Oscillator")]));
    const user = userEvent.setup();
    renderPage();

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "The module catalog didn't load. PatchHive can't be reached.",
    );
    expect(screen.queryByText("No modules in the catalog yet.")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Retry" }));
    expect(await screen.findByText(/Showing 1 of 1/)).toBeInTheDocument();
  });
});
