import { apiDeleteJson, apiGetJson, apiPatchJson, apiPostFormData, apiPostJson } from "./client";
import type {
  PortalDashboardDto,
  ScanCartonsDto,
  ScanDashboardDto,
  ScanShipmentsReadyDto,
  ScanShipmentsTrackingDto,
  ScanStockDto,
  ShipmentFormOptionsDto,
  UiPrintTemplateDto,
  UiPrintTemplateListDto,
  UiPrintTemplateMutationDto,
  UiPrintTemplateMutationInput,
  UiShipmentCloseDto,
  UiShipmentDocumentDeleteDto,
  UiShipmentDocumentsDto,
  UiShipmentDocumentUploadDto,
  UiShipmentLabelDto,
  UiShipmentLabelsDto,
  UiShipmentMutationDto,
  UiShipmentMutationInput,
  UiShipmentTrackingEventDto,
  UiShipmentTrackingEventInput,
  UiPortalAccountDto,
  UiPortalAccountMutationDto,
  UiPortalAccountUpdateInput,
  UiPortalOrderCreateDto,
  UiPortalOrderCreateInput,
  UiPortalRecipientInput,
  UiPortalRecipientMutationDto,
  UiPortalRecipientsDto,
  UiShipmentsReadyArchiveDto,
  UiStockOutDto,
  UiStockOutInput,
  UiStockUpdateDto,
  UiStockUpdateInput,
} from "./types";

export function getScanDashboard(query = "") {
  const suffix = query ? `?${query}` : "";
  return apiGetJson<ScanDashboardDto>(`/api/v1/ui/dashboard/${suffix}`);
}

export function getScanCartons() {
  return apiGetJson<ScanCartonsDto>("/api/v1/ui/cartons/");
}

export function getScanStock(query = "") {
  const suffix = query ? `?${query}` : "";
  return apiGetJson<ScanStockDto>(`/api/v1/ui/stock/${suffix}`);
}

export function getShipmentFormOptions() {
  return apiGetJson<ShipmentFormOptionsDto>("/api/v1/ui/shipments/form-options/");
}

export function getShipmentsReady() {
  return apiGetJson<ScanShipmentsReadyDto>("/api/v1/ui/shipments/ready/");
}

export function postShipmentsReadyArchiveStaleDrafts() {
  return apiPostJson<UiShipmentsReadyArchiveDto>(
    "/api/v1/ui/shipments/ready/archive-stale-drafts/",
    {},
  );
}

export function getShipmentsTracking(query = "") {
  const suffix = query ? `?${query}` : "";
  return apiGetJson<ScanShipmentsTrackingDto>(`/api/v1/ui/shipments/tracking/${suffix}`);
}

export function getPortalDashboard() {
  return apiGetJson<PortalDashboardDto>("/api/v1/ui/portal/dashboard/");
}

export function postStockUpdate(payload: UiStockUpdateInput) {
  return apiPostJson<UiStockUpdateDto>("/api/v1/ui/stock/update/", payload);
}

export function postStockOut(payload: UiStockOutInput) {
  return apiPostJson<UiStockOutDto>("/api/v1/ui/stock/out/", payload);
}

export function postShipmentCreate(payload: UiShipmentMutationInput) {
  return apiPostJson<UiShipmentMutationDto>("/api/v1/ui/shipments/", payload);
}

export function patchShipmentUpdate(shipmentId: number, payload: UiShipmentMutationInput) {
  return apiPatchJson<UiShipmentMutationDto>(`/api/v1/ui/shipments/${shipmentId}/`, payload);
}

export function postShipmentTrackingEvent(
  shipmentId: number,
  payload: UiShipmentTrackingEventInput,
) {
  return apiPostJson<UiShipmentTrackingEventDto>(
    `/api/v1/ui/shipments/${shipmentId}/tracking-events/`,
    payload,
  );
}

export function postShipmentClose(shipmentId: number) {
  return apiPostJson<UiShipmentCloseDto>(`/api/v1/ui/shipments/${shipmentId}/close/`, {});
}

export function getShipmentDocuments(shipmentId: number) {
  return apiGetJson<UiShipmentDocumentsDto>(`/api/v1/ui/shipments/${shipmentId}/documents/`);
}

export function postShipmentDocument(shipmentId: number, file: File) {
  const payload = new FormData();
  payload.append("document_file", file);
  return apiPostFormData<UiShipmentDocumentUploadDto>(
    `/api/v1/ui/shipments/${shipmentId}/documents/`,
    payload,
  );
}

export function deleteShipmentDocument(shipmentId: number, documentId: number) {
  return apiDeleteJson<UiShipmentDocumentDeleteDto>(
    `/api/v1/ui/shipments/${shipmentId}/documents/${documentId}/`,
  );
}

export function getShipmentLabels(shipmentId: number) {
  return apiGetJson<UiShipmentLabelsDto>(`/api/v1/ui/shipments/${shipmentId}/labels/`);
}

export function getShipmentLabel(shipmentId: number, cartonId: number) {
  return apiGetJson<UiShipmentLabelDto>(
    `/api/v1/ui/shipments/${shipmentId}/labels/${cartonId}/`,
  );
}

export function getPrintTemplates() {
  return apiGetJson<UiPrintTemplateListDto>("/api/v1/ui/templates/");
}

export function getPrintTemplate(docType: string) {
  return apiGetJson<UiPrintTemplateDto>(`/api/v1/ui/templates/${docType}/`);
}

export function patchPrintTemplate(docType: string, payload: UiPrintTemplateMutationInput) {
  return apiPatchJson<UiPrintTemplateMutationDto>(`/api/v1/ui/templates/${docType}/`, payload);
}

export function postPortalOrder(payload: UiPortalOrderCreateInput) {
  return apiPostJson<UiPortalOrderCreateDto>("/api/v1/ui/portal/orders/", payload);
}

export function getPortalRecipients() {
  return apiGetJson<UiPortalRecipientsDto>("/api/v1/ui/portal/recipients/");
}

export function postPortalRecipient(payload: UiPortalRecipientInput) {
  return apiPostJson<UiPortalRecipientMutationDto>("/api/v1/ui/portal/recipients/", payload);
}

export function patchPortalRecipient(recipientId: number, payload: UiPortalRecipientInput) {
  return apiPatchJson<UiPortalRecipientMutationDto>(
    `/api/v1/ui/portal/recipients/${recipientId}/`,
    payload,
  );
}

export function getPortalAccount() {
  return apiGetJson<UiPortalAccountDto>("/api/v1/ui/portal/account/");
}

export function patchPortalAccount(payload: UiPortalAccountUpdateInput) {
  return apiPatchJson<UiPortalAccountMutationDto>("/api/v1/ui/portal/account/", payload);
}
