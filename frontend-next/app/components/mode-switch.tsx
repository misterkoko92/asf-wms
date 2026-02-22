"use client";

import { usePathname } from "next/navigation";

function inferLegacyPath(pathname: string): string {
  if (pathname.startsWith("/portal/")) {
    return "/portal/";
  }
  if (pathname.startsWith("/scan/stock")) {
    return "/scan/stock/";
  }
  if (pathname.startsWith("/scan/shipment-create")) {
    return "/scan/shipment/";
  }
  return "/scan/dashboard/";
}

export function ModeSwitch() {
  const pathname = usePathname();
  const legacyPath = inferLegacyPath(pathname || "/");
  const switchBackUrl = `/ui/mode/legacy/?next=${encodeURIComponent(legacyPath)}`;

  return (
    <div className="mode-switch">
      <a className="mode-chip" href={switchBackUrl} data-track="switch.back.legacy">
        Retour interface actuelle
      </a>
      <span className="mode-hint">Mode Next (parallele)</span>
    </div>
  );
}
