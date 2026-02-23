"use client";

import { useEffect, useState } from "react";

import { getPortalDashboard } from "../lib/api/ui";
import type { PortalDashboardDto } from "../lib/api/types";

export function PortalDashboardLive() {
  const [data, setData] = useState<PortalDashboardDto | null>(null);
  const [error, setError] = useState<string>("");

  useEffect(() => {
    let cancelled = false;
    getPortalDashboard()
      .then((payload) => {
        if (!cancelled) {
          setData(payload);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : String(err));
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (error) {
    return (
      <div className="api-state api-error">
        API portal indisponible: <span>{error}</span>
      </div>
    );
  }

  if (!data) {
    return <div className="api-state">Chargement API portal...</div>;
  }

  return (
    <div className="api-state api-ok">
      API portal connectee. Commandes {data.kpis.orders_total}, en attente validation{" "}
      {data.kpis.orders_pending_review}, avec expedition {data.kpis.orders_with_shipment}.
    </div>
  );
}
