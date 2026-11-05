/**
 * The registry answers differently for a signed-in reader (owner decision 39), so when the reader
 * changes, the page drops what it holds and asks again. Each mock answers for whoever holds the
 * token at the time of the call, as the API would.
 */
import { act, cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { useAuthStore } from "@/lib/store";
import type { User } from "@/types/api";

const { listManufacturers, getCoverage, search, getManufacturer, listModelsForManufacturer } =
  vi.hoisted(() => ({
    listManufacturers: vi.fn(),
    getCoverage: vi.fn(),
    search: vi.fn(),
    getManufacturer: vi.fn(),
    listModelsForManufacturer: vi.fn(),
  }));

vi.mock("@/lib/api", () => ({
  registryApi: {
    listManufacturers,
    getCoverage,
    search,
    getManufacturer,
    listModelsForManufacturer,
  },
}));

import RegistryPage from "./Registry";

const MAKER = { id: 1, slug: "maker", name: "Maker", status: "active" };

const signedIn = () => Boolean(useAuthStore.getState().token);
const models = () =>
  (signedIn() ? ["Known Osc", "Lead Osc"] : ["Known Osc"]).map((name) => ({ name }));

function serveByReader() {
  listManufacturers.mockImplementation(async () => ({ data: { total: 1, items: [MAKER] } }));
  getCoverage.mockImplementation(async () => ({
    data: { total_manufacturers: 1, total_models: signedIn() ? 2222 : 1111, hp_coverage_pct: 90 },
  }));
  search.mockImplementation(async () => ({
    data: { results: models().map((m) => ({ ...m, brand: "Maker" })) },
  }));
  getManufacturer.mockImplementation(async () => ({ data: MAKER }));
  listModelsForManufacturer.mockImplementation(async () => ({ data: { models: models() } }));
}

const signIn = (token = "token") =>
  useAuthStore.getState().setAuth({ id: 1, username: "reader" } as unknown as User, token);

const renderPage = () =>
  render(
    <MemoryRouter initialEntries={["/products"]}>
      <RegistryPage />
    </MemoryRouter>,
  );

afterEach(() => {
  cleanup();
  vi.resetAllMocks();
  useAuthStore.getState().clear();
});

describe("a change of reader on the Product Database", () => {
  it("asks again for the list and counts on sign-out", async () => {
    serveByReader();
    signIn();
    renderPage();
    await screen.findByText("2222");

    act(() => useAuthStore.getState().clear());

    await screen.findByText("1111");
    expect(screen.queryByText("2222")).not.toBeInTheDocument();
    expect(listManufacturers).toHaveBeenCalledTimes(2);
    expect(getCoverage).toHaveBeenCalledTimes(2);
  });

  it("asks again for the list and counts on sign-in", async () => {
    serveByReader();
    renderPage();
    await screen.findByText("1111");

    act(() => signIn());

    await screen.findByText("2222");
    expect(screen.queryByText("1111")).not.toBeInTheDocument();
  });

  it("asks again for the open manufacturer's models, keeping it open", async () => {
    serveByReader();
    signIn();
    const user = userEvent.setup();
    renderPage();
    await user.click(await screen.findByRole("button", { name: /maker/i }));
    await screen.findByText("Lead Osc");

    act(() => useAuthStore.getState().clear());

    expect(screen.queryByText("Lead Osc")).not.toBeInTheDocument();
    await screen.findByText("Known Osc");
    expect(screen.getByRole("heading", { name: "Maker" })).toBeInTheDocument();
    expect(listModelsForManufacturer).toHaveBeenCalledTimes(2);
  });

  it("drops a manufacturer answer the last reader asked for", async () => {
    serveByReader();
    signIn();
    const user = userEvent.setup();
    renderPage();
    const button = await screen.findByRole("button", { name: /maker/i });

    let answerLastReader: (value: unknown) => void = () => {};
    listModelsForManufacturer.mockImplementationOnce(
      () => new Promise((resolve) => (answerLastReader = resolve)),
    );
    await user.click(button);
    await waitFor(() => expect(listModelsForManufacturer).toHaveBeenCalledTimes(1));

    act(() => useAuthStore.getState().clear());
    await screen.findByText("Known Osc");

    await act(async () => answerLastReader({ data: { models: [{ name: "Lead Osc" }] } }));

    expect(screen.queryByText("Lead Osc")).not.toBeInTheDocument();
  });

  it("asks again for the model search, and shows no old hits meanwhile", async () => {
    serveByReader();
    signIn();
    const user = userEvent.setup();
    renderPage();
    await user.type(await screen.findByPlaceholderText(/Search manufacturers/), "osc");
    await screen.findByText("Maker Lead Osc");
    const searches = search.mock.calls.length;

    let answer: (value: unknown) => void = () => {};
    search.mockImplementationOnce(() => new Promise((resolve) => (answer = resolve)));
    act(() => useAuthStore.getState().clear());

    expect(screen.queryByText("Maker Lead Osc")).not.toBeInTheDocument();
    await waitFor(() => expect(search.mock.calls.length).toBe(searches + 1));

    await act(async () => answer({ data: { results: [{ name: "Known Osc", brand: "Maker" }] } }));
    await screen.findByText("Maker Known Osc");
  });

  it("does not ask again when a token is only renewed", async () => {
    serveByReader();
    signIn("first");
    renderPage();
    await screen.findByText("2222");

    await act(async () => signIn("renewed"));

    expect(listManufacturers).toHaveBeenCalledTimes(1);
    expect(getCoverage).toHaveBeenCalledTimes(1);
    expect(screen.getByText("2222")).toBeInTheDocument();
  });
});
