# Contact Label Template Design

**Goal:** Align the legacy XLSX contact label template with the current workbook layout and the uppercase display rules already used for the shipment note.

**Scope:** Only the legacy Django print-pack contact label document (`C / contact_label / shipment`). Translation and Next/React migration scope stay untouched.

## Decisions

- Apply the same display rules as the shipment note:
  - `Nom` uses the concatenated person label.
  - `Organisation` uses the organization name.
  - `Adresse` uses a single-line concatenated postal address.
  - `Contact` uses the primary email only.
  - `Telephone` uses the primary phone only.
- All mapped text is rendered in uppercase through mapping transforms.
- Keep the same behavior for organization-only contacts: the `Nom` row may stay blank when no distinct person label exists.

## Mapping Strategy

- Shipper block:
  - `B3` name
  - `B4` organization
  - `B5` address
  - `B6` contact
  - `B7` phone
- Recipient block:
  - `B10` name
  - `B11` organization
  - `B12` address
  - `B13` contact
  - `B14` phone
- Correspondent block:
  - `B17` name
  - `B18` organization
  - `B19` address
  - `B20` contact
  - `B21` phone

## Verification

- Update seeded mapping tests to assert the new cell references, source keys, and uppercase transforms.
- Run the targeted print-pack model and engine tests.
