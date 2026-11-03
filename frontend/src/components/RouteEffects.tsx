/**
 * RouteEffects — what a page load would do, done on in-app navigation: name the screen in the
 * document title, start at the top, and move focus to the workspace so keyboard and screen
 * reader users land on the new screen instead of the link they left. The first screen keeps
 * the browser's own focus order (skip link first).
 */
import { useEffect, useRef } from "react";
import { useLocation } from "react-router-dom";
import { titleFor } from "@/lib/routeTitles";

export default function RouteEffects() {
  const { pathname, hash } = useLocation();
  const shown = useRef(pathname);

  useEffect(() => {
    document.title = titleFor(pathname);
    if (shown.current === pathname) return;
    shown.current = pathname;
    // A link to a section of the page is the browser's to handle.
    if (hash) return;
    window.scrollTo(0, 0);
    document.getElementById("main-content")?.focus({ preventScroll: true });
  }, [pathname, hash]);

  return null;
}
