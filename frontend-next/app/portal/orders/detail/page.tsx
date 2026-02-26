"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";

import { AppShell } from "../../../components/app-shell";
import { ApiClientError } from "../../../lib/api/client";
import { getPortalOrderDetail } from "../../../lib/api/ui";
import type { UiPortalOrderDetailDto } from "../../../lib/api/types";

function toErrorMessage(error: unknown): string {
  if (error instanceof ApiClientError) {
    return `${error.message} (${error.code})`;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return String(error);
}

function parseOrderId(rawValue: string | null): number | null {
  if (!rawValue) {
    return null;
  }
  const value = Number(rawValue.trim());
  if (!Number.isInteger(value) || value <= 0) {
    return null;
  }
  return value;
}

function PortalOrderDetailContent() {
  const searchParams = useSearchParams();
  const orderId = parseOrderId(searchParams.get("id"));
  const [selectedOrder, setSelectedOrder] = useState<UiPortalOrderDetailDto["order"] | null>(null);
  const [error, setError] = useState<string>("");
  const [isLoading, setIsLoading] = useState<boolean>(false);

  useEffect(() => {
    if (orderId === null) {
      setSelectedOrder(null);
      setError("");
      setIsLoading(false);
      return;
    }
    setError("");
    setIsLoading(true);
    getPortalOrderDetail(orderId)
      .then((payload) => {
        setSelectedOrder(payload.order);
      })
      .catch((err: unknown) => {
        setSelectedOrder(null);
        setError(toErrorMessage(err));
      })
      .finally(() => {
        setIsLoading(false);
      });
  }, [orderId]);

  return (
    <AppShell
      section="portal"
      title="Detail commande"
      subtitle="Vue detaillee commande association (parite fonctionnelle)"
    >
      <article className="panel">
        <p>
          <a href="/app/portal/dashboard/" className="table-action">
            Retour dashboard portal
          </a>
        </p>
      </article>

      {orderId === null ? (
        <article className="panel api-error">Identifiant commande invalide.</article>
      ) : null}

      {orderId !== null && isLoading ? (
        <article className="panel">Chargement commande...</article>
      ) : null}

      {orderId !== null && !isLoading && error ? (
        <article className="panel api-error">{error}</article>
      ) : null}

      {orderId !== null && !isLoading && !error && !selectedOrder ? (
        <article className="panel api-error">Commande introuvable.</article>
      ) : null}

      {selectedOrder ? (
        <article className="panel">
          <h2>{selectedOrder.reference}</h2>
          <dl className="details-list">
            <div>
              <dt>Statut revue</dt>
              <dd>{selectedOrder.review_status_label}</dd>
            </div>
            <div>
              <dt>Expedition liee</dt>
              <dd>{selectedOrder.shipment_reference || "Aucune expedition"}</dd>
            </div>
            <div>
              <dt>Creee le</dt>
              <dd>{selectedOrder.created_at}</dd>
            </div>
          </dl>
        </article>
      ) : null}
    </AppShell>
  );
}

export default function PortalOrderDetailPage() {
  return (
    <Suspense
      fallback={
        <AppShell
          section="portal"
          title="Detail commande"
          subtitle="Vue detaillee commande association (parite fonctionnelle)"
        >
          <article className="panel">Chargement commande...</article>
        </AppShell>
      }
    >
      <PortalOrderDetailContent />
    </Suspense>
  );
}
