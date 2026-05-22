# Account Onboarding Stopover Indications Design

## Goal

Tighten public account creation so ASF receives the minimum operational data needed to review shipper and recipient eligibility, while letting shippers indicate intended stopovers without turning those indications into shipment restrictions.

## Decisions

- Active form controls on the public account request page must render with a white background.
- Structure phone is required for shipper and recipient account requests.
- Administrative and preparation contacts must show every required address field instead of relying on hidden fields.
- Contact country is required for administrative and preparation contacts.
- The optional first recipient block remains optional during shipper signup. It must be labeled and explained as optional at signup but required before nominal order creation through a validated linked recipient.
- Stopover labels must render as `Ville (IATA), Pays`.
- Stopover lists must be sorted by city A-Z, then country A-Z.
- Recipient signup keeps `Escale de livraison` as the first required field.
- Shipper signup shows an informational checkbox list named `Escales envisagées`.
- Shipper stopover indications are stored on the public account request for review and history. They do not constrain future portal orders.
- `Autre escale` creates a feasibility request with subject `Demande nouvelle escale` and must not create a destination, recipient, grant, account, or shipper-recipient link.

## Shipper Stopover Behavior

| Selection | Behavior |
| --- | --- |
| No stopover selected | Account request can continue normally. |
| One or more served stopovers selected | Store the selected stopovers as indicative needs on the account request. |
| Only `Autre escale` selected | Keep required shipper structure and contact fields, hide non-relevant first-recipient fields, and show the new-stopover feasibility request fields. |
| Served stopover(s) plus `Autre escale` selected | Keep the normal account request and append the feasibility request fields at the end. |

## Scan Visibility

The current implementation should expose stopover indications in Scan account validation surfaces:

- pending account validation list
- account validation detail summary
- simple filter on the pending account validation list

This keeps account review inside Scan instead of Django admin.

## Separate Follow-Up

The richer `Contacts > Escales` cockpit is intentionally separate. It should provide a page per stopover with indicative shippers, linked recipients, correspondent contacts, requested products, shipment volumes, and new-stopover requests. That surface crosses account requests, shipment parties, recipient preferences, and shipment analytics, so it should not block the signup corrections.
