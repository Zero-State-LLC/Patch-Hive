import { Link, useLocation } from "react-router-dom";

const links = [
  { to: "/admin", label: "Dashboard", exact: true },
  { to: "/admin/users", label: "Users" },
  { to: "/admin/modules", label: "Modules" },
  { to: "/admin/gallery", label: "Gallery" },
  { to: "/admin/runs", label: "Runs" },
  { to: "/admin/exports", label: "Exports" },
  { to: "/admin/leaderboards", label: "Leaderboards" },
];

export function AdminNav() {
  const { pathname } = useLocation();

  return (
    <nav className="admin-nav" aria-label="Admin console">
      {links.map((link) => {
        const active = link.exact
          ? pathname === link.to
          : pathname === link.to || pathname.startsWith(`${link.to}/`);
        return (
          <Link key={link.to} to={link.to} className={active ? "active" : undefined}>
            {link.label}
          </Link>
        );
      })}
    </nav>
  );
}
