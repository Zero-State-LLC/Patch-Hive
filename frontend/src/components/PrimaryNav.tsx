/**
 * PrimaryNav — the app's sections. On a phone the row scrolls: its edges fade where more links
 * lie past them, and the current section scrolls into view on arrival.
 */
import { useEffect } from "react";
import { NavLink, useLocation } from "react-router-dom";
import { useScrollEdges } from "@/lib/useScrollEdges";

export default function PrimaryNav({
  signedIn,
  canSeeAdmin,
}: {
  signedIn: boolean;
  canSeeAdmin: boolean;
}) {
  const ref = useScrollEdges<HTMLElement>();
  const { pathname } = useLocation();

  useEffect(() => {
    const nav = ref.current;
    const current = nav?.querySelector<HTMLElement>("a.active");
    if (!nav || !current || nav.scrollWidth <= nav.clientWidth) return;
    // Centre the current section in the row; the page itself does not scroll.
    const row = nav.getBoundingClientRect();
    const link = current.getBoundingClientRect();
    nav.scrollLeft += link.left - row.left - (row.width - link.width) / 2;
  }, [pathname, ref]);

  return (
    <nav ref={ref} className="primary-nav" aria-label="Primary navigation">
      <NavLink to="/racks">Rigs</NavLink>
      <NavLink to="/modules">Modules</NavLink>
      <NavLink to="/products">Products</NavLink>
      <NavLink to="/cases">Cases</NavLink>
      <NavLink to="/patches">Patches</NavLink>
      {signedIn ? <NavLink to="/account">Account</NavLink> : null}
      {canSeeAdmin ? <NavLink to="/admin">Ops</NavLink> : null}
    </nav>
  );
}
