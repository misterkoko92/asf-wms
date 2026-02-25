"use client";

import { useEffect, useMemo, useState, type FormEvent } from "react";

import { ApiClientError } from "../lib/api/client";
import {
  getShipmentFormOptions,
  postShipmentClose,
  postShipmentCreate,
  postShipmentTrackingEvent,
} from "../lib/api/ui";
import type { ShipmentFormOptionsDto } from "../lib/api/types";

type RawOptionRow = Record<string, string | number | boolean | null>;
type IdOption = {
  id: number;
  label: string;
};

const TRACKING_STATUS_OPTIONS = [
  { value: "planning_ok", label: "Planning OK" },
  { value: "planned", label: "Planned" },
  { value: "moved_export", label: "Moved export" },
  { value: "boarding_ok", label: "Boarding OK" },
  { value: "received_correspondent", label: "Received correspondent" },
  { value: "received_recipient", label: "Received recipient" },
];

function toErrorMessage(error: unknown): string {
  if (error instanceof ApiClientError) {
    return `${error.message} (${error.code})`;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return String(error);
}

function toIdOptions(rows: RawOptionRow[], labelKeys: string[]): IdOption[] {
  return rows
    .map((row) => {
      const rawId = row.id;
      const id = typeof rawId === "number" ? rawId : Number(rawId);
      if (!Number.isInteger(id) || id <= 0) {
        return null;
      }
      const labelValue = labelKeys
        .map((key) => row[key])
        .find((value) => typeof value === "string" && value.trim().length > 0) as
        | string
        | undefined;
      return {
        id,
        label: labelValue ? labelValue.trim() : `#${id}`,
      };
    })
    .filter((item): item is IdOption => Boolean(item));
}

function parseId(rawValue: string): number | null {
  const value = Number(rawValue.trim());
  if (!Number.isInteger(value) || value <= 0) {
    return null;
  }
  return value;
}

export function ScanShipmentOptionsLive() {
  const [data, setData] = useState<ShipmentFormOptionsDto | null>(null);
  const [error, setError] = useState<string>("");
  const [mutationError, setMutationError] = useState<string>("");
  const [mutationStatus, setMutationStatus] = useState<string>("");
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [defaultsApplied, setDefaultsApplied] = useState<boolean>(false);

  const [destinationId, setDestinationId] = useState<string>("");
  const [shipperId, setShipperId] = useState<string>("");
  const [recipientId, setRecipientId] = useState<string>("");
  const [correspondentId, setCorrespondentId] = useState<string>("");
  const [cartonId, setCartonId] = useState<string>("");
  const [createProductCode, setCreateProductCode] = useState<string>("");
  const [createQuantity, setCreateQuantity] = useState<string>("");
  const [trackingShipmentId, setTrackingShipmentId] = useState<string>("");
  const [trackingStatus, setTrackingStatus] = useState<string>(
    TRACKING_STATUS_OPTIONS[0].value,
  );
  const [actorName, setActorName] = useState<string>("Operateur");
  const [actorStructure, setActorStructure] = useState<string>("ASF");
  const [closeShipmentId, setCloseShipmentId] = useState<string>("");

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

  const destinations = useMemo<IdOption[]>(
    () => toIdOptions(data?.destinations || [], ["label", "city", "name"]),
    [data],
  );
  const shippers = useMemo<IdOption[]>(
    () => toIdOptions(data?.shipper_contacts || [], ["label", "name", "display_name"]),
    [data],
  );
  const recipients = useMemo<IdOption[]>(
    () => toIdOptions(data?.recipient_contacts || [], ["label", "name", "display_name"]),
    [data],
  );
  const correspondents = useMemo<IdOption[]>(
    () => toIdOptions(data?.correspondent_contacts || [], ["label", "name", "display_name"]),
    [data],
  );
  const cartons = useMemo<IdOption[]>(
    () => toIdOptions(data?.available_cartons || [], ["code", "label", "name"]),
    [data],
  );

  useEffect(() => {
    if (!data || defaultsApplied) {
      return;
    }
    if (!destinationId && destinations.length) {
      setDestinationId(String(destinations[0].id));
    }
    if (!shipperId && shippers.length) {
      setShipperId(String(shippers[0].id));
    }
    if (!recipientId && recipients.length) {
      setRecipientId(String(recipients[0].id));
    }
    if (!correspondentId && correspondents.length) {
      setCorrespondentId(String(correspondents[0].id));
    }
    if (!cartonId && cartons.length) {
      setCartonId(String(cartons[0].id));
    }
    setDefaultsApplied(true);
  }, [
    cartonId,
    cartons,
    correspondentId,
    correspondents,
    data,
    defaultsApplied,
    destinationId,
    destinations,
    recipientId,
    recipients,
    shipperId,
    shippers,
  ]);

  const onCreateShipment = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const parsedDestination = parseId(destinationId);
    const parsedShipper = parseId(shipperId);
    const parsedRecipient = parseId(recipientId);
    const parsedCorrespondent = parseId(correspondentId);
    const parsedCarton = parseId(cartonId);
    const productCode = createProductCode.trim();
    const hasProductFields = productCode.length > 0 || createQuantity.trim().length > 0;
    const parsedCreateQuantity = parseId(createQuantity);
    if (
      !parsedDestination ||
      !parsedShipper ||
      !parsedRecipient ||
      !parsedCorrespondent
    ) {
      setMutationError("Parametres creation expedition invalides.");
      return;
    }
    let linePayload:
      | { carton_id: number }
      | { product_code: string; quantity: number }
      | null = null;
    if (parsedCarton) {
      if (hasProductFields) {
        setMutationError("Choisir carton ou produit+quantite, pas les deux.");
        return;
      }
      linePayload = { carton_id: parsedCarton };
    } else {
      if (!productCode || !parsedCreateQuantity) {
        setMutationError("Carton ID ou produit+quantite requis.");
        return;
      }
      linePayload = { product_code: productCode, quantity: parsedCreateQuantity };
    }

    setIsSubmitting(true);
    setMutationError("");
    setMutationStatus("");
    try {
      const response = await postShipmentCreate({
        destination: parsedDestination,
        shipper_contact: parsedShipper,
        recipient_contact: parsedRecipient,
        correspondent_contact: parsedCorrespondent,
        lines: [linePayload],
      });
      const createdId = response.shipment.id;
      setTrackingShipmentId(String(createdId));
      setCloseShipmentId(String(createdId));
      setMutationStatus(`${response.message} Shipment #${createdId}.`);
    } catch (err: unknown) {
      setMutationError(toErrorMessage(err));
    } finally {
      setIsSubmitting(false);
    }
  };

  const onTrackingSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const shipmentId = parseId(trackingShipmentId);
    if (!shipmentId) {
      setMutationError("Shipment ID (Tracking) invalide.");
      return;
    }
    setIsSubmitting(true);
    setMutationError("");
    setMutationStatus("");
    try {
      const response = await postShipmentTrackingEvent(shipmentId, {
        status: trackingStatus,
        actor_name: actorName.trim(),
        actor_structure: actorStructure.trim(),
        comments: "",
      });
      setMutationStatus(response.message);
    } catch (err: unknown) {
      setMutationError(toErrorMessage(err));
    } finally {
      setIsSubmitting(false);
    }
  };

  const onCloseShipment = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const shipmentId = parseId(closeShipmentId);
    if (!shipmentId) {
      setMutationError("Shipment ID (Cloture) invalide.");
      return;
    }
    setIsSubmitting(true);
    setMutationError("");
    setMutationStatus("");
    try {
      const response = await postShipmentClose(shipmentId);
      setMutationStatus(response.message);
    } catch (err: unknown) {
      setMutationError(toErrorMessage(err));
    } finally {
      setIsSubmitting(false);
    }
  };

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
    <div className="stack-grid">
      <div className="api-state api-ok">
        API connectee. Destinations {data.destinations.length}, expediteurs{" "}
        {data.shipper_contacts.length}, destinataires {data.recipient_contacts.length},
        cartons dispo {data.available_cartons.length}.
      </div>

      <form className="inline-form" onSubmit={onCreateShipment}>
        <label className="field-inline">
          Destination ID
          <select
            value={destinationId}
            onChange={(event) => setDestinationId(event.target.value)}
          >
            {destinations.map((item) => (
              <option key={item.id} value={item.id}>
                {item.id} - {item.label}
              </option>
            ))}
          </select>
        </label>
        <label className="field-inline">
          Expediteur ID
          <select value={shipperId} onChange={(event) => setShipperId(event.target.value)}>
            {shippers.map((item) => (
              <option key={item.id} value={item.id}>
                {item.id} - {item.label}
              </option>
            ))}
          </select>
        </label>
        <label className="field-inline">
          Destinataire ID
          <select
            value={recipientId}
            onChange={(event) => setRecipientId(event.target.value)}
          >
            {recipients.map((item) => (
              <option key={item.id} value={item.id}>
                {item.id} - {item.label}
              </option>
            ))}
          </select>
        </label>
        <label className="field-inline">
          Correspondant ID
          <select
            value={correspondentId}
            onChange={(event) => setCorrespondentId(event.target.value)}
          >
            {correspondents.map((item) => (
              <option key={item.id} value={item.id}>
                {item.id} - {item.label}
              </option>
            ))}
          </select>
        </label>
        <label className="field-inline">
          Carton ID
          <select value={cartonId} onChange={(event) => setCartonId(event.target.value)}>
            <option value="">-- creer colis depuis produit --</option>
            {cartons.map((item) => (
              <option key={item.id} value={item.id}>
                {item.id} - {item.label}
              </option>
            ))}
          </select>
        </label>
        <label className="field-inline">
          Product code (Creation)
          <input
            value={createProductCode}
            onChange={(event) => setCreateProductCode(event.target.value)}
          />
        </label>
        <label className="field-inline">
          Quantite (Creation)
          <input
            value={createQuantity}
            onChange={(event) => setCreateQuantity(event.target.value)}
            inputMode="numeric"
          />
        </label>
        <button
          type="submit"
          className="btn-primary"
          data-track="shipment.create.submit"
          disabled={isSubmitting}
        >
          Creer expedition
        </button>
      </form>

      <form className="inline-form" onSubmit={onTrackingSubmit}>
        <label className="field-inline">
          Shipment ID (Tracking)
          <input
            value={trackingShipmentId}
            onChange={(event) => setTrackingShipmentId(event.target.value)}
            inputMode="numeric"
          />
        </label>
        <label className="field-inline">
          Status tracking
          <select
            value={trackingStatus}
            onChange={(event) => setTrackingStatus(event.target.value)}
          >
            {TRACKING_STATUS_OPTIONS.map((item) => (
              <option key={item.value} value={item.value}>
                {item.label}
              </option>
            ))}
          </select>
        </label>
        <label className="field-inline">
          Actor name
          <input
            value={actorName}
            onChange={(event) => setActorName(event.target.value)}
          />
        </label>
        <label className="field-inline">
          Actor structure
          <input
            value={actorStructure}
            onChange={(event) => setActorStructure(event.target.value)}
          />
        </label>
        <button
          type="submit"
          className="btn-secondary"
          data-track="shipment.tracking.submit"
          disabled={isSubmitting}
        >
          Envoyer tracking
        </button>
      </form>

      <form className="inline-form" onSubmit={onCloseShipment}>
        <label className="field-inline">
          Shipment ID (Cloture)
          <input
            value={closeShipmentId}
            onChange={(event) => setCloseShipmentId(event.target.value)}
            inputMode="numeric"
          />
        </label>
        <button
          type="submit"
          className="btn-secondary"
          data-track="shipment.close.submit"
          disabled={isSubmitting}
        >
          Cloturer expedition
        </button>
      </form>

      {mutationStatus ? <div className="api-state api-ok">{mutationStatus}</div> : null}
      {mutationError ? (
        <div className="api-state api-error">
          Mutation expedition indisponible: <span>{mutationError}</span>
        </div>
      ) : null}
    </div>
  );
}
