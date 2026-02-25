import Link from "next/link";

import { ModeSwitch } from "./mode-switch";

type AppShellProps = {
  title: string;
  subtitle: string;
  section: "scan" | "portal";
  children: React.ReactNode;
};

const scanNav = [
  { href: "/scan/dashboard", label: "Dashboard" },
  { href: "/scan/stock", label: "Vue stock" },
  { href: "/scan/cartons", label: "Vue colis" },
  { href: "/scan/shipment-create", label: "Creation expedition" },
  { href: "/scan/shipments-ready", label: "Vue expeditions" },
  { href: "/scan/shipments-tracking", label: "Suivi expeditions" },
  { href: "/scan/shipment-documents", label: "Docs & labels" },
  { href: "/scan/templates", label: "Templates" },
];

const portalNav = [{ href: "/portal/dashboard", label: "Portal dashboard" }];

export function AppShell({ title, subtitle, section, children }: AppShellProps) {
  const navItems = section === "portal" ? portalNav : scanNav;

  return (
    <div className="app-page">
      <aside className="app-sidebar">
        <div className="app-brand">
          <span className="app-brand-mark" />
          <div>
            <strong>ASF Ops</strong>
            <p>Next Static</p>
          </div>
        </div>
        <nav className="app-nav">
          {navItems.map((item) => (
            <Link key={item.href} href={item.href} className="app-nav-link" data-track={`nav.${item.href}`}>
              {item.label}
            </Link>
          ))}
          {section === "scan" ? (
            <Link href="/portal/dashboard" className="app-nav-link is-muted" data-track="nav.portal">
              Acceder au portal
            </Link>
          ) : (
            <Link href="/scan/dashboard" className="app-nav-link is-muted" data-track="nav.scan">
              Acceder au scan
            </Link>
          )}
        </nav>
      </aside>

      <main className="app-main">
        <header className="app-topbar">
          <div>
            <h1>{title}</h1>
            <p>{subtitle}</p>
          </div>
          <ModeSwitch />
        </header>
        <section className="app-content">{children}</section>
      </main>
    </div>
  );
}
