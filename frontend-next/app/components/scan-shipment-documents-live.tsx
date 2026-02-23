"use client";

import { useCallback, useState, type FormEvent } from "react";

import { ApiClientError } from "../lib/api/client";
import {
  deleteShipmentDocument,
  getShipmentDocuments,
  postShipmentDocument,
} from "../lib/api/ui";
import type { UiShipmentDocumentsDto } from "../lib/api/types";

function toErrorMessage(error: unknown): string {
  if (error instanceof ApiClientError) {
    return `${error.message} (${error.code})`;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return String(error);
}

function parseShipmentId(rawValue: string): number | null {
  const value = Number(rawValue.trim());
  if (!Number.isInteger(value) || value <= 0) {
    return null;
  }
  return value;
}

export function ScanShipmentDocumentsLive() {
  const [shipmentIdInput, setShipmentIdInput] = useState<string>("1");
  const [shipmentId, setShipmentId] = useState<number | null>(null);
  const [data, setData] = useState<UiShipmentDocumentsDto | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [error, setError] = useState<string>("");
  const [statusMessage, setStatusMessage] = useState<string>("");
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);

  const loadDocuments = useCallback(async (id: number) => {
    setIsLoading(true);
    setError("");
    setStatusMessage("");
    try {
      const payload = await getShipmentDocuments(id);
      setData(payload);
      setShipmentId(id);
      setStatusMessage("Documents charges.");
    } catch (err: unknown) {
      setData(null);
      setShipmentId(null);
      setError(toErrorMessage(err));
    } finally {
      setIsLoading(false);
    }
  }, []);

  const onLoadSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const parsedId = parseShipmentId(shipmentIdInput);
    if (!parsedId) {
      setError("Identifiant expedition invalide.");
      return;
    }
    await loadDocuments(parsedId);
  };

  const onUploadClick = async () => {
    if (!shipmentId || !selectedFile) {
      setError("Selectionnez une expedition et un fichier.");
      return;
    }
    setIsSubmitting(true);
    setError("");
    setStatusMessage("");
    try {
      await postShipmentDocument(shipmentId, selectedFile);
      setSelectedFile(null);
      await loadDocuments(shipmentId);
      setStatusMessage("Document televerse.");
    } catch (err: unknown) {
      setError(toErrorMessage(err));
    } finally {
      setIsSubmitting(false);
    }
  };

  const onDeleteClick = async (documentId: number) => {
    if (!shipmentId) {
      return;
    }
    setIsSubmitting(true);
    setError("");
    setStatusMessage("");
    try {
      await deleteShipmentDocument(shipmentId, documentId);
      await loadDocuments(shipmentId);
      setStatusMessage("Document supprime.");
    } catch (err: unknown) {
      setError(toErrorMessage(err));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="stack-grid">
      <form className="inline-form" onSubmit={onLoadSubmit}>
        <label className="field-inline">
          Shipment ID
          <input
            value={shipmentIdInput}
            onChange={(event) => setShipmentIdInput(event.target.value)}
            inputMode="numeric"
          />
        </label>
        <button type="submit" className="btn-secondary" data-track="shipment.docs.load">
          Charger
        </button>
        <label className="field-inline">
          Document
          <input
            type="file"
            onChange={(event) => {
              const file = event.target.files?.[0] || null;
              setSelectedFile(file);
            }}
          />
        </label>
        <button
          type="button"
          className="btn-primary"
          data-track="shipment.docs.upload"
          onClick={onUploadClick}
          disabled={isSubmitting || !shipmentId || !selectedFile}
        >
          Upload
        </button>
      </form>

      {error ? (
        <div className="api-state api-error">
          API docs indisponible: <span>{error}</span>
        </div>
      ) : null}

      {!error && statusMessage ? <div className="api-state api-ok">{statusMessage}</div> : null}

      {isLoading ? <div className="api-state">Chargement docs expedition...</div> : null}

      {data ? (
        <>
          <article className="panel">
            <h2>Documents systeme</h2>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Label</th>
                  <th>Lien</th>
                </tr>
              </thead>
              <tbody>
                {data.documents.map((item) => (
                  <tr key={item.label + item.url}>
                    <td>{item.label}</td>
                    <td>
                      <a href={item.url} target="_blank" rel="noreferrer">
                        Ouvrir
                      </a>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </article>

          <article className="panel">
            <h2>Documents additionnels</h2>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Fichier</th>
                  <th>Type</th>
                  <th>Date</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {data.additional_documents.length ? (
                  data.additional_documents.map((document) => (
                    <tr key={document.id}>
                      <td>
                        <a href={document.url} target="_blank" rel="noreferrer">
                          {document.filename || `document-${document.id}`}
                        </a>
                      </td>
                      <td>{document.doc_type_label}</td>
                      <td>{document.generated_at || "-"}</td>
                      <td>
                        <button
                          type="button"
                          className="table-action"
                          data-track="shipment.docs.delete"
                          onClick={() => onDeleteClick(document.id)}
                          disabled={isSubmitting}
                        >
                          Supprimer
                        </button>
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={4}>Aucun document additionnel.</td>
                  </tr>
                )}
              </tbody>
            </table>
          </article>

          <article className="panel">
            <h2>Labels expedition</h2>
            <div className="inline-actions">
              <a
                className="btn-secondary"
                href={data.labels.all_url}
                target="_blank"
                rel="noreferrer"
                data-track="shipment.labels.all"
              >
                Ouvrir tous les labels
              </a>
            </div>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Carton</th>
                  <th>Label</th>
                </tr>
              </thead>
              <tbody>
                {data.labels.items.length ? (
                  data.labels.items.map((item) => (
                    <tr key={item.carton_id}>
                      <td>{item.carton_code}</td>
                      <td>
                        <a href={item.url} target="_blank" rel="noreferrer">
                          Ouvrir
                        </a>
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={2}>Aucun label disponible.</td>
                  </tr>
                )}
              </tbody>
            </table>
          </article>
        </>
      ) : null}
    </div>
  );
}
