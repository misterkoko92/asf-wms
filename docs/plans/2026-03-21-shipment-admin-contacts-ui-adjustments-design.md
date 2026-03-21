# Shipment And Admin Contacts UI Adjustments Design

## Goal

Apply targeted UI changes on the legacy Django stack so shipment party selection is clearer during shipment creation and the admin contacts cockpit is easier to inspect.

## Shipment Creation

Keep `shipment_parties` as the only shipment-party runtime. The change stays in presentation and selection grouping:

- shipper labels become `Structure, Title First LAST`
- recipient labels become `Structure, Title First LAST`
- correspondent recipient labels become `Correspondant ASF - IATA - Title First LAST`
- shipper select keeps three groups:
  - ASF only
  - active shippers for the selected destination, alphabetically by structure
  - an instructional disabled option
- recipient select keeps three groups:
  - destination correspondent as recipient
  - recipients linked to the selected shipper and destination, alphabetically by structure
  - an instructional disabled option

The server payload remains the source of truth. JS only renders groups from canonical payload data already produced from `Shipment*`.

## Admin Contacts

The admin contacts page keeps the current cockpit actions, but becomes easier to browse:

- add a destination filter that scopes the shipment cockpit and configured correspondents
- keep the global contact directory unfiltered by destination
- render every table inside a closed-by-default collapse block
- enable the existing table tools (`data-table-tools="1"`) on every table so each table can be sorted and column-filtered like stock

## Implementation Shape

- `wms/contact_labels.py`: centralize the new label formats
- `wms/shipment_helpers.py` and `wms/static/scan/scan.js`: expose enough payload metadata and render the three shipment select blocks
- `wms/views_scan_admin.py`, `wms/scan_admin_contacts_cockpit.py`, and `templates/scan/admin_contacts.html`: add destination filtering and collapsible/table-tools rendering

## Risks

- grouped select rendering is duplicated between server labels and JS payload labels, so tests must lock both
- the destination filter must not accidentally hide the global contact directory
- disabled instructional options must not break current invalid-choice handling in the shipment form

## Testing

- shipment label formatting tests
- shipment form tests for grouped choices and ordering
- admin contacts view tests for destination filter and collapse/table markers
- bootstrap JS regression test for instructional options and grouped select markers
