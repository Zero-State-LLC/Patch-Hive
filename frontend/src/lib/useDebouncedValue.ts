/**
 * useDebouncedValue — the value once it has held still for `delay` ms, so a search box asks the
 * API once per pause instead of once per keystroke.
 */
import { useEffect, useState } from "react";

export const SEARCH_DEBOUNCE_MS = 250;

export function useDebouncedValue<T>(value: T, delay = SEARCH_DEBOUNCE_MS): T {
  const [settled, setSettled] = useState(value);

  useEffect(() => {
    const timer = window.setTimeout(() => setSettled(value), delay);
    return () => window.clearTimeout(timer);
  }, [value, delay]);

  return settled;
}
