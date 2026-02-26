"use client";

import { useCallback, useEffect, useState } from "react";

import { ApiClientError } from "../lib/api/client";
import {
  getScanOrders,
  postScanOrderCreateShipment,
  postScanOrderReviewStatus,
} from "../lib/api/ui";
import type { ScanOrdersDto } from "../lib/api/types";

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

export function ScanOrdersLive() {
  const [data, setData] = useState<ScanOrdersDto | null>(null);
  const [statusByOrderId, setStatusByOrderId] = useState<Record<number, string>>({});
  const [error, setError] = useState<string>("");
  const [mutationError, setMutationError] = useState<string>("");
  const [mutationStatus, setMutationStatus] = useState<string>("");
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);

  const loadOrders = useCallback(async () => {
    setError("");
    try {
      const payload = await getScanOrders();
      setData(payload);
      const nextStatuses: Record<number, string> = {};
      for (const order of payload.orders) {
        nextStatuses[order.id] = order.review_status;
      }
      setStatusByOrderId(nextStatuses);
    } catch (err: unknown) {
      setData(null);
      setError(toErrorMessage(err));
    }
  }, []);

  useEffect(() => {
    loadOrders().catch(() => undefined);
  }, [loadOrders]);

  const onUpdateStatus = async (orderId: number) => {
    const reviewStatus = statusByOrderId[orderId];
    if (!reviewStatus) {
      setMutationError("Statut commande invalide.");
      return;
    }
    setMutationError("");
    setMutationStatus("");
    setIsSubmitting(true);
    try {
      const response = await postScanOrderReviewStatus(orderId, {
        review_status: reviewStatus,
      });
      setMutationStatus(response.message);
      await loadOrders();
    } catch (err: unknown) {
      setMutationError(toErrorMessage(err));
    } finally {
      setIsSubmitting(false);
    }
  };

  const onCreateShipment = async (orderId: number) => {
    setMutationError("");
    setMutationStatus("");
    setIsSubmitting(true);
    try {
      const response = await postScanOrderCreateShipment(orderId);
      window.location.href = response.shipment.edit_url;
    } catch (err: unknown) {
      setMutationError(toErrorMessage(err));
      setIsSubmitting(false);
    }
  };

  if (error) {
    return (
      <div className="api-state api-error">
        API commandes indisponible: <span>{error}</span>
      </div>
    );
  }

  if (!data) {
    return <div className="api-state">Chargement API commandes...</div>;
  }

  return (
    <div className="stack-grid">
      <div className="api-state api-ok">API commandes connectee. {data.orders.length} commande(s).</div>

      {mutationStatus ? <div className="api-state api-ok">{mutationStatus}</div> : null}
      {mutationError ? (
        <div className="api-state api-error">
          Mutation commandes indisponible: <span>{mutationError}</span>
        </div>
      ) : null}

      <article className="panel">
        <h2>Vue commandes ({data.orders.length})</h2>
        <table className="data-table">
          <thead>
            <tr>
              <th>Commande</th>
              <th>Date</th>
              <th>Association</th>
              <th>Contact</th>
              <th>Statut commande</th>
              <th>Expedition</th>
              <th>Documents</th>
            </tr>
          </thead>
          <tbody>
            {data.orders.map((order) => (
              <tr key={order.id}>
                <td>{order.reference}</td>
                <td>{formatDate(order.created_at)}</td>
                <td>{order.association_name}</td>
                <td>
                  <div>{order.creator.name}</div>
                  <div className="scan-help">{order.creator.phone || "-"}</div>
                  <div className="scan-help">{order.creator.email || "-"}</div>
                </td>
                <td>
                  <div className="inline-actions">
                    <select
                      value={statusByOrderId[order.id] || order.review_status}
                      onChange={(event) =>
                        setStatusByOrderId((current) => ({
                          ...current,
                          [order.id]: event.target.value,
                        }))
                      }
                    >
                      {data.review_status_choices.map((choice) => (
                        <option key={choice.value} value={choice.value}>
                          {choice.label}
                        </option>
                      ))}
                    </select>
                    <button
                      type="button"
                      className="btn-secondary"
                      onClick={() => onUpdateStatus(order.id).catch(() => undefined)}
                      disabled={isSubmitting}
                    >
                      Mettre a jour
                    </button>
                  </div>
                </td>
                <td>
                  {order.can_create_shipment ? (
                    <button
                      type="button"
                      className="btn-secondary"
                      onClick={() => onCreateShipment(order.id).catch(() => undefined)}
                      disabled={isSubmitting}
                    >
                      Creer l expedition
                    </button>
                  ) : (
                    "-"
                  )}
                </td>
                <td>
                  {order.documents.length > 0 ? (
                    <div className="inline-actions">
                      {order.documents.map((document) => (
                        <a
                          key={`${order.id}-${document.url}`}
                          className="btn-secondary"
                          href={document.url}
                          target="_blank"
                          rel="noopener"
                        >
                          {document.label}
                        </a>
                      ))}
                    </div>
                  ) : (
                    <span className="scan-help">-</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </article>

      {data.orders
        .filter((order) => order.contact_message)
        .map((order) => (
          <article key={`message-${order.id}`} className="panel">
            <p className="scan-help">{order.contact_message}</p>
          </article>
        ))}
    </div>
  );
}
