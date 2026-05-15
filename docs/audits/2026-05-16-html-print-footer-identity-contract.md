# HTML Print Footer Identity Contract Audit

## 1. Scope and baseline

- Current branch for this audit draft: `audit/html-print-footer-identity-contract`.
- Branch was created from `main` at `1545c0665e7b11075d1d188cd4d7c0c664a454a2`.
- `git status --short` was clean before creating this audit document.
- This PR16 work is audit-only. No runtime code, templates, tests, installation config, namespaces, or print layout files were changed.
- PR15 is already merged. After PR15, `org_name` comes from `installation.identity.organization_full_name` through `wms.documents.build_org_context()`, while the context key remains `org_name`.

## 2. Surfaces inspected

Primary template surfaces inspected:

- `templates/print/base_document.html`
- `templates/print/base_a5.html`

Supporting context and rendering files inspected:

- `wms/documents.py`
- `wms/print_context.py`
- `wms/print_renderer.py`
- `wms/views_print_docs.py`
- `wms/shipment_view_helpers.py`
- `wms/views_print_templates.py`

Additional config/default surfaces inspected during the audit correction:

- `asf_wms/settings.py`
- `.env.example`
- `deploy/pythonanywhere/asf-wms.env.template`
- `deploy/pythonanywhere/asf-wms.messmed.env.template`

These additional files were inspected because `build_org_context()` reads `settings.ORG_ADDRESS`, `settings.ORG_CONTACT`, and `settings.ORG_SIGNATORY`; the correction needed to determine whether the settings defaults or ASF-like environment templates already carry the exact structured footer lines.

## 3. Exact visible footer strings

| file | line/reference | exact visible string or summarized string if long | classification A-F | duplicated? | currently hardcoded or context-backed | notes |
|---|---:|---|---|---|---|---|
| `templates/print/base_document.html` | 79 | `https://aviation-sans-frontieres.org/messmed // messmed@aviation-sans-frontières-fr.org` | B | yes | Hardcoded only | Public URL and email contact line. Contains ASF-specific domain and service path. Not backed by `org_contact`. |
| `templates/print/base_document.html` | 80 | `Siège: Bat 293, Porte 1150, Orly Fret 768 - 94398 Orly Aérogare Cedex - Tel: (33) 1 49 75 74 36` | C | yes | Hardcoded only | Headquarters address plus phone. Wrapped in `blocktrans`, but not installation-config or settings-backed. |
| `templates/print/base_document.html` | 81 | `Magasin: Bat. 7200, Porte 2D520, rue de la Remise - 95700 ROISSY en France - Tél: (33) 1 74 25 03 22` | C | yes | Hardcoded only | Warehouse address plus phone. Wrapped in `blocktrans`, but not installation-config or settings-backed. |
| `templates/print/base_document.html` | 82 | `Association reconnue d'utilité publique par décret du 12 novembre 1993` | D | yes | Hardcoded only | Legal/public utility wording. It is ASF-specific and should not be generalized without a human legal/editorial decision. |
| `templates/print/base_a5.html` | 79 | `https://aviation-sans-frontieres.org/messmed // messmed@aviation-sans-frontières-fr.org` | B | yes | Hardcoded only | Exact duplicate of `base_document.html`. |
| `templates/print/base_a5.html` | 80 | `Siège: Bat 293, Porte 1150, Orly Fret 768 - 94398 Orly Aérogare Cedex - Tel: (33) 1 49 75 74 36` | C | yes | Hardcoded only | Exact duplicate of `base_document.html`. |
| `templates/print/base_a5.html` | 81 | `Magasin: Bat. 7200, Porte 2D520, rue de la Remise - 95700 ROISSY en France - Tél: (33) 1 74 25 03 22` | C | yes | Hardcoded only | Exact duplicate of `base_document.html`. |
| `templates/print/base_a5.html` | 82 | `Association reconnue d'utilité publique par décret du 12 novembre 1993` | D | yes | Hardcoded only | Exact duplicate of `base_document.html`. |

No footer string in either base template is currently context-backed. The only footer control is `hide_footer`.

## 4. Current context and settings flow

The two base templates receive Django template context from whichever document template extends or renders through them. In both base templates, the footer is rendered unless `hide_footer` is truthy. The footer text itself does not read `org_name`, `org_address`, `org_contact`, `org_signatory`, or any installation config value.

`wms.documents.build_org_context()` currently returns:

- `org_name`: `installation.identity.organization_full_name`
- `org_address`: `settings.ORG_ADDRESS`, falling back to `""`
- `org_contact`: `settings.ORG_CONTACT`, falling back to `""`
- `org_signatory`: `settings.ORG_SIGNATORY`, falling back to `""`

The approved files show `build_org_context()` included in shipment document contexts, sample document contexts, billing document contexts, and sample billing contexts. They also show several contexts that do not carry the org keys, including carton document, contact sheet, carton contact label, carton picking, label, product label, and product QR contexts. Most of those contexts explicitly set `hide_footer` to `True`.

After PR15, the important change is only the source of `org_name`: it now comes from `installation.identity.organization_full_name` through `build_org_context()`. The footer block did not change in PR15 and still hardcodes all visible contact, address, and legal text.

`ORG_ADDRESS`, `ORG_CONTACT`, and `ORG_SIGNATORY` remain part of the effective document identity context contract because `build_org_context()` still exposes them as `org_address`, `org_contact`, and `org_signatory`. They are not currently used by the two base footer blocks. Within the approved files, they are available to body and custom layout rendering when the render path receives a context produced by `build_org_context()`. This audit did not inspect child body templates, so it does not claim which body templates print each key today.

Correction evidence from the settings/default files shows that `ORG_ADDRESS` and `ORG_CONTACT` do not naturally carry the three structured footer contact/address lines. `asf_wms/settings.py` falls back to placeholder strings, and `.env.example` plus the PythonAnywhere environment templates use one placeholder address and one placeholder email, not the current URL/email, `Siège: ...`, and `Magasin: ...` footer structure.

## 5. Configuration options analysis

Option A - Reuse existing context keys only.

- Benefits: smallest config surface; no new installation keys; aligns with PR15's decision to keep existing `org_name`; can use `org_address` and `org_contact` without adding namespaces.
- Risks: `org_address` and `org_contact` are broad document identity settings, not footer-specific fields. They do not naturally represent two address lines plus one service URL/email line. `org_signatory` is not relevant to the footer.
- Files likely touched: `wms/documents.py`, `templates/print/base_document.html`, `templates/print/base_a5.html`, focused print footer tests.
- ASF behavior preservation risk: medium unless the implementation includes exact ASF fallbacks and tests that lock the current visible footer under defaults.
- White-label usefulness: moderate for contact/address override, low for legal wording.
- Recommendation status: rejected for PR17 after config/default inspection. Reusing `org_contact` and `org_address` would not preserve the byte-exact current footer under default ASF-like templates without pre-formatting environment values or adding hidden fallback formatting in code.

Option B - Add narrow installation identity/contact keys.

- Benefits: explicit white-label contract; avoids overloading `ORG_ADDRESS` and `ORG_CONTACT`; can model the existing footer lines exactly.
- Risks: adds new config surface before legal/editorial decisions are settled; "contact" keys do not currently have a clear existing namespace; adding them under `identity` may blur brand identity and operational contact details.
- Files likely touched: `wms/config/installation.py`, `wms/documents.py`, both base templates, installation config tests, print footer tests.
- ASF behavior preservation risk: low if defaults are exact copies of current strings, but the schema expansion itself is a governance cost.
- White-label usefulness: high for footer contact/address details.
- Recommendation status: recommended direction for a later footer-parameterization PR, after the legal/contact/editorial decisions are made. It should not be smuggled into PR17.

Option C - Add a dedicated documents/print/footer namespace.

- Benefits: precise model for footer lines, legal notices, and future print-specific policy.
- Risks: too broad for the next slice; conflicts with the PR15 decision not to introduce `installation.documents` or a document namespace; encourages premature product architecture.
- Files likely touched: installation config schema, documents context, base templates, tests, possibly documentation.
- ASF behavior preservation risk: low if defaults are copied exactly, but high process risk due unnecessary abstraction.
- White-label usefulness: high eventually, but not needed for a first safe slice.
- Recommendation status: not recommended for PR17.

Option D - Leave legal/public-utility wording hardcoded for now and only parameterize contact/address details.

- Benefits: avoids making legal claims configurable without human review; keeps PR17 small; addresses the clearest operational white-label leak in URL, email, and addresses.
- Risks: non-ASF deployments would still show ASF public-utility wording if the footer is visible; that must be called out as an accepted temporary limitation or blocked before real white-label use.
- Files likely touched: `wms/documents.py`, both base templates, focused print footer tests.
- ASF behavior preservation risk: low if hardcoded legal text remains unchanged and contact/address defaults are tested.
- White-label usefulness: moderate; enough for an incremental internal slice, not enough for external non-ASF launch.
- Recommendation status: not recommended as a parameterization PR17 because it depends on rejected Option A. PR17 may still keep the footer hardcoded and add characterization coverage.

Existing installation keys are not sufficient by themselves for the full footer. `identity.organization_full_name`, `identity.organization_brand_name`, and `identity.product_display_name` express names, brand, and product shell identity. They do not express public URL/email, headquarters address, warehouse address, phone labels, or the legal public-utility sentence.

## 6. Recommended PR17 implementation slice

Preferred PR17 slice: keep the HTML print footer hardcoded for now and add characterization coverage only. Defer footer parameterization to a later PR backed by narrow installation keys. Option A is rejected for PR17 because the inspected settings/default files do not naturally carry the current structured footer lines.

Exact files to touch:

- `wms/tests/views/test_html_print_footer_identity.py` as a new focused test module, or the closest existing print-render test module if PR17 inspection shows a stronger local convention.

Exact values/strings to parameterize:

- None in PR17.

Exact values/strings to leave hardcoded:

- `https://aviation-sans-frontieres.org/messmed // messmed@aviation-sans-frontières-fr.org`
- `Siège: Bat 293, Porte 1150, Orly Fret 768 - 94398 Orly Aérogare Cedex - Tel: (33) 1 49 75 74 36`
- `Magasin: Bat. 7200, Porte 2D520, rue de la Remise - 95700 ROISSY en France - Tél: (33) 1 74 25 03 22`
- `Association reconnue d'utilité publique par décret du 12 novembre 1993`

Context/config decision:

- Do not reuse `org_contact` and `org_address` for footer rendering in PR17.
- Do not use `org_name` in the footer in PR17; neither current footer has an organization-name line.
- Do not use `org_signatory` in the footer.
- Add no installation config keys in PR17.
- Add no new namespace in PR17.
- Do not add derived render-only footer context keys in PR17.
- A later parameterization PR should use narrow installation keys rather than hidden fallback formatting in `build_org_context()`. Exact key names remain open and should be decided in that later PR.
- PR17 must avoid the gettext-extraction side effect by leaving the existing `blocktrans` footer literals unchanged. A later PR that replaces those literals with variables must explicitly document and accept the extraction change, or choose a deliberate mechanism to preserve the translatable strings.

Expected tests:

- Render `base_document.html` with default context and assert the four current footer lines remain visible exactly.
- Render `base_a5.html` with default context and assert the four current footer lines remain visible exactly.
- Render both templates with `hide_footer=True` and assert no footer contact/address/legal line is visible.
- Override `ORG_CONTACT` and `ORG_ADDRESS` and assert the base footer remains unchanged in PR17, documenting that these settings are not yet the footer contract.
- Assert `identity.organization_full_name` still feeds `org_name` for document contexts and is not part of footer rendering.

Expected unchanged behavior under ASF defaults:

- Same visible footer strings.
- Same footer visibility behavior through `hide_footer`.
- Same logo, body blocks, document context keys, billing contexts, shipment document routes, and dynamic layout rendering behavior.

## 7. Explicit exclusions for PR17

PR17 must not include legal/footer statutory wording changes beyond leaving the current legal line unchanged. It must not add installation config keys, add namespaces, touch `wms/print_layouts.py`, touch donation certificate logic/templates, touch shipment/customs role labels, touch logos, image paths, stamp images, or alt text, touch XLSX templates under `data/print_templates`, touch Microsoft Graph/local helper/PDF merge/pypdf logic, touch planning workbook/PDF exports, touch gettext catalogs, touch contact identifier labels or generated prefixes, touch ASF-ORG-ROOT or default shipper, touch API headers/User-Agent, touch `CommunicationFamily.EMAIL_ASF` or persisted value `email_asf`, perform broad search-and-replace, or include implementation snippets intended to be applied blindly.

## 8. Risks and open decisions

Resolved by correction inspection:

- `ORG_CONTACT` and `ORG_ADDRESS` do not naturally express the current three structured footer contact/address lines in the inspected defaults or ASF-like environment templates.
- Option A is rejected for PR17. Reusing `org_contact` and `org_address` would require either pre-formatting environment values outside code or adding hidden ASF fallback formatting in code.
- PR17 can avoid gettext extraction changes by leaving the `blocktrans` footer literals unchanged.

Remaining open decisions:

- Whether the footer URL/email line is a generic organization contact, a MessMed service contact, or an ASF-specific operational contact.
- Whether one future address key should represent both headquarters and warehouse address lines, or whether those lines require separate narrow keys.
- Whether the warehouse address should remain visible for all document types where the footer is shown.
- Whether non-ASF deployments may legally show any public-utility wording, and what replacement wording should be when they cannot.
- Whether `ORG_ADDRESS`, `ORG_CONTACT`, and `ORG_SIGNATORY` should remain Django settings long term or be migrated into installation config in a later governed PR.
- Whether future footer wording should remain translatable through gettext or become installation-controlled text outside gettext catalogs.
- If a later parameterization PR replaces the `blocktrans` literal footer address lines with variables, gettext extraction for those ASF strings changes even if gettext catalogs are untouched. That side effect must be documented and accepted, or deliberately avoided, in that later PR.

## 9. Evidence appendix

- `templates/print/base_document.html:77-83` renders the footer when `not hide_footer`, with four literal visible footer lines.
- `templates/print/base_a5.html:77-83` renders the same footer when `not hide_footer`, with the same four literal visible footer lines.
- `wms/documents.py:9-15` defines `build_org_context()` and maps `org_name`, `org_address`, `org_contact`, and `org_signatory`.
- `wms/print_context.py:331` includes `build_org_context()` in shipment document contexts.
- `wms/print_context.py:366-367` hides the footer for `packing_list_shipment`, `shipment_note`, `customs`, and `donation_certificate`.
- `wms/print_context.py:403-413` builds contact sheet context from shipment context but returns a subset and sets `hide_footer=True`.
- `wms/print_context.py:540` includes `build_org_context()` in sample document contexts.
- `wms/print_context.py:687-701` includes `build_org_context()` in billing document contexts and sets `hide_footer=False`.
- `wms/print_context.py:748-762` includes `build_org_context()` in sample billing document contexts and sets `hide_footer=False`.
- `wms/shipment_view_helpers.py:96-101` renders either a dynamic document from pre-rendered blocks or the default print template with the context.
- `wms/shipment_view_helpers.py:450-463` chooses shipment document context and hands it to `_render_document_with_layout()`.
- `wms/shipment_view_helpers.py:466-473` renders carton document context, which does not include `build_org_context()` and has `hide_footer=True`.
- `wms/print_renderer.py:106-120` renders text and context blocks using the supplied context, so org keys are available to custom layout blocks when the caller supplies them.
- `wms/print_renderer.py:208-220` renders layout blocks from the resolved layout and context.
- `wms/views_print_docs.py:161-166` has a carton document dynamic/default render path with `hide_footer=True`.
- `wms/views_print_docs.py:409-410` renders print partials with the supplied context for bundle sections.
- `wms/views_print_docs.py:1033-1045` routes shipment-view HTML documents through `render_shipment_document()`.
- `wms/views_print_templates.py:747-753` builds preview context, renders layout blocks with it, and returns the dynamic document preview.
- `asf_wms/settings.py:429-432` defines `ORG_NAME`, `ORG_ADDRESS`, `ORG_CONTACT`, and `ORG_SIGNATORY` from environment variables with placeholder fallbacks.
- `.env.example:38-42` provides example organization metadata with one placeholder address and one placeholder contact email.
- `deploy/pythonanywhere/asf-wms.env.template:23-27` provides PythonAnywhere organization metadata placeholders, not the structured footer lines.
- `deploy/pythonanywhere/asf-wms.messmed.env.template:16-19` provides the MessMed PythonAnywhere organization metadata placeholders, not the structured footer lines.
