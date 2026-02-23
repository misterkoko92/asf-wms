"use client";

import { useEffect, useState } from "react";

import { getScanDashboard } from "../lib/api/ui";
import type { ScanDashboardDto } from "../lib/api/types";

export function ScanDashboardLive() {
  const [data, setData] = useState<ScanDashboardDto | null>(null);
  const [error, setError] = useState<string>("");

  useEffect(() => {
    let cancelled = false;
    getScanDashboard()
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
        API dashboard indisponible: <span>{error}</span>
      </div>
    );
  }

  if (!data) {
    return <div className="api-state">Chargement API dashboard...</div>;
  }

  return (
    <div className="api-state api-ok">
      API connectee. Open {data.kpis.open_shipments}, litiges {data.kpis.open_disputes},
      stock alerts {data.kpis.stock_alerts}.
    </div>
  );
}
