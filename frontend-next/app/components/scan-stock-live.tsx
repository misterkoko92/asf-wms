"use client";

import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";

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

function buildStockQuery(params: {
  q: string;
  category: string;
  warehouse: string;
  sort: string;
}): string {
  const query = new URLSearchParams();
  const q = params.q.trim();
  const category = params.category.trim();
  const warehouse = params.warehouse.trim();
  const sort = params.sort.trim();
  if (q) {
    query.set("q", q);
  }
  if (category) {
    query.set("category", category);
  }
  if (warehouse) {
    query.set("warehouse", warehouse);
  }
  if (sort) {
    query.set("sort", sort);
  }
  return query.toString();
}

function formatLastMovement(value: string | null): string {
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

const DEFAULT_UPDATE_EXPIRY = "2026-12-31";
const DEFAULT_SORT = "name";

export function ScanStockLive() {
  const [data, setData] = useState<ScanStockDto | null>(null);
  const [error, setError] = useState<string>("");
  const [mutationError, setMutationError] = useState<string>("");
  const [mutationStatus, setMutationStatus] = useState<string>("");
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const filtersHydratedRef = useRef<boolean>(false);

  const [filterQ, setFilterQ] = useState<string>("");
  const [filterCategory, setFilterCategory] = useState<string>("");
  const [filterWarehouse, setFilterWarehouse] = useState<string>("");
  const [filterSort, setFilterSort] = useState<string>(DEFAULT_SORT);

  const [updateProductCode, setUpdateProductCode] = useState<string>("");
  const [updateQuantity, setUpdateQuantity] = useState<string>("1");
  const [updateExpiresOn, setUpdateExpiresOn] = useState<string>(DEFAULT_UPDATE_EXPIRY);
  const [updateLotCode, setUpdateLotCode] = useState<string>("");

  const [outProductCode, setOutProductCode] = useState<string>("");
  const [outQuantity, setOutQuantity] = useState<string>("1");
  const [outReasonCode, setOutReasonCode] = useState<string>("next_ui_flow");
  const [outReasonNotes, setOutReasonNotes] = useState<string>("Workflow navigateur Next");

  const loadStock = useCallback(
    async (query = "") => {
      setError("");
      setIsLoading(true);
      try {
        const payload = await getScanStock(query);
        setData(payload);
        if (!filtersHydratedRef.current) {
          setFilterQ(payload.filters.q || "");
          setFilterCategory(payload.filters.category || "");
          setFilterWarehouse(payload.filters.warehouse || "");
          setFilterSort(payload.filters.sort || DEFAULT_SORT);
          filtersHydratedRef.current = true;
        }
      } catch (err: unknown) {
        setData(null);
        setError(toErrorMessage(err));
      } finally {
        setIsLoading(false);
      }
    },
    [],
  );

  useEffect(() => {
    loadStock().catch(() => undefined);
  }, [loadStock]);

  const reloadCurrentFilters = useCallback(async () => {
    const query = buildStockQuery({
      q: filterQ,
      category: filterCategory,
      warehouse: filterWarehouse,
      sort: filterSort,
    });
    await loadStock(query);
  }, [filterCategory, filterQ, filterSort, filterWarehouse, loadStock]);

  const onFilterSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    await reloadCurrentFilters();
  };

  const onFilterReset = async () => {
    setFilterQ("");
    setFilterCategory("");
    setFilterWarehouse("");
    setFilterSort(DEFAULT_SORT);
    await loadStock("");
  };

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
      await reloadCurrentFilters();
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
      await reloadCurrentFilters();
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
    <div className="stack-grid">
      <div className="api-state api-ok">
        API stock connectee. {data.meta.total_products} produits, seuil bas{" "}
        {data.meta.low_stock_threshold}.
      </div>

      <form className="inline-form" onSubmit={onFilterSubmit}>
        <label className="field-inline">
          Recherche
          <input value={filterQ} onChange={(event) => setFilterQ(event.target.value)} />
        </label>
        <label className="field-inline">
          Categorie
          <select
            value={filterCategory}
            onChange={(event) => setFilterCategory(event.target.value)}
          >
            <option value="">Toutes categories</option>
            {data.categories.map((category) => (
              <option key={category.id} value={category.id}>
                {category.name}
              </option>
            ))}
          </select>
        </label>
        <label className="field-inline">
          Entrepot
          <select
            value={filterWarehouse}
            onChange={(event) => setFilterWarehouse(event.target.value)}
          >
            <option value="">Tous entrepots</option>
            {data.warehouses.map((warehouse) => (
              <option key={warehouse.id} value={warehouse.id}>
                {warehouse.name}
              </option>
            ))}
          </select>
        </label>
        <label className="field-inline">
          Tri
          <select value={filterSort} onChange={(event) => setFilterSort(event.target.value)}>
            <option value="category">Categorie</option>
            <option value="name">Nom</option>
            <option value="sku">Reference</option>
            <option value="qty_asc">Stock croissant</option>
            <option value="qty_desc">Stock decroissant</option>
          </select>
        </label>
        <button type="submit" className="btn-secondary" disabled={isSubmitting || isLoading}>
          Filtrer
        </button>
        <button
          type="button"
          className="btn-secondary"
          onClick={() => onFilterReset().catch(() => undefined)}
          disabled={isSubmitting || isLoading}
        >
          Reinitialiser
        </button>
      </form>

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

      <article className="panel">
        <h2>Produits en stock ({data.products.length})</h2>
        <table className="data-table">
          <thead>
            <tr>
              <th>Reference</th>
              <th>Produit</th>
              <th>Categorie</th>
              <th>Stock</th>
              <th>Derniere modification</th>
            </tr>
          </thead>
          <tbody>
            {data.products.map((row) => (
              <tr key={row.id}>
                <td>{row.sku}</td>
                <td>{row.name}</td>
                <td>{row.category_name || "-"}</td>
                <td>{row.stock_total}</td>
                <td>{formatLastMovement(row.last_movement_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </article>
    </div>
  );
}
