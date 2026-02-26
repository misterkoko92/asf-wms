"use client";

import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { ApiClientError } from "../lib/api/client";
import {
  getScanOrderState,
  postScanOrderAddLine,
  postScanOrderCreate,
  postScanOrderPrepare,
} from "../lib/api/ui";
import type { ScanOrderStateDto, UiScanOrderCreateInput } from "../lib/api/types";

function toErrorMessage(error: unknown): string {
  if (error instanceof ApiClientError) {
    return `${error.message} (${error.code})`;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return String(error);
}

function parsePositiveInteger(rawValue: string): number | null {
  const value = Number(rawValue.trim());
  if (!Number.isInteger(value) || value <= 0) {
    return null;
  }
  return value;
}

function parseNullableId(rawValue: string): number | null {
  const parsed = parsePositiveInteger(rawValue);
  return parsed || null;
}

export function ScanOrderLive() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const selectedOrderId = useMemo(
    () => parsePositiveInteger(searchParams.get("order") || ""),
    [searchParams],
  );

  const [data, setData] = useState<ScanOrderStateDto | null>(null);
  const [error, setError] = useState<string>("");
  const [mutationError, setMutationError] = useState<string>("");
  const [mutationStatus, setMutationStatus] = useState<string>("");
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [orderSelectValue, setOrderSelectValue] = useState<string>("");

  const [shipperName, setShipperName] = useState<string>("");
  const [recipientName, setRecipientName] = useState<string>("");
  const [correspondentName, setCorrespondentName] = useState<string>("");
  const [shipperContactId, setShipperContactId] = useState<string>("");
  const [recipientContactId, setRecipientContactId] = useState<string>("");
  const [correspondentContactId, setCorrespondentContactId] = useState<string>("");
  const [destinationAddress, setDestinationAddress] = useState<string>("");
  const [destinationCity, setDestinationCity] = useState<string>("");
  const [destinationCountry, setDestinationCountry] = useState<string>("France");
  const [requestedDeliveryDate, setRequestedDeliveryDate] = useState<string>("");
  const [notes, setNotes] = useState<string>("");

  const [lineProductCode, setLineProductCode] = useState<string>("");
  const [lineQuantity, setLineQuantity] = useState<string>("1");

  const loadState = useCallback(async (orderId: number | null) => {
    setError("");
    try {
      const payload = await getScanOrderState(orderId);
      setData(payload);
      setOrderSelectValue(orderId ? String(orderId) : "");
      if (payload.defaults.destination_country && !destinationCountry.trim()) {
        setDestinationCountry(payload.defaults.destination_country);
      }
    } catch (err: unknown) {
      setData(null);
      setError(toErrorMessage(err));
    }
  }, [destinationCountry]);

  useEffect(() => {
    loadState(selectedOrderId).catch(() => undefined);
  }, [loadState, selectedOrderId]);

  const onOpenOrder = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const orderId = parsePositiveInteger(orderSelectValue);
    if (!orderId) {
      setMutationError("Commande invalide.");
      return;
    }
    setMutationError("");
    setMutationStatus("");
    router.push(`/scan/order?order=${orderId}`);
  };

  const onCreateOrder = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!shipperName.trim() || !recipientName.trim() || !destinationAddress.trim()) {
      setMutationError("Expediteur, destinataire et adresse destination sont requis.");
      return;
    }
    const payload: UiScanOrderCreateInput = {
      shipper_name: shipperName.trim(),
      recipient_name: recipientName.trim(),
      correspondent_name: correspondentName.trim(),
      shipper_contact_id: parseNullableId(shipperContactId),
      recipient_contact_id: parseNullableId(recipientContactId),
      correspondent_contact_id: parseNullableId(correspondentContactId),
      destination_address: destinationAddress.trim(),
      destination_city: destinationCity.trim(),
      destination_country: destinationCountry.trim() || "France",
      requested_delivery_date: requestedDeliveryDate.trim() || null,
      notes: notes.trim(),
    };
    setMutationError("");
    setMutationStatus("");
    setIsSubmitting(true);
    try {
      const response = await postScanOrderCreate(payload);
      setMutationStatus(response.message);
      router.push(`/scan/order?order=${response.order.id}`);
      setLineProductCode("");
      setLineQuantity("1");
    } catch (err: unknown) {
      setMutationError(toErrorMessage(err));
    } finally {
      setIsSubmitting(false);
    }
  };

  const onAddLine = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const orderId = selectedOrderId;
    if (!orderId) {
      setMutationError("Selectionnez une commande.");
      return;
    }
    const quantity = parsePositiveInteger(lineQuantity);
    if (!quantity) {
      setMutationError("Quantite invalide.");
      return;
    }
    const productCode = lineProductCode.trim();
    if (!productCode) {
      setMutationError("Code produit requis.");
      return;
    }
    setMutationError("");
    setMutationStatus("");
    setIsSubmitting(true);
    try {
      const response = await postScanOrderAddLine({
        order_id: orderId,
        product_code: productCode,
        quantity,
      });
      setMutationStatus(response.message);
      await loadState(orderId);
      setLineQuantity("1");
    } catch (err: unknown) {
      setMutationError(toErrorMessage(err));
    } finally {
      setIsSubmitting(false);
    }
  };

  const onPrepareOrder = async () => {
    const orderId = selectedOrderId;
    if (!orderId) {
      setMutationError("Selectionnez une commande.");
      return;
    }
    setMutationError("");
    setMutationStatus("");
    setIsSubmitting(true);
    try {
      const response = await postScanOrderPrepare({
        order_id: orderId,
      });
      setMutationStatus(response.message);
      await loadState(orderId);
    } catch (err: unknown) {
      setMutationError(toErrorMessage(err));
    } finally {
      setIsSubmitting(false);
    }
  };

  if (error) {
    return (
      <div className="api-state api-error">
        API commande scan indisponible: <span>{error}</span>
      </div>
    );
  }

  if (!data) {
    return <div className="api-state">Chargement API commande scan...</div>;
  }

  return (
    <div className="stack-grid">
      <div className="api-state api-ok">
        API commande scan connectee. {data.orders.length} commande(s) disponible(s).
      </div>

      {mutationStatus ? <div className="api-state api-ok">{mutationStatus}</div> : null}
      {mutationError ? (
        <div className="api-state api-error">
          Mutation commande scan indisponible: <span>{mutationError}</span>
        </div>
      ) : null}

      <article className="panel">
        <h2>Commande existante</h2>
        <form className="inline-form" onSubmit={onOpenOrder}>
          <label className="field-inline">
            Commande
            <select
              value={orderSelectValue}
              onChange={(event) => setOrderSelectValue(event.target.value)}
            >
              <option value="">Selectionner une commande</option>
              {data.orders.map((order) => (
                <option key={order.id} value={order.id}>
                  {order.label}
                </option>
              ))}
            </select>
          </label>
          <button type="submit" className="btn-secondary" disabled={isSubmitting}>
            Ouvrir commande
          </button>
          <a
            className="btn-secondary"
            href="/admin/wms/order/add/"
            target="_blank"
            rel="noreferrer"
          >
            Ajouter commande
          </a>
        </form>
      </article>

      <article className="panel">
        <h2>Creer commande</h2>
        <form className="inline-form" onSubmit={onCreateOrder}>
          <label className="field-inline">
            Expediteur
            <input value={shipperName} onChange={(event) => setShipperName(event.target.value)} />
          </label>
          <label className="field-inline">
            Destinataire
            <input
              value={recipientName}
              onChange={(event) => setRecipientName(event.target.value)}
            />
          </label>
          <label className="field-inline">
            Correspondant
            <input
              value={correspondentName}
              onChange={(event) => setCorrespondentName(event.target.value)}
            />
          </label>
          <label className="field-inline">
            Expediteur (contact)
            <select
              value={shipperContactId}
              onChange={(event) => setShipperContactId(event.target.value)}
            >
              <option value="">Aucun</option>
              {data.contacts.shippers.map((contact) => (
                <option key={`shipper-${contact.id}`} value={contact.id}>
                  {contact.name}
                </option>
              ))}
            </select>
          </label>
          <label className="field-inline">
            Destinataire (contact)
            <select
              value={recipientContactId}
              onChange={(event) => setRecipientContactId(event.target.value)}
            >
              <option value="">Aucun</option>
              {data.contacts.recipients.map((contact) => (
                <option key={`recipient-${contact.id}`} value={contact.id}>
                  {contact.name}
                </option>
              ))}
            </select>
          </label>
          <label className="field-inline">
            Correspondant (contact)
            <select
              value={correspondentContactId}
              onChange={(event) => setCorrespondentContactId(event.target.value)}
            >
              <option value="">Aucun</option>
              {data.contacts.correspondents.map((contact) => (
                <option key={`correspondent-${contact.id}`} value={contact.id}>
                  {contact.name}
                </option>
              ))}
            </select>
          </label>
          <label className="field-inline">
            Adresse destination
            <textarea
              rows={3}
              value={destinationAddress}
              onChange={(event) => setDestinationAddress(event.target.value)}
            />
          </label>
          <label className="field-inline">
            Ville destination
            <input
              value={destinationCity}
              onChange={(event) => setDestinationCity(event.target.value)}
            />
          </label>
          <label className="field-inline">
            Pays destination
            <input
              value={destinationCountry}
              onChange={(event) => setDestinationCountry(event.target.value)}
            />
          </label>
          <label className="field-inline">
            Date souhaitee
            <input
              type="date"
              value={requestedDeliveryDate}
              onChange={(event) => setRequestedDeliveryDate(event.target.value)}
            />
          </label>
          <label className="field-inline">
            Notes
            <textarea rows={3} value={notes} onChange={(event) => setNotes(event.target.value)} />
          </label>
          <button type="submit" className="btn-secondary" disabled={isSubmitting}>
            Creer commande
          </button>
        </form>
      </article>

      {data.selected_order ? (
        <>
          <article className="panel">
            <h2>Commande active</h2>
            <div className="metric-grid">
              <article className="kpi-card">
                <h3>Reference</h3>
                <strong>{data.selected_order.reference}</strong>
              </article>
              <article className="kpi-card">
                <h3>Statut</h3>
                <strong>{data.selected_order.status_label}</strong>
              </article>
              <article className="kpi-card">
                <h3>Expedition</h3>
                <strong>{data.selected_order.shipment_reference || "-"}</strong>
              </article>
              <article className="kpi-card">
                <h3>Destination</h3>
                <strong>{data.selected_order.destination_address}</strong>
              </article>
            </div>
          </article>

          <article className="panel">
            <h2>Ajouter une ligne</h2>
            <form className="inline-form" onSubmit={onAddLine}>
              <label className="field-inline">
                Code produit
                <input
                  list="scan-order-products"
                  value={lineProductCode}
                  onChange={(event) => setLineProductCode(event.target.value)}
                />
              </label>
              <label className="field-inline">
                Quantite
                <input
                  value={lineQuantity}
                  onChange={(event) => setLineQuantity(event.target.value)}
                  inputMode="numeric"
                />
              </label>
              <button type="submit" className="btn-secondary" disabled={isSubmitting}>
                Ajouter ligne et reserver
              </button>
            </form>
            <datalist id="scan-order-products">
              {data.products.map((product) => (
                <option
                  key={`product-${product.id}`}
                  value={product.sku || product.name}
                  label={`${product.name}${product.barcode ? ` | ${product.barcode}` : ""}`}
                />
              ))}
            </datalist>
          </article>

          <article className="panel">
            <div className="panel-head">
              <h2>Lignes de commande ({data.order_lines.length})</h2>
              <button
                type="button"
                className="btn-secondary"
                onClick={() => onPrepareOrder().catch(() => undefined)}
                disabled={isSubmitting}
              >
                Preparer commande (reste {data.remaining_total})
              </button>
            </div>
            {data.order_lines.length > 0 ? (
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Produit</th>
                    <th>Quantite</th>
                    <th>Reserve</th>
                    <th>Prepare</th>
                    <th>Restant</th>
                  </tr>
                </thead>
                <tbody>
                  {data.order_lines.map((line) => (
                    <tr key={line.id}>
                      <td>{line.product_name}</td>
                      <td>{line.quantity}</td>
                      <td>{line.reserved_quantity}</td>
                      <td>{line.prepared_quantity}</td>
                      <td>{line.remaining_quantity}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <p className="scan-help">Aucune ligne pour cette commande.</p>
            )}
          </article>
        </>
      ) : (
        <article className="panel">
          <h2>Aucune commande selectionnee</h2>
          <p className="scan-help">
            Creez une commande ou selectionnez-en une pour ajouter des lignes.
          </p>
        </article>
      )}
    </div>
  );
}
