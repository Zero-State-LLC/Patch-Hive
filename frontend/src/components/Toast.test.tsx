import { act, fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { useToast } from "@/lib/useToast";
import Toast from "./Toast";

function Harness({ onUndo, onFocus = vi.fn() }: { onUndo: () => void; onFocus?: () => void }) {
  const { toast, show, dismiss } = useToast();
  return (
    <>
      <button
        type="button"
        onClick={() =>
          show("Beta moved to row 1 at 12 HP.", {
            action: { label: "Undo", run: onUndo },
            returnFocus: onFocus,
          })
        }
      >
        Move
      </button>
      <button type="button" onClick={() => show("Saved.")}>
        Save
      </button>
      <input aria-label="Notes" />
      <Toast toast={toast} onDismiss={dismiss} />
    </>
  );
}

afterEach(() => {
  vi.useRealTimers();
});

describe("Toast", () => {
  it("announces the message in a polite live region and runs its action once", async () => {
    const user = userEvent.setup();
    const onUndo = vi.fn();
    render(<Harness onUndo={onUndo} />);

    await user.click(screen.getByRole("button", { name: "Move" }));
    expect(screen.getByRole("status")).toHaveTextContent("Beta moved to row 1 at 12 HP.");
    expect(screen.getByRole("status")).toHaveAttribute("aria-live", "polite");

    await user.click(screen.getByRole("button", { name: "Undo" }));
    expect(onUndo).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole("button", { name: "Undo" })).not.toBeInTheDocument();
  });

  it("lets a plain message leave after a few seconds, but not while the pointer is on it", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    render(<Harness onUndo={vi.fn()} />);

    await user.click(screen.getByRole("button", { name: "Save" }));
    fireEvent.mouseEnter(screen.getByRole("status"));
    act(() => vi.advanceTimersByTime(10_000));
    expect(screen.getByRole("status")).toHaveTextContent("Saved.");

    fireEvent.mouseLeave(screen.getByRole("status"));
    act(() => vi.advanceTimersByTime(7_000));
    expect(screen.getByRole("status")).not.toHaveTextContent("Saved.");
  });

  it("keeps an Undo until it is used, however long that takes", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    render(<Harness onUndo={vi.fn()} />);

    await user.click(screen.getByRole("button", { name: "Move" }));
    act(() => vi.advanceTimersByTime(60_000));

    expect(screen.getByRole("button", { name: "Undo" })).toBeInTheDocument();
  });

  it("runs Undo with Ctrl+Z or Cmd+Z, but not while typing in a field", async () => {
    const user = userEvent.setup();
    const onUndo = vi.fn();
    render(<Harness onUndo={onUndo} />);
    await user.click(screen.getByRole("button", { name: "Move" }));
    expect(screen.getByRole("button", { name: "Undo" })).toHaveAttribute(
      "aria-keyshortcuts",
      "Control+Z Meta+Z",
    );

    await user.click(screen.getByRole("textbox", { name: "Notes" }));
    await user.keyboard("{Control>}z{/Control}");
    expect(onUndo).not.toHaveBeenCalled();

    await user.click(screen.getByRole("button", { name: "Move" }));
    await user.keyboard("{Meta>}z{/Meta}");
    expect(onUndo).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole("button", { name: "Undo" })).not.toBeInTheDocument();
  });

  it("returns focus to what it was about when dismissed", async () => {
    const user = userEvent.setup();
    const onFocus = vi.fn();
    render(<Harness onUndo={vi.fn()} onFocus={onFocus} />);

    await user.click(screen.getByRole("button", { name: "Move" }));
    await user.click(screen.getByRole("button", { name: "Dismiss" }));

    expect(onFocus).toHaveBeenCalledTimes(1);
  });
});
