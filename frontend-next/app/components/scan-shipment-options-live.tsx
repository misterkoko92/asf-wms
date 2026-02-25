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
type DestinationOption = IdOption & {
  correspondentContactId: string;
};
type ContactOption = IdOption & {
  destinationId: string;
  destinationIds: string[];
  linkedShipperIds: string[];
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

function toStringValue(value: unknown): string {
  if (typeof value === "string") {
    return value.trim();
  }
  if (typeof value === "number") {
    return String(value);
  }
  return "";
}

function toStringList(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.map((entry) => toStringValue(entry)).filter((entry) => entry.length > 0);
}

function toDestinationOptions(rows: RawOptionRow[]): DestinationOption[] {
  return rows
    .map((row) => {
      const rawId = row.id;
      const id = typeof rawId === "number" ? rawId : Number(rawId);
      if (!Number.isInteger(id) || id <= 0) {
        return null;
      }
      const labelValue = ["label", "city", "name", "country"]
        .map((key) => row[key])
        .find((value) => typeof value === "string" && value.trim().length > 0) as
        | string
        | undefined;
      return {
        id,
        label: labelValue ? labelValue.trim() : `#${id}`,
        correspondentContactId: toStringValue(row.correspondent_contact_id),
      };
    })
    .filter((item): item is DestinationOption => Boolean(item));
}

function toContactOptions(rows: RawOptionRow[]): ContactOption[] {
  return rows
    .map((row) => {
      const rawId = row.id;
      const id = typeof rawId === "number" ? rawId : Number(rawId);
      if (!Number.isInteger(id) || id <= 0) {
        return null;
      }
      const labelValue = ["label", "name", "display_name"]
        .map((key) => row[key])
        .find((value) => typeof value === "string" && value.trim().length > 0) as
        | string
        | undefined;
      return {
        id,
        label: labelValue ? labelValue.trim() : `#${id}`,
        destinationId: toStringValue(row.destination_id),
        destinationIds: toStringList(row.destination_ids),
        linkedShipperIds: toStringList(row.linked_shipper_ids),
      };
    })
    .filter((item): item is ContactOption => Boolean(item));
}

function hasOptionValue(value: string, options: IdOption[]): boolean {
  return options.some((item) => String(item.id) === value);
}

function resolveSelectedValue(value: string, options: IdOption[]): string {
  return hasOptionValue(value, options) ? value : "";
}

function matchesDestination(contact: ContactOption, destinationId: string): boolean {
  if (!destinationId) {
    return false;
  }
  if (contact.destinationIds.length > 0) {
    return contact.destinationIds.includes(destinationId);
  }
  if (contact.destinationId) {
    return contact.destinationId === destinationId;
  }
  return true;
}

function matchesLinkedShipper(contact: ContactOption, shipperId: string): boolean {
  if (!shipperId) {
    return false;
  }
  if (contact.linkedShipperIds.length === 0) {
    return true;
  }
  return contact.linkedShipperIds.includes(shipperId);
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

  const destinations = useMemo<DestinationOption[]>(
    () => toDestinationOptions(data?.destinations || []),
    [data],
  );
  const shippers = useMemo<ContactOption[]>(
    () => toContactOptions(data?.shipper_contacts || []),
    [data],
  );
  const recipients = useMemo<ContactOption[]>(
    () => toContactOptions(data?.recipient_contacts || []),
    [data],
  );
  const correspondents = useMemo<ContactOption[]>(
    () => toContactOptions(data?.correspondent_contacts || []),
    [data],
  );
  const cartons = useMemo<IdOption[]>(
    () => toIdOptions(data?.available_cartons || [], ["code", "label", "name"]),
    [data],
  );

  const selectedDestinationId = resolveSelectedValue(destinationId, destinations);
  const destination = useMemo<DestinationOption | null>(() => {
    if (!selectedDestinationId) {
      return null;
    }
    return (
      destinations.find((item) => String(item.id) === selectedDestinationId) || null
    );
  }, [destinations, selectedDestinationId]);
  const shipperOptions = useMemo<ContactOption[]>(
    () =>
      selectedDestinationId
        ? shippers.filter((contact) => matchesDestination(contact, selectedDestinationId))
        : [],
    [selectedDestinationId, shippers],
  );
  const canShowShipperSection = Boolean(selectedDestinationId);
  const selectedShipperId = resolveSelectedValue(shipperId, shipperOptions);
  const canShowRecipientAndCorrespondent = Boolean(
    selectedDestinationId && selectedShipperId,
  );
  const recipientOptions = useMemo<ContactOption[]>(
    () =>
      canShowRecipientAndCorrespondent
        ? recipients.filter(
            (contact) =>
              matchesDestination(contact, selectedDestinationId) &&
              matchesLinkedShipper(contact, selectedShipperId),
          )
        : [],
    [
      canShowRecipientAndCorrespondent,
      recipients,
      selectedDestinationId,
      selectedShipperId,
    ],
  );
  const correspondentOptions = useMemo<ContactOption[]>(
    () =>
      canShowRecipientAndCorrespondent
        ? correspondents.filter((contact) => {
            if (!matchesDestination(contact, selectedDestinationId)) {
              return false;
            }
            if (!destination?.correspondentContactId) {
              return false;
            }
            return String(contact.id) === destination.correspondentContactId;
          })
        : [],
    [
      canShowRecipientAndCorrespondent,
      correspondents,
      destination?.correspondentContactId,
      selectedDestinationId,
    ],
  );
  const selectedRecipientId = resolveSelectedValue(recipientId, recipientOptions);
  const selectedCorrespondentId = resolveSelectedValue(
    correspondentId,
    correspondentOptions,
  );
  const canShowCreateDetails = Boolean(
    canShowRecipientAndCorrespondent &&
      selectedRecipientId &&
      selectedCorrespondentId,
  );
  const selectedCartonId = canShowCreateDetails
    ? resolveSelectedValue(cartonId, cartons)
    : "";

  useEffect(() => {
    setDestinationId((current) => resolveSelectedValue(current, destinations));
  }, [destinations]);

  useEffect(() => {
    setShipperId((current) => {
      if (!selectedDestinationId) {
        return "";
      }
      return resolveSelectedValue(current, shipperOptions);
    });
  }, [selectedDestinationId, shipperOptions]);

  useEffect(() => {
    setRecipientId((current) => {
      if (!canShowRecipientAndCorrespondent) {
        return "";
      }
      return resolveSelectedValue(current, recipientOptions);
    });
  }, [canShowRecipientAndCorrespondent, recipientOptions]);

  useEffect(() => {
    setCorrespondentId((current) => {
      if (!canShowRecipientAndCorrespondent) {
        return "";
      }
      return resolveSelectedValue(current, correspondentOptions);
    });
  }, [canShowRecipientAndCorrespondent, correspondentOptions]);

  useEffect(() => {
    setCartonId((current) => {
      if (!canShowCreateDetails) {
        return "";
      }
      return resolveSelectedValue(current, cartons);
    });
  }, [canShowCreateDetails, cartons]);

  const showShipperEmptyMessage = canShowShipperSection && shipperOptions.length === 0;
  const showRecipientEmptyMessage =
    canShowRecipientAndCorrespondent && recipientOptions.length === 0;
  const showCorrespondentEmptyMessage =
    canShowRecipientAndCorrespondent && correspondentOptions.length === 0;
  const canSubmitCreate = canShowCreateDetails;

  const onCreateShipment = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const parsedDestination = parseId(selectedDestinationId);
    const parsedShipper = parseId(selectedShipperId);
    const parsedRecipient = parseId(selectedRecipientId);
    const parsedCorrespondent = parseId(selectedCorrespondentId);
    const parsedCarton = parseId(selectedCartonId);
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
        setMutationError("Carton ou produit+quantite requis.");
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
      setMutationError("Expedition (Tracking) invalide.");
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
      setMutationError("Expedition (Cloture) invalide.");
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
          Destination
          <select
            aria-label="Destination"
            value={selectedDestinationId}
            onChange={(event) => setDestinationId(event.target.value)}
          >
            <option value="">---</option>
            {destinations.map((item) => (
              <option key={item.id} value={item.id}>
                {item.label}
              </option>
            ))}
          </select>
          <a
            className="btn-secondary"
            href="/admin/wms/destination/add/"
            target="_blank"
            rel="noreferrer"
          >
            Ajouter destination
          </a>
          <div className="api-state">
            Merci de selectionner une destination pour poursuivre la creation de
            l'expedition.
          </div>
        </label>
        {canShowShipperSection ? (
          <label className="field-inline">
            Expediteur
            <select
              aria-label="Expediteur"
              value={selectedShipperId}
              onChange={(event) => setShipperId(event.target.value)}
            >
              <option value="">---</option>
              {shipperOptions.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.label}
                </option>
              ))}
            </select>
            <a
              className="btn-secondary"
              href="/admin/contacts/contact/add/"
              target="_blank"
              rel="noreferrer"
            >
              Ajouter expediteur
            </a>
            <div className="api-state">
              Merci de selectionner un expediteur pour poursuivre la creation de
              l'expedition.
            </div>
            {showShipperEmptyMessage ? (
              <div className="api-state api-error">
                Aucun expediteur trouve dans la base, verifier les "Destinations"
                des affectes aux Expediteurs dans les contacts et recommencez
              </div>
            ) : null}
          </label>
        ) : null}
        {canShowRecipientAndCorrespondent ? (
          <>
            <label className="field-inline">
              Destinataire
              <select
                aria-label="Destinataire"
                value={selectedRecipientId}
                onChange={(event) => setRecipientId(event.target.value)}
              >
                <option value="">---</option>
                {recipientOptions.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.label}
                  </option>
                ))}
              </select>
              <a
                className="btn-secondary"
                href="/admin/contacts/contact/add/"
                target="_blank"
                rel="noreferrer"
              >
                Ajouter destinataire
              </a>
              {showRecipientEmptyMessage ? (
                <div className="api-state api-error">
                  Aucun destinataire trouve dans la base, verifier les "Expediteurs
                  Lies" dans les contacts et recommencez
                </div>
              ) : null}
            </label>
            <label className="field-inline">
              Correspondant
              <select
                aria-label="Correspondant"
                value={selectedCorrespondentId}
                onChange={(event) => setCorrespondentId(event.target.value)}
              >
                <option value="">---</option>
                {correspondentOptions.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.label}
                  </option>
                ))}
              </select>
              <a
                className="btn-secondary"
                href="/admin/contacts/contact/add/"
                target="_blank"
                rel="noreferrer"
              >
                Ajouter correspondant
              </a>
              <div className="api-state">
                Merci de selectionner un destinataire et un correspondant pour
                poursuivre la creation de l'expedition.
              </div>
              {showCorrespondentEmptyMessage ? (
                <div className="api-state api-error">
                  Aucun correspondant trouve dans la base, verifier les
                  "Correspondants" dans les contacts et recommencez
                </div>
              ) : null}
            </label>
          </>
        ) : null}
        {canSubmitCreate ? (
          <>
            <label className="field-inline">
              Carton
              <select
                aria-label="Carton"
                value={selectedCartonId}
                onChange={(event) => setCartonId(event.target.value)}
              >
                <option value="">-- creer colis depuis produit --</option>
                {cartons.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.label}
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
          </>
        ) : (
          <div className="api-state">
            Merci de selectionner destination, expediteur, destinataire et
            correspondant pour activer la creation expedition.
          </div>
        )}
      </form>

      <form className="inline-form" onSubmit={onTrackingSubmit}>
        <label className="field-inline">
          Expedition (Tracking)
          <input
            aria-label="Expedition (Tracking)"
            value={trackingShipmentId}
            onChange={(event) => setTrackingShipmentId(event.target.value)}
            inputMode="numeric"
          />
        </label>
        <label className="field-inline">
          Statut tracking
          <select
            aria-label="Statut tracking"
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
          Nom acteur
          <input
            aria-label="Nom acteur"
            value={actorName}
            onChange={(event) => setActorName(event.target.value)}
          />
        </label>
        <label className="field-inline">
          Structure acteur
          <input
            aria-label="Structure acteur"
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
          Expedition (Cloture)
          <input
            aria-label="Expedition (Cloture)"
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
