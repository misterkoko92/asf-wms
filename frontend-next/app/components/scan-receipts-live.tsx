"use client";

import { useCallback, useEffect, useState } from "react";

import { ApiClientError } from "../lib/api/client";
import { getScanReceipts } from "../lib/api/ui";
import type { ScanReceiptsDto } from "../lib/api/types";

function toErrorMessage(error: unknown): string {
  if (error instanceof ApiClientError) {
    return `${error.message} (${error.code})`;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return String(error);
}

function formatDate(value: string | null): string {
  if (!value) {
    return "-";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return "-";
  }
  return parsed.toLocaleDateString("fr-FR");
}

export function ScanReceiptsLive() {
  const [data, setData] = useState<ScanReceiptsDto | null>(null);
  const [error, setError] = useState<string>("");
  const [filterValue, setFilterValue] = useState<string>("all");
  const [isLoading, setIsLoading] = useState<boolean>(false);

  const loadReceipts = useCallback(async (nextFilter: string) => {
    setError("");
    setIsLoading(true);
    try {
      const query = nextFilter && nextFilter !== "all" ? `type=${nextFilter}` : "";
      const payload = await getScanReceipts(query);
      setData(payload);
      setFilterValue(payload.filter_value || "all");
    } catch (err: unknown) {
      setData(null);
      setError(toErrorMessage(err));
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadReceipts("all").catch(() => undefined);
  }, [loadReceipts]);

  if (error) {
    return (
      <div className="api-state api-error">
        API receptions indisponible: <span>{error}</span>
      </div>
    );
  }

  if (!data) {
    return <div className="api-state">Chargement API receptions...</div>;
  }

  return (
    <div className="stack-grid">
      <div className="api-state api-ok">
        API receptions connectee. {data.receipts.length} reception(s).
      </div>
      <form className="inline-form">
        <label className="field-inline">
          Filtre
          <select
            value={filterValue}
            onChange={(event) => {
              const nextValue = event.target.value;
              setFilterValue(nextValue);
              loadReceipts(nextValue).catch(() => undefined);
            }}
            disabled={isLoading}
          >
            {data.filters.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
      </form>
      <article className="panel">
        <h2>Vue reception ({data.receipts.length})</h2>
        {data.receipts.length > 0 ? (
          <table className="data-table">
            <thead>
              <tr>
                <th>Date de reception</th>
                <th>Nom</th>
                <th>Quantite</th>
                <th>Quantite Hors Format</th>
                <th>Transporteur</th>
              </tr>
            </thead>
            <tbody>
              {data.receipts.map((receipt) => (
                <tr key={receipt.id}>
                  <td>{formatDate(receipt.received_on)}</td>
                  <td>{receipt.name}</td>
                  <td>{receipt.quantity}</td>
                  <td>{receipt.hors_format}</td>
                  <td>{receipt.carrier}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="scan-help">Aucune reception.</p>
        )}
      </article>
    </div>
  );
}
