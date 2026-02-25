"use client";

import { useCallback, useEffect, useState, type FormEvent } from "react";

import { getScanDashboard } from "../lib/api/ui";
import type { ScanDashboardDto } from "../lib/api/types";

function formatTimestamp(value: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toLocaleString("fr-FR", {
    day: "2-digit",
    month: "2-digit",
    year: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function buildDashboardQuery(params: { destination: string }): string {
  const query = new URLSearchParams();
  const destination = params.destination.trim();
  if (destination) {
    query.set("destination", destination);
  }
  return query.toString();
}

export function ScanDashboardLive() {
  const [data, setData] = useState<ScanDashboardDto | null>(null);
  const [error, setError] = useState<string>("");
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [filterDestination, setFilterDestination] = useState<string>("");

  const loadDashboard = useCallback(async (query = "") => {
    setError("");
    setIsLoading(true);
    try {
      const payload = await getScanDashboard(query);
      setData(payload);
      setFilterDestination(payload.filters.destination || "");
    } catch (err: unknown) {
      setData(null);
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadDashboard().catch(() => undefined);
  }, [loadDashboard]);

  const onFilterSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const query = buildDashboardQuery({ destination: filterDestination });
    await loadDashboard(query);
  };

  const onFilterReset = async () => {
    setFilterDestination("");
    await loadDashboard("");
  };

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
    <div className="stack-grid">
      <div className="api-state api-ok">
        API connectee. Open {data.kpis.open_shipments}, litiges{" "}
        {data.kpis.open_disputes}, stock alerts {data.kpis.stock_alerts}.
      </div>

      <form className="inline-form" onSubmit={onFilterSubmit}>
        <label className="field-inline">
          Destination
          <select
            value={filterDestination}
            onChange={(event) => setFilterDestination(event.target.value)}
          >
            <option value="">Toutes les destinations</option>
            {data.filters.destinations.map((destination) => (
              <option key={destination.id} value={destination.id}>
                {destination.label}
              </option>
            ))}
          </select>
        </label>
        <button type="submit" className="btn-secondary" disabled={isLoading}>
          Filtrer
        </button>
        <button
          type="button"
          className="btn-secondary"
          onClick={() => onFilterReset().catch(() => undefined)}
          disabled={isLoading}
        >
          Reinitialiser
        </button>
      </form>

      <div className="kpi-grid">
        <article className="kpi-card">
          <span>Expeditions ouvertes</span>
          <strong>{data.kpis.open_shipments}</strong>
        </article>
        <article className="kpi-card">
          <span>Alertes stock</span>
          <strong>{data.kpis.stock_alerts}</strong>
        </article>
        <article className="kpi-card">
          <span>Litiges actifs</span>
          <strong>{data.kpis.open_disputes}</strong>
        </article>
        <article className="kpi-card">
          <span>Commandes en attente</span>
          <strong>{data.kpis.pending_orders}</strong>
        </article>
        <article className="kpi-card">
          <span>Expeditions en retard</span>
          <strong>{data.kpis.shipments_delayed}</strong>
        </article>
      </div>

      <div className="dashboard-grid">
        <article className="panel">
          <h2>Mission timeline</h2>
          {data.timeline.length ? (
            <ul className="timeline-list">
              {data.timeline.map((item) => (
                <li key={item.id}>
                  {formatTimestamp(item.timestamp)} - {item.reference} - {item.status}
                </li>
              ))}
            </ul>
          ) : (
            <p className="scan-help">Aucun evenement de suivi.</p>
          )}
        </article>

        <article className="panel">
          <h2>Actions en attente</h2>
          <table className="data-table">
            <thead>
              <tr>
                <th>Action</th>
                <th>Ref</th>
                <th>Owner</th>
                <th>Priorite</th>
              </tr>
            </thead>
            <tbody>
              {data.pending_actions.map((row) => (
                <tr key={`${row.type}-${row.reference}-${row.label}`}>
                  <td>{row.label}</td>
                  <td>{row.reference}</td>
                  <td>{row.owner}</td>
                  <td>{row.priority}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="inline-actions">
            <a className="btn-primary" href="/app/scan/cartons/" data-track="scan.create.carton">
              Creer colis
            </a>
            <a
              className="btn-secondary"
              href="/app/scan/shipment-create/"
              data-track="scan.create.shipment"
            >
              Creer expedition
            </a>
            <a className="btn-secondary" href="/app/scan/stock/" data-track="scan.add.stock">
              Ajouter stock
            </a>
          </div>
        </article>
      </div>
    </div>
  );
}
