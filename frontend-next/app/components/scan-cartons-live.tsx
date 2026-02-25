"use client";

import { useEffect, useState } from "react";

import { getScanCartons } from "../lib/api/ui";
import type { ScanCartonsDto } from "../lib/api/types";

function formatDate(value: string | null): string {
  if (!value) {
    return "-";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return "-";
  }
  return parsed.toLocaleString("fr-FR", {
    day: "2-digit",
    month: "2-digit",
    year: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatWeight(value: number | null): string {
  if (value === null || value === undefined) {
    return "-";
  }
  return `${value.toFixed(2)} kg`;
}

function formatVolume(value: number | null): string {
  if (value === null || value === undefined) {
    return "-";
  }
  return `${value}%`;
}

export function ScanCartonsLive() {
  const [data, setData] = useState<ScanCartonsDto | null>(null);
  const [error, setError] = useState<string>("");

  useEffect(() => {
    let cancelled = false;
    getScanCartons()
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
        API vue colis indisponible: <span>{error}</span>
      </div>
    );
  }

  if (!data) {
    return <div className="api-state">Chargement API vue colis...</div>;
  }

  return (
    <div className="stack-grid">
      <div className="api-state api-ok">
        API colis connectee. {data.meta.total_cartons} colis avec contenu.
      </div>

      <article className="panel">
        <h2>Vue colis ({data.cartons.length})</h2>
        <table className="data-table">
          <thead>
            <tr>
              <th>Numero colis</th>
              <th>Date creation</th>
              <th>Statut</th>
              <th>N° expedition</th>
              <th>Emplacement</th>
              <th>Remplissage</th>
              <th>Liste de colisage</th>
            </tr>
          </thead>
          <tbody>
            {data.cartons.map((carton) => (
              <tr key={carton.id}>
                <td>{carton.code}</td>
                <td>{formatDate(carton.created_at)}</td>
                <td>{carton.status_label}</td>
                <td>{carton.shipment_reference || "-"}</td>
                <td>{carton.location || "-"}</td>
                <td>
                  <div>Poids: {formatWeight(carton.weight_kg)}</div>
                  <div>Volume: {formatVolume(carton.volume_percent)}</div>
                </td>
                <td>
                  {carton.packing_list.length ? (
                    <div className="stack-grid">
                      <div>
                        {carton.packing_list.map((item) => (
                          <div key={`${carton.id}-${item.label}`}>
                            {item.label} ({item.quantity})
                          </div>
                        ))}
                      </div>
                      <div className="inline-actions">
                        <a
                          className="btn-secondary"
                          href={carton.packing_list_url}
                          target="_blank"
                          rel="noopener"
                        >
                          Imprimer
                        </a>
                        <a
                          className="btn-secondary"
                          href={carton.picking_url}
                          target="_blank"
                          rel="noopener"
                        >
                          Picking
                        </a>
                      </div>
                    </div>
                  ) : (
                    "-"
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </article>
    </div>
  );
}
