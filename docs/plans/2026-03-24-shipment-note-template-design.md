# Shipment Note Template Design

**Goal:** Align the legacy XLSX shipment note template with the current workbook layout and business rules used for shipment documents.

**Scope:** Only the legacy Django print-pack shipment note document (`C / shipment_note / shipment`). Translation and Next/React migration scope stay untouched.

## Decisions

- Keep these cells intentionally unmapped and therefore blank:
  `NUMERO DE VOL`, `DATE DE VOL`, `TRANSITAIRE`, `VISA DOUANE`, `NUMERO EX`,
  `RESP. DOUANE ASF`, `RESPONSABLE VOL ASF`, `COMMANDANT DE BORD`, and signatures.
- Remap the shipment note document to the new workbook coordinates that use merged cells for party details.
- For merged display rows:
  - `Nom` uses a concatenated person label.
  - `Adresse` uses a single-line concatenated postal address.
  - `Contact` uses the primary email only.
  - `Telephone` uses the primary phone only.
- All mapped text is rendered in uppercase through mapping transforms.

## Data Model Changes

- Add a party `display_name` field for person labels that avoids duplicating organization-only contacts on the `Nom` row.
- Add a party `postal_address_display` field formatted as:
  `street, postal_code city - country`

## Mapping Strategy

- Top shipment summary fields move to `B7`, `D7`, `B8`, `D8`, `B10`, and `B11/B12`.
- Party blocks move to merged anchors:
  - shipper: `B18`, `B19`, `B20`, `B21`, `B22`
  - recipient: `B25`, `B26`, `B27`, `B28`, `B29`
  - correspondent: `B32`, `B33`, `B34`, `B35`, `B36`

## Verification

- Update seeded mapping tests to assert the new cell references and source keys.
- Update payload tests to assert the new display helpers.
- Run the targeted print-pack model and engine tests.
