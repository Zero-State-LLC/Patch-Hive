/**
 * RouteEffects — what a page load would do, done on in-app navigation: name the screen in the
 * document title, start at the top, and move focus to the workspace so keyboard and screen
 * reader users land on the new screen instead of the link they left. The first screen keeps
 * the browser's own focus order (skip link first), and a new selection within the same screen
 * (another rig in the list) leaves focus where the user is.
 */
import { useEffect, useRef } from "react";
import { useLocation } from "react-router-dom";
import { titleFor } from "@/lib/routeTitles";

export default function RouteEffects() {
  const { pathname, hash } = useLocation();
  const title = titleFor(pathname);
  const shown = useRef(title);

  useEffect(() => {
    document.title = title;
    if (shown.current === title) return;
    shown.current = title;
    // A link to a section of the page is the browser's to handle.
    if (hash) return;
    window.scrollTo(0, 0);
    document.getElementById("main-content")?.focus({ preventScroll: true });
  }, [title, hash]);

  return null;
}
