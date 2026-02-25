"use client";

import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";

import { ApiClientError } from "../lib/api/client";
import {
  getShipmentsTracking,
  postShipmentClose,
  postShipmentTrackingEvent,
} from "../lib/api/ui";
import type { ScanShipmentsTrackingDto } from "../lib/api/types";

const TRACKING_STATUS_OPTIONS = [
  { value: "planning_ok", label: "OK pour planification" },
  { value: "planned", label: "Planifie" },
  { value: "moved_export", label: "Deplace au magasin export" },
  { value: "boarding_ok", label: "OK mise a bord" },
  { value: "received_correspondent", label: "Recu correspondant" },
  { value: "received_recipient", label: "Recu destinataire" },
];
const CLOSED_FILTER_EXCLUDE = "exclude";
const CLOSED_FILTER_ALL = "all";

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

function buildTrackingQuery(params: { plannedWeek: string; closed: string }): string {
  const query = new URLSearchParams();
  const plannedWeek = params.plannedWeek.trim();
  if (plannedWeek) {
    query.set("planned_week", plannedWeek);
  }
  if (params.closed === CLOSED_FILTER_ALL) {
    query.set("closed", CLOSED_FILTER_ALL);
  }
  return query.toString();
}

function formatDate(value: string | null): string {
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

export function ScanShipmentTrackingLive() {
  const [data, setData] = useState<ScanShipmentsTrackingDto | null>(null);
  const [error, setError] = useState<string>("");
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const filtersHydratedRef = useRef<boolean>(false);

  const [filterPlannedWeek, setFilterPlannedWeek] = useState<string>("");
  const [filterClosed, setFilterClosed] = useState<string>(CLOSED_FILTER_EXCLUDE);

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

  const loadTracking = useCallback(async (query = "") => {
    setError("");
    setIsLoading(true);
    try {
      const payload = await getShipmentsTracking(query);
      setData(payload);
      if (!filtersHydratedRef.current) {
        setFilterPlannedWeek(payload.filters.planned_week || "");
        setFilterClosed(payload.filters.closed || CLOSED_FILTER_EXCLUDE);
        filtersHydratedRef.current = true;
      }
    } catch (err: unknown) {
      setData(null);
      setError(toErrorMessage(err));
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadTracking().catch(() => undefined);
  }, [loadTracking]);

  const reloadCurrentFilters = useCallback(async () => {
    const query = buildTrackingQuery({
      plannedWeek: filterPlannedWeek,
      closed: filterClosed,
    });
    await loadTracking(query);
  }, [filterClosed, filterPlannedWeek, loadTracking]);

  const onFilterSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    await reloadCurrentFilters();
  };

  const onFilterReset = async () => {
    setFilterPlannedWeek("");
    setFilterClosed(CLOSED_FILTER_EXCLUDE);
    await loadTracking("");
  };

  const onTrackingSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const shipmentId = parseId(trackingShipmentId);
    if (!shipmentId) {
      setMutationError("Expedition (Suivi) invalide.");
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
      await reloadCurrentFilters();
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
      await reloadCurrentFilters();
    } catch (err: unknown) {
      setMutationError(toErrorMessage(err));
    } finally {
      setIsSubmitting(false);
    }
  };

  const onCloseShipmentFromRow = async (shipmentId: number) => {
    setIsSubmitting(true);
    setMutationError("");
    setMutationStatus("");
    try {
      const response = await postShipmentClose(shipmentId);
      setCloseShipmentId(String(shipmentId));
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
        API suivi expeditions indisponible: <span>{error}</span>
      </div>
    );
  }

  if (!data) {
    return <div className="api-state">Chargement API suivi expeditions...</div>;
  }

  return (
    <div className="stack-grid">
      <div className="api-state api-ok">
        API suivi connectee. {data.meta.total_shipments} expedition(s) filtree(s).
      </div>

      {data.warnings.map((warning) => (
        <div key={warning} className="api-state api-error">
          {warning}
        </div>
      ))}

      <form className="inline-form" onSubmit={onFilterSubmit}>
        <label className="field-inline">
          Semaine planifiee
          <input
            type="week"
            value={filterPlannedWeek}
            onChange={(event) => setFilterPlannedWeek(event.target.value)}
          />
        </label>
        <label className="field-inline">
          Dossiers clos
          <select
            value={filterClosed}
            onChange={(event) => setFilterClosed(event.target.value)}
          >
            <option value={CLOSED_FILTER_EXCLUDE}>Exclure clos</option>
            <option value={CLOSED_FILTER_ALL}>Inclure clos</option>
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

      <form className="inline-form" onSubmit={onTrackingSubmit}>
        <label className="field-inline">
          Expedition (Suivi)
          <input
            aria-label="Expedition (Suivi)"
            value={trackingShipmentId}
            onChange={(event) => setTrackingShipmentId(event.target.value)}
            inputMode="numeric"
          />
        </label>
        <label className="field-inline">
          Statut suivi
          <select
            aria-label="Statut suivi"
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
          Envoyer suivi
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

      <article className="panel">
        <h2>Suivi expeditions ({data.shipments.length})</h2>
        {data.shipments.length ? (
          <table className="data-table">
            <thead>
              <tr>
                <th>No expedition</th>
                <th>Nb colis</th>
                <th>Expediteur</th>
                <th>Destinataire</th>
                <th>Planifie</th>
                <th>OK mise a bord</th>
                <th>Expedie</th>
                <th>Recu escale</th>
                <th>Livre</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {data.shipments.map((shipment) => (
                <tr key={shipment.id}>
                  <td>{shipment.reference}</td>
                  <td>{shipment.carton_count}</td>
                  <td>{shipment.shipper_name}</td>
                  <td>{shipment.recipient_name}</td>
                  <td>{formatDate(shipment.planned_at)}</td>
                  <td>{formatDate(shipment.boarding_ok_at)}</td>
                  <td>{formatDate(shipment.shipped_at)}</td>
                  <td>{formatDate(shipment.received_correspondent_at)}</td>
                  <td>{formatDate(shipment.delivered_at)}</td>
                  <td>
                    <div className="inline-actions">
                      <a className="btn-secondary" href={shipment.actions.tracking_url}>
                        Suivi/MAJ
                      </a>
                      {shipment.is_closed ? (
                        <button
                          type="button"
                          className="btn-secondary btn-success-soft"
                          disabled
                        >
                          Dossier cloture
                        </button>
                      ) : shipment.can_close ? (
                        <button
                          type="button"
                          className="btn-secondary btn-success-soft"
                          onClick={() => onCloseShipmentFromRow(shipment.id).catch(() => undefined)}
                          disabled={isSubmitting}
                        >
                          Clore le dossier
                        </button>
                      ) : (
                        <button
                          type="button"
                          className="btn-secondary btn-danger-soft"
                          onClick={() => window.alert(data.close_inactive_message)}
                        >
                          Clore le dossier
                        </button>
                      )}
                    </div>
                    {shipment.closed_at ? (
                      <p className="panel-note">
                        Cloture le {formatDate(shipment.closed_at)}
                        {shipment.closed_by_username
                          ? ` par ${shipment.closed_by_username}`
                          : ""}
                      </p>
                    ) : shipment.is_disputed ? (
                      <p className="panel-note">Litige en cours</p>
                    ) : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="panel-note">Aucune expedition correspondante.</p>
        )}
      </article>
    </div>
  );
}
