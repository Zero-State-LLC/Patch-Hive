/**
 * useScrollEdges — marks a horizontally scrolling row with data-edge-start / data-edge-end when
 * more content lies past that edge, so CSS can fade the edge and show the row scrolls.
 */
import { useEffect, useRef } from "react";

export function useScrollEdges<T extends HTMLElement>() {
  const ref = useRef<T>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const update = () => {
      const max = el.scrollWidth - el.clientWidth;
      el.dataset.edgeStart = String(el.scrollLeft > 1);
      el.dataset.edgeEnd = String(el.scrollLeft < max - 1);
    };
    update();
    el.addEventListener("scroll", update, { passive: true });
    // The row's own size and its contents (links that appear after sign-in) both move the edges.
    const resize = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(update);
    resize?.observe(el);
    const children = typeof MutationObserver === "undefined" ? null : new MutationObserver(update);
    children?.observe(el, { childList: true });
    return () => {
      el.removeEventListener("scroll", update);
      resize?.disconnect();
      children?.disconnect();
    };
  }, []);

  return ref;
}
