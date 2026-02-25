"use client";

import { usePathname } from "next/navigation";

function inferLegacyPath(pathname: string): string {
  if (pathname.startsWith("/portal/")) {
    return "/portal/";
  }
  if (pathname.startsWith("/scan/stock")) {
    return "/scan/stock/";
  }
  if (pathname.startsWith("/scan/cartons")) {
    return "/scan/cartons/";
  }
  if (pathname.startsWith("/scan/shipment-create")) {
    return "/scan/shipment/";
  }
  if (pathname.startsWith("/scan/shipments-ready")) {
    return "/scan/shipments-ready/";
  }
  if (pathname.startsWith("/scan/shipments-tracking")) {
    return "/scan/shipments-tracking/";
  }
  if (pathname.startsWith("/scan/shipment-documents")) {
    return "/scan/shipment/";
  }
  if (pathname.startsWith("/scan/templates")) {
    return "/scan/templates/";
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
