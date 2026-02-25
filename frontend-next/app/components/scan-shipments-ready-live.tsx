"use client";

import { useCallback, useEffect, useState } from "react";

import { ApiClientError } from "../lib/api/client";
import { getShipmentsReady, postShipmentsReadyArchiveStaleDrafts } from "../lib/api/ui";
import type { ScanShipmentsReadyDto } from "../lib/api/types";

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
  return parsed.toLocaleString("fr-FR", {
    day: "2-digit",
    month: "2-digit",
    year: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function ScanShipmentsReadyLive() {
  const [data, setData] = useState<ScanShipmentsReadyDto | null>(null);
  const [error, setError] = useState<string>("");
  const [mutationError, setMutationError] = useState<string>("");
  const [mutationStatus, setMutationStatus] = useState<string>("");
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);

  const loadShipments = useCallback(async () => {
    setError("");
    try {
      const payload = await getShipmentsReady();
      setData(payload);
    } catch (err: unknown) {
      setData(null);
      setError(toErrorMessage(err));
    }
  }, []);

  useEffect(() => {
    loadShipments().catch(() => undefined);
  }, [loadShipments]);

  const onArchiveStaleDrafts = async () => {
    setIsSubmitting(true);
    setMutationError("");
    setMutationStatus("");
    try {
      const response = await postShipmentsReadyArchiveStaleDrafts();
      setMutationStatus(response.message);
      await loadShipments();
    } catch (err: unknown) {
      setMutationError(toErrorMessage(err));
    } finally {
      setIsSubmitting(false);
    }
  };

  if (error) {
    return (
      <div className="api-state api-error">
        API vue expeditions indisponible: <span>{error}</span>
      </div>
    );
  }

  if (!data) {
    return <div className="api-state">Chargement API vue expeditions...</div>;
  }

  return (
    <div className="stack-grid">
      <div className="api-state api-ok">
        API expeditions connectee. {data.meta.total_shipments} expeditions.
      </div>

      {data.meta.stale_draft_count > 0 ? (
        <>
          <div className="api-state api-error">
            {data.meta.stale_draft_count} brouillon(s) temporaire(s) de plus de{" "}
            {data.meta.stale_draft_days} jours.
          </div>
          <div className="inline-actions">
            <button
              type="button"
              className="btn-secondary"
              onClick={() => onArchiveStaleDrafts().catch(() => undefined)}
              disabled={isSubmitting}
            >
              Archiver brouillons anciens
            </button>
          </div>
        </>
      ) : null}

      {mutationStatus ? <div className="api-state api-ok">{mutationStatus}</div> : null}
      {mutationError ? (
        <div className="api-state api-error">
          Mutation expeditions indisponible: <span>{mutationError}</span>
        </div>
      ) : null}

      <article className="panel">
        <h2>Vue expeditions ({data.shipments.length})</h2>
        <table className="data-table">
          <thead>
            <tr>
              <th>N° expedition</th>
              <th>Nb colis</th>
              <th>Destination (IATA)</th>
              <th>Expediteur</th>
              <th>Destinataire</th>
              <th>Date creation</th>
              <th>Date mise a dispo</th>
              <th>Statut</th>
              <th>Documents</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {data.shipments.map((shipment) => (
              <tr key={shipment.id}>
                <td>{shipment.reference}</td>
                <td>{shipment.carton_count}</td>
                <td>{shipment.destination_iata || "-"}</td>
                <td>{shipment.shipper_name}</td>
                <td>{shipment.recipient_name}</td>
                <td>{formatDate(shipment.created_at)}</td>
                <td>{formatDate(shipment.ready_at)}</td>
                <td>{shipment.status_label}</td>
                <td>
                  <div className="inline-actions">
                    <a
                      className="btn-secondary"
                      href={shipment.documents.shipment_note_url}
                      target="_blank"
                      rel="noopener"
                    >
                      Bon
                    </a>
                    <a
                      className="btn-secondary"
                      href={shipment.documents.labels_url}
                      target="_blank"
                      rel="noopener"
                    >
                      Labels
                    </a>
                  </div>
                </td>
                <td>
                  <div className="inline-actions">
                    <a className="btn-secondary" href={shipment.actions.tracking_url}>
                      Suivi
                    </a>
                    {shipment.actions.edit_url ? (
                      <a className="btn-secondary" href={shipment.actions.edit_url}>
                        Modifier
                      </a>
                    ) : null}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </article>
    </div>
  );
}
