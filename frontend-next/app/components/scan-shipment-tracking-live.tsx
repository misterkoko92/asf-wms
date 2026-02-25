"use client";

import { useState, type FormEvent } from "react";

import { ApiClientError } from "../lib/api/client";
import { postShipmentClose, postShipmentTrackingEvent } from "../lib/api/ui";

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

function parseId(rawValue: string): number | null {
  const value = Number(rawValue.trim());
  if (!Number.isInteger(value) || value <= 0) {
    return null;
  }
  return value;
}

export function ScanShipmentTrackingLive() {
  const [trackingShipmentId, setTrackingShipmentId] = useState<string>("");
  const [trackingStatus, setTrackingStatus] = useState<string>(
    TRACKING_STATUS_OPTIONS[0].value,
  );
  const [actorName, setActorName] = useState<string>("Operateur");
  const [actorStructure, setActorStructure] = useState<string>("ASF");
  const [closeShipmentId, setCloseShipmentId] = useState<string>("");
  const [mutationError, setMutationError] = useState<string>("");
  const [mutationStatus, setMutationStatus] = useState<string>("");
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);

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
      setCloseShipmentId(String(shipmentId));
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

  return (
    <div className="stack-grid">
      <div className="api-state api-ok">
        API suivi connectee. Mise a jour des etapes et cloture de dossier depuis l&apos;ID
        expedition.
      </div>

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
