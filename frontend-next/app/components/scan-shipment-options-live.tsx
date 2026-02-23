"use client";

import { useEffect, useState } from "react";

import { getShipmentFormOptions } from "../lib/api/ui";
import type { ShipmentFormOptionsDto } from "../lib/api/types";

export function ScanShipmentOptionsLive() {
  const [data, setData] = useState<ShipmentFormOptionsDto | null>(null);
  const [error, setError] = useState<string>("");

  useEffect(() => {
    let cancelled = false;
    getShipmentFormOptions()
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
        API creation expedition indisponible: <span>{error}</span>
      </div>
    );
  }

  if (!data) {
    return <div className="api-state">Chargement API creation expedition...</div>;
  }

  return (
    <div className="api-state api-ok">
      API connectee. Destinations {data.destinations.length}, expediteurs{" "}
      {data.shipper_contacts.length}, destinataires {data.recipient_contacts.length},
      cartons dispo {data.available_cartons.length}.
    </div>
  );
}
