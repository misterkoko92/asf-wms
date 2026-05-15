# PR13b Contact Identifier Visible Labels Audit

Date: 2026-05-14

Branch: `audit/pr13b-contact-identifier-labels`

Scope: inspection only. Excludes `docs/audits/` as implementation evidence.

## Executive Summary

Recommended PR13b implementation scope: externalize only explicit visible labels that directly name the contact identifier, preserving the current ASF defaults exactly where they already render:

- `ASF ID` for scan/admin contact form labels, scan contact search placeholder text, and tracking access email rows that already say `ASF ID`.
- `ID ASF` for the shipment tracking gateway contact-role identifier label and nearby tracking help copy that already says `ID ASF`.

The proposed two-key contract is confirmed with one adjustment: keep both keys, but define the consumers narrowly. Do not apply `contact_identifier_label = "ASF ID"` to every model/admin-derived `asf_id` label, because `Contact._meta.get_field("asf_id").verbose_name` is currently auto-generated as `asf id`, not explicitly `ASF ID`.

Implementation can proceed after human review as one small PR if it explicitly defers Django model `verbose_name`, gettext catalog changes, import/export columns, print/PDF output, and all data contracts.

## Inventory Table

| Occurrence / string | File path | Surface | Classification | Current visible output | Recommended PR13b action |
|---|---|---|---|---|---|
| `label=_("ASF ID")` | `wms/forms_admin_contacts_contact.py:72` | Scan/admin contact create/edit form source | A | `ASF ID` | Use `references.contact_identifier_label`. HIGH confidence. |
| `{{ contact_form.asf_id.label }}` | `templates/scan/includes/admin_contacts_contact_form.html:98` | Scan/admin contact create/edit form rendering | A | `ASF ID` via form field | No template change needed if form source changes. HIGH confidence. |
| `Nom, email, téléphone, ASF ID` | `templates/scan/includes/admin_contacts_filters_card.html:12` | Scan/admin contact search placeholder | A | `Nom, email, téléphone, ASF ID` | Compose with `references.contact_identifier_label` while preserving default string. MEDIUM confidence due gettext. |
| `ASF ID : {{ identifier }}` | `templates/emails/shipment_tracking_access_recovery.txt:3` | Tracking access recovery email | A | `ASF ID : <identifier>` | Use `references.contact_identifier_label`, not tracking label, to preserve current email wording. HIGH confidence. |
| `ASF ID : {{ identifier }}` | `templates/emails/shipment_tracking_pending_created.txt:6` | Tracking pending access email | A | `ASF ID : <identifier>` | Use `references.contact_identifier_label`, not tracking label, to preserve current email wording. HIGH confidence. |
| `self.assertIn("ASF ID", message)` | `wms/tests/emailing/tests_shipment_tracking_access.py:22,42` | Email template assertions | A | Test expects `ASF ID` | Add override/default assertions around the email label context. HIGH confidence. |
| `return "ID ASF"` | `wms/shipment_tracking_access.py:127-132` | Tracking identifier label helper | C | `ID ASF` for contact roles | Use `references.tracking_contact_identifier_label` for `TRACKING_CONTACT_ROLES`. HIGH confidence. |
| `tracking_identifier_label_for_role(...)` | `wms/forms.py:1437-1449` | Shipment tracking gateway form | C | `ID ASF` for shipper/recipient/correspondent | Covered by helper change; keep volunteer `ID bénévole` and fallback `Identifiant` unchanged. HIGH confidence. |
| `{{ gateway_form.identifier.label }}` | `templates/scan/shipment_tracking.html:336-338` | Tracking gateway page label | C | `ID ASF` for contact roles | No template change needed if helper changes. HIGH confidence. |
| `l'ID ASF` help text | `templates/scan/shipment_tracking.html:351` | Tracking lost-code help copy | C | Sentence mentions `ID ASF` | Consider context variable/blocktrans, or defer if grammar/config substitution is too awkward. MEDIUM confidence. |
| `self.assertEqual(..., "ID ASF")` | `wms/tests/forms/tests_forms_shipment_tracking.py:26-29` | Gateway form visible-label test | C | Test expects `ID ASF` | Add default and override assertions. HIGH confidence. |
| `tracking_identifier_label_for_role(...), "ID ASF"` | `wms/tests/shipment/tests_shipment_tracking_access.py:203-211` | Tracking helper test | C | Test expects `ID ASF` | Add default and override assertions. HIGH confidence. |
| Auto field label | `contacts/models.py:59`, effective metadata | Django model/admin-derived label | E | `asf id` from field name | Do not change in PR13b unless review accepts current-output drift or an admin-only override. |
| `list_display`, `readonly_fields`, fieldset `asf_id` | `contacts/admin.py:82,99,122` | Django admin Contact model | E | Likely `asf id` / `Asf id` via model metadata | Defer. Applying `ASF ID` would not preserve exact current admin output. |
| `msgid "Nom, email, téléphone, ASF ID"` | `locale/en/LC_MESSAGES/django.po:1498` | Gettext catalog | E | English translation includes `ASF ID` | Architectural decision needed. Do not update locale in PR13b unless translation scope is reopened. |
| `asf_id`, `id_asf` | `wms/import_services_contacts.py`, `wms/exports.py`, `wms/static/scan/import_templates/contacts.csv`, tests | Import/export columns and lookup keys | B | Technical columns, not labels | Do not change. |
| `structure_asf_id` | `wms/application/parties/use_cases.py`, `wms/parties/sync.py`, portal tests | Recipient structure reuse contract | B | Technical field/lookup | Do not change. |
| `Contact.asf_id` generation and persistence | `contacts/asf_ids.py`, `contacts/models.py`, contact tests | Generated identifier values and model field | B | Stored values like `ASF-C-*` | Do not change. PR13a owns generated prefix only. |
| `asf_id` duplicate/search lookups | `wms/admin_contacts_duplicate_detection.py`, `wms/views_scan_admin.py`, `wms/admin_contacts_contact_service.py` | Search, duplicate, save logic | B | No visible label by itself | Do not change lookup behavior. |
| tracking identifiers, grants, URLs, snapshots | `wms/views_shipment_tracking_access.py`, `wms/views_scan_shipments.py`, tracking tests | Access control and metadata | B | Identifier values in URLs/messages | Do not change parameter names, normalization, lookup, or stored snapshots. |
| default shipper `asf_id` family | `wms/default_shipper_bindings.py`, `wms/policies/shipment_parties.py`, default shipper tests | Default ASF shipper lookup | D | No PR13b label | Do not change. |
| Management command output `contact asf ids` | `contacts/management/commands/backfill_contact_asf_ids.py`, command tests | Developer/operator CLI | D | `Backfill contact asf ids [...]` | Out of PR13b visible-label scope. |
| Historical docs, plans, architecture graphs | `docs/`, excluding this audit and `docs/audits/` | Documentation/reference text | D | Various references | Do not treat as runtime surfaces. |

## Recommended PR13b Scope - Proposal Only

Candidate config keys:

- `installation.references.contact_identifier_label`, default exactly `ASF ID`.
- `installation.references.tracking_contact_identifier_label`, default exactly `ID ASF`.

Candidate implementation files:

- `wms/config/installation.py` - HIGH: existing references config owns contact identifier prefix and is the right namespace for adjacent labels.
- `wms/tests/config/tests_installation_config.py` - HIGH: current tests assert reference dataclass fields, defaults, overrides, immutability, and type hints.
- `wms/forms_admin_contacts_contact.py` - HIGH: explicit scan/admin form source for `ASF ID`.
- `templates/scan/includes/admin_contacts_filters_card.html` - MEDIUM: direct visible placeholder, but gettext currently wraps the whole string.
- `wms/shipment_tracking_access.py` - HIGH: single helper source for tracking contact-role `ID ASF`.
- `wms/forms.py` - HIGH: gateway form consumes the tracking helper; likely no direct label logic beyond tests.
- `templates/scan/shipment_tracking.html` - MEDIUM: dynamic gateway label is already helper-backed; lost-code sentence needs careful config interpolation or deferral.
- `templates/emails/shipment_tracking_access_recovery.txt` and `templates/emails/shipment_tracking_pending_created.txt` - HIGH: direct `ASF ID` rows.
- `wms/views_shipment_tracking_access.py` and `wms/views_scan_shipments.py` - MEDIUM: likely needed only to pass an email label into templates.
- `wms/tests/forms/tests_forms_shipment_tracking.py`, `wms/tests/shipment/tests_shipment_tracking_access.py`, `wms/tests/emailing/tests_shipment_tracking_access.py` - HIGH: existing assertions pin current visible labels.

Candidate consumers:

- `contact_identifier_label`: scan/admin contact form, scan/admin contact search placeholder, tracking access email templates that currently say `ASF ID`.
- `tracking_contact_identifier_label`: tracking helper for contact roles and tracking page help copy that currently says `ID ASF`.

Candidate tests:

- Config default/override/type/immutability tests for both keys.
- Contact CRUD form label default and override.
- Tracking helper/gateway form default and override.
- Email template rendering with a supplied label, plus view-level context if implementation passes label from view.
- Optional template response assertion for the lost-code help copy if that line is changed.

## Explicit Non-Goals

- Do not rename `Contact.asf_id`, DB fields, form field names, URLs, variables, serializer keys, import/export columns, or lookup behavior.
- Do not create migrations.
- Do not change existing stored values or generated values such as `ASF-C-00000001`.
- Do not rename `references.contact_identifier_generated_prefix`.
- Do not alter `asf_id`, `id_asf`, or `structure_asf_id` import/export and party-sync contracts.
- Do not touch `ASF-ORG-ROOT`, default shipper behavior, API headers, User-Agent values, `CommunicationFamily.EMAIL_ASF`, `email_asf`, print/PDF output, scan branding, PWA manifest, logout redirect, or legal/privacy/trust/footer identity.
- Do not perform broad search/replace.
- Do not update gettext catalogs unless translation scope is explicitly reopened.

## Risk Assessment

Behavior risks:

- Low if consumers are explicit and defaults match current strings.
- Medium for the tracking help sentence because config substitution inside French prose can create grammar or i18n drift.
- Medium for Django admin if touched, because the current model-derived label is `asf id`, not `ASF ID`.

Data contract risks:

- High if anyone changes `asf_id`, `id_asf`, `structure_asf_id`, URL parameters, import/export headers, or generated identifier values. These must remain untouched.

Test risks:

- Existing tests pin `ID ASF` and `ASF ID`. PR13b should extend them for overrides rather than loosening them.
- If email labels are moved into context, template-only tests need matching context updates.

White-label risks:

- Two labels are justified because ASF currently uses both `ASF ID` and `ID ASF` on different surfaces.
- Collapsing them would either alter ASF output or impose a UX rationalization outside white-label scope.
- Applying labels too broadly to model metadata would hide a current inconsistency rather than preserve ASF exactly.

## Implementation Recommendation

Recommendation: **a) implement as one small PR after this audit**, with strict scope exclusions.

The PR should add the two config keys, wire only the explicit A/C consumers above, and leave Django model/admin auto labels plus gettext catalog maintenance deferred. Splitting into admin/forms and tracking is not necessary if implementation remains narrow, but it is a safe fallback if review wants to avoid touching tracking emails and templates in the same PR.

## Observations

- `Contact._meta.get_field("asf_id").verbose_name` is `asf id`, and `_verbose_name` is `None`, so Django derives it from the field name. This is a real current ASF inconsistency with explicit `ASF ID` labels. Do not fix it in PR13b unless explicitly accepted.
- The tracking flow is inconsistent by design/current state: gateway UI uses `ID ASF`, while tracking access emails use `ASF ID`. PR13b should preserve both defaults.
- Gettext catalogs are present at `locale/fr/LC_MESSAGES/django.po` and `locale/en/LC_MESSAGES/django.po`. The only relevant catalog hit found was the English entry for `Nom, email, téléphone, ASF ID`; no `ID ASF` catalog hit was found. Translation scope is otherwise paused.
- The backfill management command and tests contain `contact asf ids` text, but this is CLI/developer output and not a PR13b visible contact-label target.

## Evidence Appendix

Representative snippets:

- `wms/forms_admin_contacts_contact.py:72`: `asf_id = forms.CharField(max_length=20, required=False, label=_("ASF ID"))`
- `templates/scan/includes/admin_contacts_contact_form.html:98-101`: the scan contact form renders `{{ contact_form.asf_id.label }}` and `{{ contact_form.asf_id }}`.
- `templates/scan/includes/admin_contacts_filters_card.html:12`: `placeholder="{% trans "Nom, email, téléphone, ASF ID" %}"`
- `wms/shipment_tracking_access.py:127-132`: `tracking_identifier_label_for_role()` returns `ID bénévole`, `ID ASF`, or `Identifiant`.
- `wms/forms.py:1437-1449`: `ShipmentTrackingGatewayForm` initializes `identifier` as `Identifiant`, then replaces it with `tracking_identifier_label_for_role(role)` when a role is known.
- `templates/scan/shipment_tracking.html:336-338`: the tracking gateway renders `{{ gateway_form.identifier.label }}`.
- `templates/scan/shipment_tracking.html:351`: lost-code copy says an email will indicate `l'ID ASF`.
- `templates/emails/shipment_tracking_access_recovery.txt:3`: `ASF ID : {{ identifier }}`
- `templates/emails/shipment_tracking_pending_created.txt:6`: `ASF ID : {{ identifier }}`
- `wms/tests/forms/tests_forms_shipment_tracking.py:26-29`: asserts gateway contact roles use `ID ASF`.
- `wms/tests/shipment/tests_shipment_tracking_access.py:203-211`: asserts the tracking helper returns `ID ASF`.
- `wms/tests/emailing/tests_shipment_tracking_access.py:22,42`: asserts tracking emails mention `ASF ID`.
- `contacts/admin.py:82,99,122`: Django admin references the technical `asf_id` field in `list_display`, `readonly_fields`, and fieldsets.
- Runtime metadata inspection: `Contact._meta.get_field("asf_id").verbose_name == "asf id"` and `_verbose_name is None`.
- `locale/en/LC_MESSAGES/django.po:1498-1499`: catalog contains the scan search placeholder `Nom, email, téléphone, ASF ID` and English `Name, email, phone, ASF ID`.
