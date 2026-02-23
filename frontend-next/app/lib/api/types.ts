export type ScanDashboardDto = {
  kpis: {
    open_shipments: number;
    stock_alerts: number;
    open_disputes: number;
    pending_orders: number;
    shipments_delayed: number;
  };
  timeline: Array<{
    id: number;
    shipment_id: number;
    reference: string;
    status: string;
    timestamp: string;
    comments: string;
  }>;
  pending_actions: Array<{
    type: string;
    reference: string;
    label: string;
    priority: string;
    owner: string;
  }>;
  filters: {
    destination: string;
  };
  updated_at: string;
};

export type ScanStockDto = {
  filters: {
    q: string;
    category: string;
    warehouse: string;
    sort: string;
  };
  meta: {
    total_products: number;
    low_stock_threshold: number;
  };
  products: Array<{
    id: number;
    sku: string;
    name: string;
    brand: string;
    category_id: number | null;
    category_name: string;
    location: string;
    stock_total: number;
    last_movement_at: string | null;
    state: string;
  }>;
  categories: Array<{ id: number; name: string }>;
  warehouses: Array<{ id: number; name: string }>;
};

export type ShipmentFormOptionsDto = {
  products: Array<Record<string, string | number | boolean | null>>;
  available_cartons: Array<Record<string, string | number | boolean | null>>;
  destinations: Array<Record<string, string | number | boolean | null>>;
  shipper_contacts: Array<Record<string, string | number | boolean | null>>;
  recipient_contacts: Array<Record<string, string | number | boolean | null>>;
  correspondent_contacts: Array<Record<string, string | number | boolean | null>>;
};

export type PortalDashboardDto = {
  kpis: {
    orders_total: number;
    orders_pending_review: number;
    orders_changes_requested: number;
    orders_with_shipment: number;
  };
  orders: Array<{
    id: number;
    reference: string;
    review_status: string;
    review_status_label: string;
    shipment_id: number | null;
    shipment_reference: string;
    requested_delivery_date: string | null;
    created_at: string;
  }>;
};

export type UiShipmentSummary = {
  id: number;
  reference: string;
  status: string;
  status_label: string;
  tracking_token: string;
  is_disputed: boolean;
  closed_at: string | null;
};

export type UiStockUpdateInput = {
  product_code: string;
  quantity: number;
  expires_on: string;
  lot_code?: string;
  donor_contact_id?: number | null;
};

export type UiStockUpdateDto = {
  ok: boolean;
  message: string;
  lot_id: number;
  product_id: number;
  quantity_on_hand: number;
  location_id: number;
  receipt_id: number | null;
};

export type UiStockOutInput = {
  product_code: string;
  quantity: number;
  shipment_reference?: string;
  reason_code?: string;
  reason_notes?: string;
};

export type UiStockOutDto = {
  ok: boolean;
  message: string;
  product_id: number;
  shipment_id: number | null;
  quantity: number;
};

export type UiShipmentLineInput = {
  carton_id?: number | null;
  product_code?: string;
  quantity?: number | null;
};

export type UiShipmentMutationInput = {
  destination: number;
  shipper_contact: number;
  recipient_contact: number;
  correspondent_contact: number;
  lines: UiShipmentLineInput[];
};

export type UiShipmentMutationDto = {
  ok: boolean;
  message: string;
  shipment: UiShipmentSummary;
  line_count: number;
};

export type UiShipmentTrackingEventInput = {
  status: string;
  actor_name: string;
  actor_structure: string;
  comments?: string;
};

export type UiShipmentTrackingEventDto = {
  ok: boolean;
  message: string;
  shipment: UiShipmentSummary;
  tracking_event: {
    id: number;
    status: string;
    status_label: string;
    created_at: string;
    comments: string;
  };
};

export type UiShipmentCloseDto = {
  ok: boolean;
  message: string;
  shipment: UiShipmentSummary;
};

export type UiPortalOrderCreateInput = {
  destination_id: number;
  recipient_id: string;
  notes?: string;
  lines: Array<{
    product_id: number;
    quantity: number;
  }>;
};

export type UiPortalOrderCreateDto = {
  ok: boolean;
  message: string;
  order: {
    id: number;
    reference: string;
    review_status: string;
    review_status_label: string;
    shipment_id: number | null;
    shipment_reference: string;
    created_at: string;
  };
};

export type UiPortalRecipientInput = {
  destination_id: number;
  structure_name: string;
  contact_title?: string;
  contact_last_name?: string;
  contact_first_name?: string;
  phones?: string;
  emails?: string;
  address_line1: string;
  address_line2?: string;
  postal_code?: string;
  city?: string;
  country?: string;
  notes?: string;
  notify_deliveries?: boolean;
  is_delivery_contact?: boolean;
};

export type UiPortalRecipient = {
  id: number;
  display_name: string;
  destination_id: number | null;
  destination_label: string;
  structure_name: string;
  contact_title: string;
  contact_first_name: string;
  contact_last_name: string;
  phones: string;
  emails: string;
  address_line1: string;
  address_line2: string;
  postal_code: string;
  city: string;
  country: string;
  notes: string;
  notify_deliveries: boolean;
  is_delivery_contact: boolean;
  is_active: boolean;
};

export type UiPortalRecipientsDto = {
  recipients: UiPortalRecipient[];
  destinations: Array<{
    id: number;
    label: string;
  }>;
};

export type UiPortalRecipientMutationDto = {
  ok: boolean;
  message: string;
  recipient: UiPortalRecipient;
};

export type UiPortalAccountContactInput = {
  title?: string;
  last_name?: string;
  first_name?: string;
  phone?: string;
  email: string;
  is_administrative?: boolean;
  is_shipping?: boolean;
  is_billing?: boolean;
};

export type UiPortalAccountUpdateInput = {
  association_name: string;
  association_email?: string;
  association_phone?: string;
  address_line1: string;
  address_line2?: string;
  postal_code?: string;
  city?: string;
  country?: string;
  contacts: UiPortalAccountContactInput[];
};

export type UiPortalAccountDto = {
  association_name: string;
  association_email: string;
  association_phone: string;
  address_line1: string;
  address_line2: string;
  postal_code: string;
  city: string;
  country: string;
  notification_emails: string[];
  portal_contacts: Array<{
    id: number;
    title: string;
    first_name: string;
    last_name: string;
    phone: string;
    email: string;
    is_administrative: boolean;
    is_shipping: boolean;
    is_billing: boolean;
  }>;
};

export type UiPortalAccountMutationDto = {
  ok: boolean;
  message: string;
  account: UiPortalAccountDto;
};
