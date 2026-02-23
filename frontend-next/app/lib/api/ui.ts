import { apiGetJson, apiPatchJson, apiPostJson } from "./client";
import type {
  PortalDashboardDto,
  ScanDashboardDto,
  ScanStockDto,
  ShipmentFormOptionsDto,
  UiShipmentCloseDto,
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
  UiStockOutDto,
  UiStockOutInput,
  UiStockUpdateDto,
  UiStockUpdateInput,
} from "./types";

export function getScanDashboard() {
  return apiGetJson<ScanDashboardDto>("/api/v1/ui/dashboard/");
}

export function getScanStock(query = "") {
  const suffix = query ? `?${query}` : "";
  return apiGetJson<ScanStockDto>(`/api/v1/ui/stock/${suffix}`);
}

export function getShipmentFormOptions() {
  return apiGetJson<ShipmentFormOptionsDto>("/api/v1/ui/shipments/form-options/");
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
