"use client";

import { useEffect, useMemo, useState } from "react";

import { ApiClientError } from "../lib/api/client";
import { getPrintTemplate, getPrintTemplates, patchPrintTemplate } from "../lib/api/ui";
import type { UiPrintTemplateDto, UiPrintTemplateListDto } from "../lib/api/types";

function toErrorMessage(error: unknown): string {
  if (error instanceof ApiClientError) {
    return `${error.message} (${error.code})`;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return String(error);
}

function prettyLayout(layout: Record<string, unknown>): string {
  return JSON.stringify(layout, null, 2);
}

export function ScanPrintTemplatesLive() {
  const [list, setList] = useState<UiPrintTemplateListDto | null>(null);
  const [selectedDocType, setSelectedDocType] = useState<string>("");
  const [detail, setDetail] = useState<UiPrintTemplateDto | null>(null);
  const [layoutDraft, setLayoutDraft] = useState<string>("");
  const [statusMessage, setStatusMessage] = useState<string>("");
  const [error, setError] = useState<string>("");
  const [isLoadingList, setIsLoadingList] = useState<boolean>(true);
  const [isLoadingDetail, setIsLoadingDetail] = useState<boolean>(false);
  const [isSaving, setIsSaving] = useState<boolean>(false);

  useEffect(() => {
    let cancelled = false;
    setIsLoadingList(true);
    getPrintTemplates()
      .then((payload) => {
        if (cancelled) {
          return;
        }
        setList(payload);
        if (payload.templates.length && !selectedDocType) {
          setSelectedDocType(payload.templates[0].doc_type);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(toErrorMessage(err));
        }
      })
      .finally(() => {
        if (!cancelled) {
          setIsLoadingList(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!selectedDocType) {
      return;
    }
    let cancelled = false;
    setIsLoadingDetail(true);
    setError("");
    getPrintTemplate(selectedDocType)
      .then((payload) => {
        if (cancelled) {
          return;
        }
        setDetail(payload);
        setLayoutDraft(prettyLayout(payload.layout));
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(toErrorMessage(err));
        }
      })
      .finally(() => {
        if (!cancelled) {
          setIsLoadingDetail(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [selectedDocType]);

  const canSave = useMemo(
    () => Boolean(selectedDocType && !isSaving && !isLoadingDetail),
    [selectedDocType, isSaving, isLoadingDetail],
  );

  const onSave = async () => {
    if (!selectedDocType) {
      return;
    }
    setError("");
    setStatusMessage("");
    setIsSaving(true);
    try {
      const parsedLayout = JSON.parse(layoutDraft) as Record<string, unknown>;
      const payload = await patchPrintTemplate(selectedDocType, {
        action: "save",
        layout: parsedLayout,
      });
      setDetail(payload.template);
      setLayoutDraft(prettyLayout(payload.template.layout));
      setStatusMessage(payload.message);
    } catch (err: unknown) {
      setError(toErrorMessage(err));
    } finally {
      setIsSaving(false);
    }
  };

  const onReset = async () => {
    if (!selectedDocType) {
      return;
    }
    setError("");
    setStatusMessage("");
    setIsSaving(true);
    try {
      const payload = await patchPrintTemplate(selectedDocType, {
        action: "reset",
        layout: {},
      });
      setDetail(payload.template);
      setLayoutDraft(prettyLayout(payload.template.layout));
      setStatusMessage(payload.message);
    } catch (err: unknown) {
      setError(toErrorMessage(err));
    } finally {
      setIsSaving(false);
    }
  };

  if (error) {
    return (
      <div className="api-state api-error">
        API templates indisponible: <span>{error}</span>
      </div>
    );
  }

  if (isLoadingList) {
    return <div className="api-state">Chargement templates...</div>;
  }

  return (
    <div className="stack-grid">
      <div className="inline-form">
        <label className="field-inline">
          Template
          <select
            value={selectedDocType}
            onChange={(event) => setSelectedDocType(event.target.value)}
          >
            {(list?.templates || []).map((item) => (
              <option key={item.doc_type} value={item.doc_type}>
                {item.label}
              </option>
            ))}
          </select>
        </label>
        <button
          type="button"
          className="btn-secondary"
          data-track="template.save"
          onClick={onSave}
          disabled={!canSave}
        >
          Sauver
        </button>
        <button
          type="button"
          className="btn-secondary"
          data-track="template.reset"
          onClick={onReset}
          disabled={!canSave}
        >
          Reset
        </button>
      </div>

      {statusMessage ? <div className="api-state api-ok">{statusMessage}</div> : null}
      {isLoadingDetail ? <div className="api-state">Chargement detail template...</div> : null}

      {detail ? (
        <div className="dashboard-grid">
          <article className="panel">
            <h2>Layout JSON</h2>
            <textarea
              className="json-editor"
              value={layoutDraft}
              onChange={(event) => setLayoutDraft(event.target.value)}
            />
          </article>
          <article className="panel">
            <h2>Meta template</h2>
            <table className="data-table">
              <tbody>
                <tr>
                  <td>Type</td>
                  <td>{detail.doc_type}</td>
                </tr>
                <tr>
                  <td>Override</td>
                  <td>{detail.has_override ? "Oui" : "Non"}</td>
                </tr>
                <tr>
                  <td>Maj</td>
                  <td>{detail.updated_at || "-"}</td>
                </tr>
                <tr>
                  <td>Par</td>
                  <td>{detail.updated_by || "-"}</td>
                </tr>
              </tbody>
            </table>
            <h2>Versions</h2>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Version</th>
                  <th>Date</th>
                  <th>Auteur</th>
                </tr>
              </thead>
              <tbody>
                {detail.versions.length ? (
                  detail.versions.map((version) => (
                    <tr key={version.id}>
                      <td>{version.version}</td>
                      <td>{version.created_at}</td>
                      <td>{version.created_by || "-"}</td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={3}>Aucune version enregistree.</td>
                  </tr>
                )}
              </tbody>
            </table>
          </article>
        </div>
      ) : null}
    </div>
  );
}
