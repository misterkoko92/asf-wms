"use client";

import { useCallback, useEffect, useState, type FormEvent } from "react";

import { ApiClientError } from "../lib/api/client";
import { getScanStock, postStockOut, postStockUpdate } from "../lib/api/ui";
import type { ScanStockDto, UiStockOutInput, UiStockUpdateInput } from "../lib/api/types";

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

const DEFAULT_UPDATE_EXPIRY = "2026-12-31";

export function ScanStockLive() {
  const [data, setData] = useState<ScanStockDto | null>(null);
  const [error, setError] = useState<string>("");
  const [mutationError, setMutationError] = useState<string>("");
  const [mutationStatus, setMutationStatus] = useState<string>("");
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);

  const [updateProductCode, setUpdateProductCode] = useState<string>("");
  const [updateQuantity, setUpdateQuantity] = useState<string>("1");
  const [updateExpiresOn, setUpdateExpiresOn] = useState<string>(DEFAULT_UPDATE_EXPIRY);
  const [updateLotCode, setUpdateLotCode] = useState<string>("");

  const [outProductCode, setOutProductCode] = useState<string>("");
  const [outQuantity, setOutQuantity] = useState<string>("1");
  const [outReasonCode, setOutReasonCode] = useState<string>("next_ui_flow");
  const [outReasonNotes, setOutReasonNotes] = useState<string>("Workflow navigateur Next");

  const loadStock = useCallback(async () => {
    setError("");
    try {
      const payload = await getScanStock();
      setData(payload);
    } catch (err: unknown) {
      setData(null);
      setError(toErrorMessage(err));
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    loadStock().catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [loadStock]);

  const onStockUpdateSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const quantity = parsePositiveInteger(updateQuantity);
    if (!quantity) {
      setMutationError("Quantite (MAJ) invalide.");
      return;
    }
    const productCode = updateProductCode.trim();
    if (!productCode) {
      setMutationError("Product code (MAJ) requis.");
      return;
    }
    const payload: UiStockUpdateInput = {
      product_code: productCode,
      quantity,
      expires_on: updateExpiresOn,
      lot_code: updateLotCode.trim(),
    };
    setIsSubmitting(true);
    setMutationError("");
    setMutationStatus("");
    try {
      const response = await postStockUpdate(payload);
      setMutationStatus(response.message);
      await loadStock();
    } catch (err: unknown) {
      setMutationError(toErrorMessage(err));
    } finally {
      setIsSubmitting(false);
    }
  };

  const onStockOutSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const quantity = parsePositiveInteger(outQuantity);
    if (!quantity) {
      setMutationError("Quantite (Sortie) invalide.");
      return;
    }
    const productCode = outProductCode.trim();
    if (!productCode) {
      setMutationError("Product code (Sortie) requis.");
      return;
    }
    const payload: UiStockOutInput = {
      product_code: productCode,
      quantity,
      reason_code: outReasonCode.trim(),
      reason_notes: outReasonNotes.trim(),
    };
    setIsSubmitting(true);
    setMutationError("");
    setMutationStatus("");
    try {
      const response = await postStockOut(payload);
      setMutationStatus(response.message);
      await loadStock();
    } catch (err: unknown) {
      setMutationError(toErrorMessage(err));
    } finally {
      setIsSubmitting(false);
    }
  };

  if (error) {
    return (
      <div className="api-state api-error">
        API stock indisponible: <span>{error}</span>
      </div>
    );
  }

  if (!data) {
    return <div className="api-state">Chargement API stock...</div>;
  }

  return (
    <>
      <div className="api-state api-ok">
        API stock connectee. {data.meta.total_products} produits, seuil bas{" "}
        {data.meta.low_stock_threshold}.
      </div>

      <form className="inline-form" onSubmit={onStockUpdateSubmit}>
        <label className="field-inline">
          Product code (MAJ)
          <input
            value={updateProductCode}
            onChange={(event) => setUpdateProductCode(event.target.value)}
          />
        </label>
        <label className="field-inline">
          Quantite (MAJ)
          <input
            value={updateQuantity}
            onChange={(event) => setUpdateQuantity(event.target.value)}
            inputMode="numeric"
          />
        </label>
        <label className="field-inline">
          Expire le (MAJ)
          <input
            type="date"
            value={updateExpiresOn}
            onChange={(event) => setUpdateExpiresOn(event.target.value)}
          />
        </label>
        <label className="field-inline">
          Lot (MAJ)
          <input value={updateLotCode} onChange={(event) => setUpdateLotCode(event.target.value)} />
        </label>
        <button
          type="submit"
          className="btn-secondary"
          data-track="stock.update.submit"
          disabled={isSubmitting}
        >
          Valider MAJ
        </button>
      </form>

      <form className="inline-form" onSubmit={onStockOutSubmit}>
        <label className="field-inline">
          Product code (Sortie)
          <input
            value={outProductCode}
            onChange={(event) => setOutProductCode(event.target.value)}
          />
        </label>
        <label className="field-inline">
          Quantite (Sortie)
          <input
            value={outQuantity}
            onChange={(event) => setOutQuantity(event.target.value)}
            inputMode="numeric"
          />
        </label>
        <label className="field-inline">
          Raison (Sortie)
          <input value={outReasonCode} onChange={(event) => setOutReasonCode(event.target.value)} />
        </label>
        <label className="field-inline">
          Notes (Sortie)
          <input value={outReasonNotes} onChange={(event) => setOutReasonNotes(event.target.value)} />
        </label>
        <button
          type="submit"
          className="btn-secondary"
          data-track="stock.out.submit"
          disabled={isSubmitting}
        >
          Valider sortie
        </button>
      </form>

      {mutationStatus ? <div className="api-state api-ok">{mutationStatus}</div> : null}
      {mutationError ? (
        <div className="api-state api-error">
          Mutation stock indisponible: <span>{mutationError}</span>
        </div>
      ) : null}

      <table className="data-table">
        <thead>
          <tr>
            <th>Produit</th>
            <th>Marque</th>
            <th>Emplacement</th>
            <th>Qty</th>
            <th>Etat</th>
            <th>Action</th>
          </tr>
        </thead>
        <tbody>
          {data.products.slice(0, 12).map((row) => (
            <tr key={row.id}>
              <td>{row.name}</td>
              <td>{row.brand}</td>
              <td>{row.location}</td>
              <td>{row.stock_total}</td>
              <td>
                <span className={`state-pill state-${row.state.toLowerCase()}`}>
                  {row.state.toUpperCase()}
                </span>
              </td>
              <td>
                <button type="button" className="table-action" data-track="stock.update.inline">
                  MAJ
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}
