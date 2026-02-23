"use client";

import { useEffect, useState } from "react";

import { getScanStock } from "../lib/api/ui";
import type { ScanStockDto } from "../lib/api/types";

export function ScanStockLive() {
  const [data, setData] = useState<ScanStockDto | null>(null);
  const [error, setError] = useState<string>("");

  useEffect(() => {
    let cancelled = false;
    getScanStock()
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
        API stock indisponible: <span>{error}</span>
      </div>
    );
  }

  if (!data) {
    return <div className="api-state">Chargement API stock...</div>;
  }

  return (
    <>
      <div className="api-state api-ok">
        API stock connectee. {data.meta.total_products} produits, seuil bas{" "}
        {data.meta.low_stock_threshold}.
      </div>
      <table className="data-table">
        <thead>
          <tr>
            <th>Produit</th>
            <th>Marque</th>
            <th>Emplacement</th>
            <th>Qty</th>
            <th>Etat</th>
            <th>Action</th>
          </tr>
        </thead>
        <tbody>
          {data.products.slice(0, 12).map((row) => (
            <tr key={row.id}>
              <td>{row.name}</td>
              <td>{row.brand}</td>
              <td>{row.location}</td>
              <td>{row.stock_total}</td>
              <td>
                <span className={`state-pill state-${row.state.toLowerCase()}`}>
                  {row.state.toUpperCase()}
                </span>
              </td>
              <td>
                <button type="button" className="table-action" data-track="stock.update.inline">
                  MAJ
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}
