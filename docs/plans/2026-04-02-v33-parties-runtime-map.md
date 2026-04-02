# V3.3 Parties Runtime Map

## Goal

Freeze the current shipment-party and portal-recipient runtime before moving logic into `wms/parties/`.

The target boundary for `V3.3` is:

- `wms/parties/selectors.py`
- `wms/parties/invariants.py`
- `wms/parties/sync.py`
- `wms/parties/merge.py`
- `wms/application/parties/use_cases.py`

## Current Runtime Entry Points

### Portal recipient sync

Current entrypoints:

- `wms/portal_recipient_sync.py`
- `wms/views_portal_account.py`
- `wms/views_portal_orders.py`

Current orchestration inside `wms/portal_recipient_sync.py` mixes:

- synced `Contact` reuse and upsert
- address upsert under the portal-specific label
- `ShipmentShipper` creation for the association
- `ShipmentRecipientOrganization` creation and reactivation
- `ShipmentRecipientContact` creation
- `ShipmentShipperRecipientLink` creation
- `ShipmentAuthorizedRecipientContact` defaulting

### Shipment-party selectors and rules

Current entrypoints:

- `wms/shipment_party_registry.py`
- `wms/shipment_party_rules.py`
- `wms/shipment_party_setup.py`
- `wms/models_domain/shipment_parties.py`

Current duplicated selector semantics:

- validated and active shipper filtering
- validated and active recipient-organization filtering
- destination-scoped recipient eligibility
- active authorized recipient-contact resolution

### Admin merge and cockpit mutations

Current entrypoints:

- `wms/admin_contacts_merge_service.py`
- `wms/scan_admin_contacts_cockpit.py`
- `wms/views_scan_admin.py`

Current merge/runtime responsibilities:

- merge organization scalar fields and addresses
- merge recipient structure documents
- merge recipient contacts and authorizations
- merge shipper-recipient links
- reconcile `ShipmentRecipientOrganization` graph state

## Current Structural Invariants

The runtime currently assumes:

- `ShipmentShipper` eligibility is restricted to active, validated rows with active organizations
- `ShipmentRecipientOrganization` eligibility is restricted to active, validated rows with active destinations and organizations
- portal sync may reuse a synced organization contact only when the recipient destination matches the existing shipment-recipient destination
- admin merge flows may only merge recipient organizations that stay on the same destination

## Target V3.3 Boundary

`wms/parties/` will become the runtime source of truth for:

- selectors reused by portal, scan, admin, and future application use cases
- graph-level invariants currently implicit in sync and merge flows
- portal-recipient synchronization
- recipient-organization merge semantics

Legacy modules will stay in place temporarily as adapters:

- `wms/portal_recipient_sync.py`
- `wms/shipment_party_registry.py`
- `wms/shipment_party_rules.py`
- `wms/admin_contacts_merge_service.py`

## First Migration Slice

The first executable `V3.3` slice should:

1. add `wms/parties/` selectors and invariants
2. route portal recipient sync through `wms/application/parties/use_cases.py`
3. keep views and old helper modules as compatibility adapters
