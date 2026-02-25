"use client";

import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";

import { ApiClientError } from "../lib/api/client";
import {
  getPortalAccount,
  getPortalDashboard,
  getPortalRecipients,
  patchPortalAccount,
  patchPortalRecipient,
  postPortalOrder,
  postPortalRecipient,
} from "../lib/api/ui";
import type {
  PortalDashboardDto,
  UiPortalAccountDto,
  UiPortalAccountUpdateInput,
  UiPortalRecipient,
  UiPortalRecipientInput,
  UiPortalRecipientsDto,
} from "../lib/api/types";

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

function findRecipientById(recipients: UiPortalRecipient[], recipientId: string) {
  const parsedId = parsePositiveInteger(recipientId);
  if (!parsedId) {
    return null;
  }
  return recipients.find((recipient) => recipient.id === parsedId) || null;
}

export function PortalDashboardLive() {
  const [dashboardData, setDashboardData] = useState<PortalDashboardDto | null>(null);
  const [recipientsData, setRecipientsData] = useState<UiPortalRecipientsDto | null>(null);
  const [accountData, setAccountData] = useState<UiPortalAccountDto | null>(null);
  const [error, setError] = useState<string>("");
  const [mutationError, setMutationError] = useState<string>("");
  const [mutationStatus, setMutationStatus] = useState<string>("");
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);

  const [orderDestinationId, setOrderDestinationId] = useState<string>("");
  const [orderRecipientId, setOrderRecipientId] = useState<string>("");
  const [orderProductId, setOrderProductId] = useState<string>("");
  const [orderQuantity, setOrderQuantity] = useState<string>("1");
  const [orderNotes, setOrderNotes] = useState<string>("Workflow navigateur Next");

  const [recipientDestinationId, setRecipientDestinationId] = useState<string>("");
  const [recipientStructureName, setRecipientStructureName] = useState<string>("");
  const [recipientAddressLine1, setRecipientAddressLine1] = useState<string>("");
  const [recipientPostalCode, setRecipientPostalCode] = useState<string>("");
  const [recipientCity, setRecipientCity] = useState<string>("");
  const [recipientCountry, setRecipientCountry] = useState<string>("France");

  const [editRecipientId, setEditRecipientId] = useState<string>("");
  const [editRecipientDestinationId, setEditRecipientDestinationId] = useState<string>("");
  const [editRecipientStructureName, setEditRecipientStructureName] = useState<string>("");
  const [editRecipientAddressLine1, setEditRecipientAddressLine1] = useState<string>("");
  const [editRecipientPostalCode, setEditRecipientPostalCode] = useState<string>("");
  const [editRecipientCity, setEditRecipientCity] = useState<string>("");
  const [editRecipientCountry, setEditRecipientCountry] = useState<string>("France");

  const [accountAssociationName, setAccountAssociationName] = useState<string>("");
  const [accountAssociationEmail, setAccountAssociationEmail] = useState<string>("");
  const [accountAssociationPhone, setAccountAssociationPhone] = useState<string>("");
  const [accountAddressLine1, setAccountAddressLine1] = useState<string>("");
  const [accountPostalCode, setAccountPostalCode] = useState<string>("");
  const [accountCity, setAccountCity] = useState<string>("");
  const [accountCountry, setAccountCountry] = useState<string>("France");
  const [accountContactEmail, setAccountContactEmail] = useState<string>("");

  const recipients = recipientsData?.recipients || [];
  const destinations = recipientsData?.destinations || [];
  const selectedRecipient = useMemo(
    () => findRecipientById(recipients, editRecipientId),
    [editRecipientId, recipients],
  );

  const applyRecipientToEditForm = useCallback((recipient: UiPortalRecipient | null) => {
    if (!recipient) {
      return;
    }
    setEditRecipientId(String(recipient.id));
    setEditRecipientDestinationId(String(recipient.destination_id || ""));
    setEditRecipientStructureName(recipient.structure_name || recipient.display_name || "");
    setEditRecipientAddressLine1(recipient.address_line1 || "");
    setEditRecipientPostalCode(recipient.postal_code || "");
    setEditRecipientCity(recipient.city || "");
    setEditRecipientCountry(recipient.country || "France");
  }, []);

  const applyAccountToForm = useCallback((account: UiPortalAccountDto) => {
    setAccountAssociationName(account.association_name || "");
    setAccountAssociationEmail(account.association_email || "");
    setAccountAssociationPhone(account.association_phone || "");
    setAccountAddressLine1(account.address_line1 || "");
    setAccountPostalCode(account.postal_code || "");
    setAccountCity(account.city || "");
    setAccountCountry(account.country || "France");
    const defaultContactEmail =
      account.portal_contacts[0]?.email || account.association_email || "";
    setAccountContactEmail(defaultContactEmail);
  }, []);

  const loadPortalData = useCallback(async () => {
    setError("");
    try {
      const [dashboardPayload, recipientsPayload, accountPayload] = await Promise.all([
        getPortalDashboard(),
        getPortalRecipients(),
        getPortalAccount(),
      ]);
      setDashboardData(dashboardPayload);
      setRecipientsData(recipientsPayload);
      setAccountData(accountPayload);

      if (recipientsPayload.destinations.length > 0) {
        const firstDestination = recipientsPayload.destinations[0];
        setOrderDestinationId(
          (current) => current || String(firstDestination.id),
        );
        setRecipientDestinationId(
          (current) => current || String(firstDestination.id),
        );
      }
      if (recipientsPayload.recipients.length > 0) {
        setOrderRecipientId((current) => current || String(recipientsPayload.recipients[0].id));
      }

      if (recipientsPayload.recipients.length > 0) {
        const recipientToEdit =
          recipientsPayload.recipients.find(
            (recipient) => String(recipient.id) === editRecipientId,
          ) || recipientsPayload.recipients[0];
        applyRecipientToEditForm(recipientToEdit);
      }
      applyAccountToForm(accountPayload);
    } catch (err: unknown) {
      setDashboardData(null);
      setRecipientsData(null);
      setAccountData(null);
      setError(toErrorMessage(err));
    }
  }, [
    applyAccountToForm,
    applyRecipientToEditForm,
    editRecipientId,
  ]);

  useEffect(() => {
    loadPortalData().catch(() => undefined);
  }, [loadPortalData]);

  useEffect(() => {
    if (selectedRecipient) {
      applyRecipientToEditForm(selectedRecipient);
    }
  }, [applyRecipientToEditForm, selectedRecipient]);

  const onOrderSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const destinationId = parsePositiveInteger(orderDestinationId);
    const productId = parsePositiveInteger(orderProductId);
    const quantity = parsePositiveInteger(orderQuantity);
    if (!destinationId) {
      setMutationError("Destination ID (Commande) invalide.");
      return;
    }
    if (!orderRecipientId.trim()) {
      setMutationError("Destinataire ID (Commande) requis.");
      return;
    }
    if (!productId) {
      setMutationError("Product ID (Commande) invalide.");
      return;
    }
    if (!quantity) {
      setMutationError("Quantite (Commande) invalide.");
      return;
    }
    setMutationError("");
    setMutationStatus("");
    setIsSubmitting(true);
    try {
      const response = await postPortalOrder({
        destination_id: destinationId,
        recipient_id: orderRecipientId.trim(),
        notes: orderNotes.trim(),
        lines: [{ product_id: productId, quantity }],
      });
      await loadPortalData();
      setMutationStatus(response.message);
    } catch (err: unknown) {
      setMutationError(toErrorMessage(err));
    } finally {
      setIsSubmitting(false);
    }
  };

  const onRecipientCreateSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const destinationId = parsePositiveInteger(recipientDestinationId);
    if (!destinationId) {
      setMutationError("Destination ID (Destinataire) invalide.");
      return;
    }
    if (!recipientStructureName.trim()) {
      setMutationError("Structure (Destinataire) requise.");
      return;
    }
    if (!recipientAddressLine1.trim()) {
      setMutationError("Adresse 1 (Destinataire) requise.");
      return;
    }
    const payload: UiPortalRecipientInput = {
      destination_id: destinationId,
      structure_name: recipientStructureName.trim(),
      address_line1: recipientAddressLine1.trim(),
      postal_code: recipientPostalCode.trim(),
      city: recipientCity.trim(),
      country: recipientCountry.trim() || "France",
      notify_deliveries: false,
      is_delivery_contact: true,
    };
    setMutationError("");
    setMutationStatus("");
    setIsSubmitting(true);
    try {
      const response = await postPortalRecipient(payload);
      const createdRecipientId = String(response.recipient.id);
      setOrderRecipientId(createdRecipientId);
      setEditRecipientId(createdRecipientId);
      applyRecipientToEditForm(response.recipient);
      await loadPortalData();
      setOrderRecipientId(createdRecipientId);
      setEditRecipientId(createdRecipientId);
      applyRecipientToEditForm(response.recipient);
      setMutationStatus(response.message);
    } catch (err: unknown) {
      setMutationError(toErrorMessage(err));
    } finally {
      setIsSubmitting(false);
    }
  };

  const onRecipientEditSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const recipientId = parsePositiveInteger(editRecipientId);
    const destinationId = parsePositiveInteger(editRecipientDestinationId);
    if (!recipientId) {
      setMutationError("Recipient ID (Edition) invalide.");
      return;
    }
    if (!destinationId) {
      setMutationError("Destination ID (Edition) invalide.");
      return;
    }
    if (!editRecipientStructureName.trim()) {
      setMutationError("Structure (Edition) requise.");
      return;
    }
    if (!editRecipientAddressLine1.trim()) {
      setMutationError("Adresse 1 (Edition) requise.");
      return;
    }
    const payload: UiPortalRecipientInput = {
      destination_id: destinationId,
      structure_name: editRecipientStructureName.trim(),
      address_line1: editRecipientAddressLine1.trim(),
      postal_code: editRecipientPostalCode.trim(),
      city: editRecipientCity.trim(),
      country: editRecipientCountry.trim() || "France",
      notify_deliveries: false,
      is_delivery_contact: true,
    };
    setMutationError("");
    setMutationStatus("");
    setIsSubmitting(true);
    try {
      const response = await patchPortalRecipient(recipientId, payload);
      applyRecipientToEditForm(response.recipient);
      await loadPortalData();
      applyRecipientToEditForm(response.recipient);
      setMutationStatus(response.message);
    } catch (err: unknown) {
      setMutationError(toErrorMessage(err));
    } finally {
      setIsSubmitting(false);
    }
  };

  const onAccountSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!accountAssociationName.trim()) {
      setMutationError("Association name (Compte) requis.");
      return;
    }
    if (!accountAddressLine1.trim()) {
      setMutationError("Adresse 1 (Compte) requise.");
      return;
    }
    if (!accountContactEmail.trim()) {
      setMutationError("Email contact (Compte) requis.");
      return;
    }
    const payload: UiPortalAccountUpdateInput = {
      association_name: accountAssociationName.trim(),
      association_email: accountAssociationEmail.trim(),
      association_phone: accountAssociationPhone.trim(),
      address_line1: accountAddressLine1.trim(),
      address_line2: "",
      postal_code: accountPostalCode.trim(),
      city: accountCity.trim(),
      country: accountCountry.trim() || "France",
      contacts: [
        {
          email: accountContactEmail.trim(),
          is_administrative: true,
          is_shipping: false,
          is_billing: false,
        },
      ],
    };
    setMutationError("");
    setMutationStatus("");
    setIsSubmitting(true);
    try {
      const response = await patchPortalAccount(payload);
      setMutationStatus(response.message);
      setAccountData(response.account);
      applyAccountToForm(response.account);
    } catch (err: unknown) {
      setMutationError(toErrorMessage(err));
    } finally {
      setIsSubmitting(false);
    }
  };

  if (error) {
    return (
      <div className="api-state api-error">
        API portal indisponible: <span>{error}</span>
      </div>
    );
  }

  if (!dashboardData || !recipientsData || !accountData) {
    return <div className="api-state">Chargement API portal...</div>;
  }

  return (
    <div className="stack-grid">
      <div className="api-state api-ok">
        API portal connectee. Commandes {dashboardData.kpis.orders_total}, en attente validation{" "}
        {dashboardData.kpis.orders_pending_review}, avec expedition{" "}
        {dashboardData.kpis.orders_with_shipment}.
      </div>

      <form className="inline-form" onSubmit={onOrderSubmit}>
        <label className="field-inline">
          Destination ID (Commande)
          <select
            value={orderDestinationId}
            onChange={(event) => setOrderDestinationId(event.target.value)}
          >
            {destinations.map((destination) => (
              <option key={destination.id} value={destination.id}>
                {destination.id} - {destination.label}
              </option>
            ))}
          </select>
        </label>
        <label className="field-inline">
          Destinataire ID (Commande)
          <select
            value={orderRecipientId}
            onChange={(event) => setOrderRecipientId(event.target.value)}
          >
            {recipients.map((recipient) => (
              <option key={recipient.id} value={recipient.id}>
                {recipient.id} - {recipient.display_name}
              </option>
            ))}
          </select>
        </label>
        <label className="field-inline">
          Product ID (Commande)
          <input
            value={orderProductId}
            onChange={(event) => setOrderProductId(event.target.value)}
            inputMode="numeric"
          />
        </label>
        <label className="field-inline">
          Quantite (Commande)
          <input
            value={orderQuantity}
            onChange={(event) => setOrderQuantity(event.target.value)}
            inputMode="numeric"
          />
        </label>
        <label className="field-inline">
          Notes (Commande)
          <input value={orderNotes} onChange={(event) => setOrderNotes(event.target.value)} />
        </label>
        <button
          type="submit"
          className="btn-primary"
          data-track="portal.order.submit"
          disabled={isSubmitting}
        >
          Envoyer commande
        </button>
      </form>

      <form className="inline-form" onSubmit={onRecipientCreateSubmit}>
        <label className="field-inline">
          Destination ID (Destinataire)
          <select
            value={recipientDestinationId}
            onChange={(event) => setRecipientDestinationId(event.target.value)}
          >
            {destinations.map((destination) => (
              <option key={destination.id} value={destination.id}>
                {destination.id} - {destination.label}
              </option>
            ))}
          </select>
        </label>
        <label className="field-inline">
          Structure (Destinataire)
          <input
            value={recipientStructureName}
            onChange={(event) => setRecipientStructureName(event.target.value)}
          />
        </label>
        <label className="field-inline">
          Adresse 1 (Destinataire)
          <input
            value={recipientAddressLine1}
            onChange={(event) => setRecipientAddressLine1(event.target.value)}
          />
        </label>
        <label className="field-inline">
          CP (Destinataire)
          <input
            value={recipientPostalCode}
            onChange={(event) => setRecipientPostalCode(event.target.value)}
          />
        </label>
        <label className="field-inline">
          Ville (Destinataire)
          <input value={recipientCity} onChange={(event) => setRecipientCity(event.target.value)} />
        </label>
        <button
          type="submit"
          className="btn-secondary"
          data-track="portal.recipient.create"
          disabled={isSubmitting}
        >
          Ajouter destinataire
        </button>
      </form>

      <form className="inline-form" onSubmit={onRecipientEditSubmit}>
        <label className="field-inline">
          Recipient ID (Edition)
          <select
            value={editRecipientId}
            onChange={(event) => setEditRecipientId(event.target.value)}
          >
            {recipients.map((recipient) => (
              <option key={recipient.id} value={recipient.id}>
                {recipient.id} - {recipient.display_name}
              </option>
            ))}
          </select>
        </label>
        <label className="field-inline">
          Destination ID (Edition)
          <select
            value={editRecipientDestinationId}
            onChange={(event) => setEditRecipientDestinationId(event.target.value)}
          >
            {destinations.map((destination) => (
              <option key={destination.id} value={destination.id}>
                {destination.id} - {destination.label}
              </option>
            ))}
          </select>
        </label>
        <label className="field-inline">
          Structure (Edition)
          <input
            value={editRecipientStructureName}
            onChange={(event) => setEditRecipientStructureName(event.target.value)}
          />
        </label>
        <label className="field-inline">
          Adresse 1 (Edition)
          <input
            value={editRecipientAddressLine1}
            onChange={(event) => setEditRecipientAddressLine1(event.target.value)}
          />
        </label>
        <label className="field-inline">
          CP (Edition)
          <input
            value={editRecipientPostalCode}
            onChange={(event) => setEditRecipientPostalCode(event.target.value)}
          />
        </label>
        <label className="field-inline">
          Ville (Edition)
          <input
            value={editRecipientCity}
            onChange={(event) => setEditRecipientCity(event.target.value)}
          />
        </label>
        <button
          type="submit"
          className="btn-secondary"
          data-track="portal.recipient.edit"
          disabled={isSubmitting}
        >
          Modifier destinataire
        </button>
      </form>

      <form className="inline-form" onSubmit={onAccountSubmit}>
        <label className="field-inline">
          Association name (Compte)
          <input
            value={accountAssociationName}
            onChange={(event) => setAccountAssociationName(event.target.value)}
          />
        </label>
        <label className="field-inline">
          Email association (Compte)
          <input
            value={accountAssociationEmail}
            onChange={(event) => setAccountAssociationEmail(event.target.value)}
          />
        </label>
        <label className="field-inline">
          Telephone association (Compte)
          <input
            value={accountAssociationPhone}
            onChange={(event) => setAccountAssociationPhone(event.target.value)}
          />
        </label>
        <label className="field-inline">
          Adresse 1 (Compte)
          <input
            value={accountAddressLine1}
            onChange={(event) => setAccountAddressLine1(event.target.value)}
          />
        </label>
        <label className="field-inline">
          CP (Compte)
          <input
            value={accountPostalCode}
            onChange={(event) => setAccountPostalCode(event.target.value)}
          />
        </label>
        <label className="field-inline">
          Ville (Compte)
          <input value={accountCity} onChange={(event) => setAccountCity(event.target.value)} />
        </label>
        <label className="field-inline">
          Email contact (Compte)
          <input
            value={accountContactEmail}
            onChange={(event) => setAccountContactEmail(event.target.value)}
          />
        </label>
        <button
          type="submit"
          className="btn-primary"
          data-track="portal.account.save"
          disabled={isSubmitting}
        >
          Sauver compte
        </button>
      </form>

      {mutationStatus ? <div className="api-state api-ok">{mutationStatus}</div> : null}
      {mutationError ? (
        <div className="api-state api-error">
          Mutation portal indisponible: <span>{mutationError}</span>
        </div>
      ) : null}
    </div>
  );
}
