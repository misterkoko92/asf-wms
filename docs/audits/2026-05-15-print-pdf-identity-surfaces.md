# Print / PDF Identity Surfaces Audit

Date: 2026-05-15

Branch: `audit/print-pdf-identity-surfaces`

Base: `main` at `ef1816e563fdbae49ade89acc10ccba1e10e696d`

Change classification: B. Generic reusable capability and E. Legacy debt reduction, constrained by A. ASF operational continuity.

Scope: audit only. No runtime, template, config, test, migration, model, binary template, email, import/export, API, PWA, legal-page, scan-branding, or default-shipper changes were made.

## 0. PDF / Print Generation Stack Inventory

This section defines the document boundary used by the rest of the audit.

| Stack / mechanism | Call sites | Input templates / files | Output type | Runtime entrypoint / job | Leaves application? | Audit boundary |
|---|---|---|---|---|---|---|
| Browser-rendered HTML print templates | `wms/views_print_docs.py`, `wms/shipment_view_helpers.py`, `wms/views_print_labels.py`, `wms/product_label_printing.py`, `wms/views_print_templates.py`, `wms/print_context.py`, `wms/print_renderer.py`, `wms/print_layouts.py` | `templates/print/*`, especially `templates/print/partials/*`, `templates/print/base_document.html`, `templates/print/base_a5.html`, `templates/print/blocks/*` | HTML intended for browser print or browser PDF save | Scan routes such as `scan_shipment_view_document`, `scan_shipment_view_bundle`, `scan_cartons_view_bundle`, `scan_shipment_labels`, `scan_product_labels_print_labels`, `scan_product_labels_print_qr`, and `scan_print_template_preview` | Yes. Operators print or save these documents, labels, and previews. | In scope. |
| XLSX print pack rendered to PDF through Microsoft Graph | `wms/print_pack_engine.py`, `wms/print_pack_graph.py`, `wms/views_print_docs.py`, `wms/views_print_labels.py`, `wms/views_planning.py`, admin actions | `data/print_templates/*.xlsx`, DB `PrintPack*` records, `PrintCellMapping`, runtime shipment/carton context | XLSX, PDF, merged PDF, two-up PDF | `generate_pack`, `render_pack_xlsx_documents`, `_build_pdf_response_from_xlsx_documents`, `scan_shipment_view_bundle_pdf`, strict planning packing-list PDF, label/document Graph paths | Yes. PDFs are returned inline/downloaded and may be synchronized to OneDrive. Source XLSX can also be returned as fallback/helper input. | In scope. |
| PDF merge / imposition through `pypdf` | `wms/print_pack_pdf.py`, `tools/planning_comm_helper/pdf_render.py` | PDF bytes produced by Graph, local helper, or helper job | Merged PDF or imposed A4 PDF | `merge_pdf_documents`, `impose_two_up_pdf_on_a4`, helper merge code | Yes, as merged document output. | In scope for metadata and file-boundary analysis. No identity strings are injected by this layer. |
| Local document helper job / document download | `wms/local_document_helper.py`, consumed by print docs, labels, admin, planning paths | Generated XLSX document URLs and helper job JSON | JSON job, individual XLSX download, helper-produced PDF outside Django | `build_local_helper_job_response`, `build_local_helper_document_response` | Yes. The helper fetches document URLs and produces local files/PDFs for operators. | In scope for filenames, input documents, and helper output boundary. |
| Generated print artifact persistence and OneDrive sync | `wms/print_artifact_delivery.py`, `wms/print_pack_sync.py`, `wms/artifacts/proofs.py`, `wms/print_pack_engine.py` | Generated PDF/XLSX artifacts | Stored PDF/XLSX files and OneDrive upload paths | `process_print_artifact_queue`, `upload_print_artifact_to_onedrive` | Yes. Artifacts can be downloaded and uploaded to configured Graph/OneDrive storage. | In scope for filenames and path identity. |
| Planning workbook and planning PDF | `wms/planning/exports.py`, `wms/artifacts/planning.py`, `wms/views_planning.py`, `tools/planning_comm_helper/planning_pdf.py`, `tools/planning_comm_helper/excel_pdf.py` | `data/planning_templates/Planning-maquette.xlsx`, planning version data | XLSX and PDF attachment/download | `planning_version_communication_workbook`, `planning_version_communication_pdf`, planning artifact generation | Yes. Planning workbooks/PDFs are downloaded and attached to communications. | In scope for document metadata and generated filenames. No visible ASF string was found in the planning template. |
| QR / image-for-print generation | `wms/models_domain/shipment.py`, `wms/models_domain/catalog.py`, rendered by print/label views | Runtime shipment URL/reference, product SKU, generated QR PNG files | PNG image embedded in labels / print views | Shipment QR generation, product QR generation, product label print routes | Yes. QR labels are printed and scanned outside the app. | In scope for implicit encoded values and filenames. |
| Browser print CSS / print-specific layout CSS | `templates/print/*`, `wms/static/scan/*` when used by print templates | HTML/CSS | Print layout | Browser print | Yes. | In scope when CSS or template structure exposes identity. No standalone CSS-only identity injection was found. |
| WeasyPrint, ReportLab, wkhtmltopdf, xhtml2pdf, pdfkit | Search of dependencies and runtime code | None found | None | None found | No | Not present. |

Dependency evidence found `openpyxl`, `Pillow`, `qrcode`, `pypdf`, and `pypdfium2` in dependency files. Runtime usage found `openpyxl`, `qrcode`, `pypdf`, Microsoft Graph conversion, and desktop Excel conversion. No runtime usage was found for WeasyPrint, ReportLab, wkhtmltopdf, xhtml2pdf, or pdfkit.

## 1. Executive Summary

Print/PDF identity is safe to tackle next, but not as one broad replacement. The audit confirms the highest-risk identity surfaces are concentrated in a small set of generated-document templates and XLSX print-pack templates. Those documents are authoritative paperwork, so they require tighter defaults and tests than normal UI copy.

Implementation is not safe as a single sweeping PR. It should be split by output family:

- PR15 should handle browser-rendered HTML print identity only, with exact ASF defaults and narrow document-issuer keys.
- A later PR should handle XLSX print-pack templates and Graph PDF output, because binary template assets, workbook metadata, and embedded images need a separate review path.
- Donation-certificate legal/signatory/stamp wording should be a dedicated decision-backed slice, not folded into a generic brand-label change.

Recommended next PR after this audit: add narrowly-scoped document issuer configuration for HTML print headers/footers and the visible ASF customs/flight labels in browser print partials, preserving current ASF defaults exactly and excluding XLSX templates, donation-certificate legal wording, Contact `asf_id`, default shipper, emails, API namespaces, scan branding, PWA, and legal pages.

## 2. Inventory Table

| File path | Function / template / view / test | Exact visible string or identity concept | Hardcoded or implicit | User-facing surface | Runtime path / entrypoint | Leaves application? | Current ASF behavior | Risk | Recommendation |
|---|---|---|---|---|---|---|---|---|---|
| `templates/print/partials/shipment_note_body.html` | Shipment note body | `Logo ASF`; `messmed@aviation-sans-frontieres-fr.org // +33 6 50 03 72 36`; `Association reconnue d'utilité publique depuis 1993`; `RESP. DOUANE ASF / ASF Customs agent`; `RESPONSABLE VOL ASF / ASF Flight Manager` | Hardcoded | Shipment note / bon d'expédition browser print | `render_shipment_document`, `scan_shipment_view_document`, bundle fallback paths | Yes | Prints ASF logo, MessMed contact, ASF public-utility wording, ASF customs agent, and ASF flight manager labels | High | Configure narrowly in PR15 for HTML print, except legal/trust wording may need a separate decision. |
| `templates/print/partials/customs_note_body.html` | Customs note body | `Logo ASF`; `messmed@aviation-sans-frontieres-fr.org // +33 6 50 03 72 36`; `Association reconnue d'utilité publique depuis 1993`; `RESP. DOUANE ASF / ASF Customs agent` | Hardcoded | Customs note browser print | `render_shipment_document`, `scan_shipment_view_document`, bundle fallback paths | Yes | Prints ASF logo/contact/public-utility wording and ASF customs label | High | Configure narrowly in PR15 for HTML print; keep Air France/customs wording deferred unless a legal/ops decision covers it. |
| `templates/print/partials/donation_certificate_body.html` | Donation certificate body | `Logo ASF`; `M. Edouard Gonnu`; `Responsable de la Messagerie Médicale`; `Aviation Sans Frontieres`; `Aviation Sans Frontières`; Orly address; `scan/cachet.png` stamp image with `Cachet` alt | Hardcoded | Donation certificate | `render_shipment_document`, `scan_shipment_view_document`, bundle fallback paths | Yes | Prints ASF legal/issuer identity, signatory, title, address, and stamp | High | Defer from PR15. Requires document issuer/legal/signatory decision and tests. |
| `templates/print/partials/packing_list_shipment_body.html` | Shipment packing list body | `Logo ASF` via `scan/logo.jpg`; humanitarian origin copy | Hardcoded | Shipment packing list | `render_shipment_document`, `scan_shipment_view_document`, strict planning packing-list fallback | Yes | Prints ASF logo on packing list | Medium | Configure logo narrowly with HTML issuer header if PR15 includes packing-list partials. |
| `templates/print/partials/packing_list_carton_body.html` | Carton packing list body | `Logo ASF` via `scan/logo.jpg` | Hardcoded | Carton packing list | `render_carton_document`, `scan_shipment_carton_document`, carton bundle paths | Yes | Prints ASF logo on carton packing list | Medium | Configure logo narrowly with HTML issuer header if PR15 includes carton print partials. |
| `templates/print/base_document.html` | Base print template footer | `scan/logo.jpg`; `https://aviation-sans-frontieres.org/messmed // messmed@aviation-sans-frontières-fr.org`; Orly and Roissy address lines; `Association reconnue d'utilité publique par décret du 12 novembre 1993` | Hardcoded, sometimes hidden by context | Dynamic documents, humanitarian certificate, billing/template previews, legacy document wrappers | Any template extending `base_document.html` when `hide_footer` is false | Yes | Prints ASF website/contact, addresses, and public-utility footer where footer is visible | Medium | Configure narrowly, but separate public-utility/legal statement from simple brand/logo. |
| `templates/print/base_a5.html` | Base A5 print template footer | Same ASF footer/contact/address/public-utility concept as `base_document.html` | Hardcoded, sometimes hidden by context | A5 labels or dynamic A5 documents | Templates extending `base_a5.html` | Yes | Prints ASF footer on A5 document surfaces when visible | Medium | Configure with the same document footer contract as `base_document.html`. |
| `templates/print/blocks/signatures.html` | Dynamic signature block | Default `Signature ASF` | Hardcoded default in template | Dynamic print template block output | `scan_print_template_preview`, dynamic print-template rendering | Yes if used in printed document | Falls back to ASF signature wording when labels are not supplied | Medium | Configure narrowly or require explicit labels in dynamic layouts; safe but should not be globalized. |
| `wms/print_layouts.py` | Default dynamic `shipment_note` layout | Donation/issuer paragraph naming `M. Edouard Gonnu`, `Responsable de la Messagerie Médicale`, `Aviation Sans Frontières`, and `scan/cachet.png` | Hardcoded layout text | Dynamic print-template preview or fallback layout output | `scan_print_template_preview`, `get_default_layout`, print-template editor | Potentially yes | Preview/default layout can render ASF legal/signatory content | High | Defer donation/legal/signatory defaults from PR15 unless the slice is explicitly about dynamic layout legal identity. |
| `wms/print_layouts.py` | Default dynamic document layouts | `{{ org_name }}`, `{{ org_address }}`, `{{ org_contact }}` in certificate/customs layouts | Implicit runtime-generated from settings | Dynamic print-template output | `scan_print_template_preview`, dynamic layouts | Potentially yes | Uses `ORG_*` settings where rendered | Medium | Do not reuse broad identity keys casually. Consider dedicated document issuer keys before changing `ORG_*` behavior. |
| `wms/documents.py`; `wms/print_context.py`; `templates/print/attestation_aide_humanitaire.html` | `build_org_context` and humanitarian certificate | `org_name`, `org_address`, `org_contact`, `org_signatory` from `settings.ORG_*` | Implicit runtime-generated | Humanitarian certificate / dynamic documents | `build_shipment_document_context`, `render_shipment_document` | Yes | Current deployment settings can render ASF organization/contact/signatory values | Medium | Defer or route through a dedicated document issuer contract. Do not consume `identity.organization_brand_name`. |
| `wms/print_context.py` | `build_sample_document_context` | Sample `shipper_info.company = "ASF"`, `shipper_name = "ASF"`, `donor_name = "ASF"` | Hardcoded sample/preview data | Template preview/sample document rendering | `scan_print_template_preview` when no real shipment context is used | No for production data, yes for preview output | Preview/sample documents may show ASF sample party names | Low | Defer or replace only in a print-template preview sample-data PR. |
| `data/print_templates/C__shipment_note__shipment.xlsx` | XLSX print-pack template | `Aviation Sans Frontieres - Bat. 7200...`; `messmed@aviation-sans-frontieres-fr.org`; `Association reconnue d'utilité publique depuis 1993`; `RESP. DOUANE ASF / ASF Customs agent`; `RESPONSABLE VOL ASF / ASF Flight Manager`; embedded image | Hardcoded cells and embedded image | Shipment note PDF/XLSX print pack | `generate_pack(pack_code="C")`, Graph PDF conversion, local helper/fallback XLSX | Yes | Graph-generated PDF and fallback XLSX carry ASF issuer/contact/customs/flight identity | High | Defer from PR15 or split into a binary-template PR with workbook tests and visual review. |
| `data/print_templates/C__customs_note__shipment.xlsx` | XLSX print-pack template | Same issuer/contact/public-utility concept; `RESP. DOUANE ASF / ASF Customs agent`; embedded image | Hardcoded cells and embedded image | Customs note PDF/XLSX print pack | `generate_pack(pack_code="C")`, Graph PDF conversion, local helper/fallback XLSX | Yes | Graph-generated PDF and fallback XLSX carry ASF issuer/contact/customs identity | High | Defer from PR15 or split into a binary-template PR with workbook tests and visual review. |
| `data/print_templates/B__donation_certificate__shipment.xlsx` | XLSX print-pack template | `Aviation Sans Frontieres`; body phrase `d'Aviation Sans Frontières`; embedded images; workbook metadata | Hardcoded cells, embedded images, implicit metadata | Donation certificate PDF/XLSX print pack | `generate_pack(pack_code="B")`, Graph PDF conversion, local helper/fallback XLSX | Yes | Graph-generated donation certificate carries ASF issuer/legal wording and likely stamp/logo assets | High | Defer to legal/signatory/template PR. |
| `data/print_templates/B__packing_list_shipment__shipment.xlsx` | XLSX print-pack template | Embedded image, no visible text hit for ASF strings | Implicit image asset | Shipment packing-list PDF/XLSX print pack | `generate_pack(pack_code="B", variant="shipment")`, strict planning packing-list PDF | Yes | Likely ASF logo/image appears although text search has no ASF string | Medium | Inspect and handle in binary-template PR. |
| `data/print_templates/B__packing_list_carton__per_carton_single.xlsx` | XLSX print-pack template | Embedded image, no visible text hit for ASF strings | Implicit image asset | Carton packing-list PDF/XLSX print pack | `generate_pack(pack_code="B")` carton path | Yes | Likely ASF logo/image appears although text search has no ASF string | Medium | Inspect and handle in binary-template PR. |
| `data/print_templates/A__picking__single_carton.xlsx` | XLSX print-pack template | Embedded image, no visible text hit for ASF strings; `EXPEDITION N°` is operational vocabulary | Implicit image asset | Picking PDF/XLSX print pack | `generate_pack(pack_code="A")` | Yes | May include identity-bearing image; text search did not confirm | Medium | Ambiguous. Inspect visually before using as PR15 evidence. |
| `data/print_templates/*.xlsx` | Workbook document properties | Creator and modifier metadata such as `Edouard Gonnu`; no title/subject ASF metadata found | Implicit metadata | Source XLSX fallback/helper documents; metadata may propagate to Graph PDF | Graph/local helper/fallback XLSX | Yes | XLSX files carry personal creator/modifier metadata | Medium | Defer to binary-template metadata cleanup. Do not conflate with visible branding. |
| `data/planning_templates/Planning-maquette.xlsx` | Planning workbook template | No visible ASF-term hits; metadata `creator='Perso'`, `lastModifiedBy='Edouard Gonnu'` | Implicit metadata | Planning workbook/PDF | `export_planning_version_workbook`, `convert_workbook_to_pdf`, planning communication downloads | Yes | Visible planning template text does not expose ASF identity, but metadata names a creator/modifier | Low | Keep for PR15; consider metadata cleanup later if planning document hygiene is addressed. |
| `wms/print_pack_engine.py` | Artifact generation | Filenames like `print-pack-{pack_code}-{timestamp}.pdf` and per-document `{pack.code}-{document.doc_type}-{document.id}.xlsx/pdf` | Implicit generated filename | Generated print-pack downloads/artifacts | `generate_pack`, `render_pack_xlsx_documents` | Yes | No ASF token by itself; pack code and shipment/carton data may be visible | Low | Keep. |
| `wms/artifacts/proofs.py`; `wms/print_pack_sync.py` | Artifact filename and OneDrive path | `print-pack-{artifact.pack_code}-{artifact.id}.pdf`; paths under `shipments/{shipment.reference}`, `cartons/{carton.code}`, `packs/{pack_code}` | Implicit generated filename/path | Downloaded and synchronized print artifacts | `process_print_artifact_queue`, `upload_print_artifact_to_onedrive` | Yes | No ASF token by itself; shipment/carton references are operational data | Low | Keep. |
| `wms/local_document_helper.py` | Helper output filename | `print-pack-{pack_code}-{carton.code}.pdf`, `print-pack-{pack_code}-{shipment.reference}.pdf`, `print-pack-{pack_code}.pdf` | Implicit generated filename | Local helper PDF output | Local helper job response | Yes | No ASF token by itself | Low | Keep. |
| `wms/planning/exports.py`; `wms/views_planning.py` | Planning artifact filenames | `planning-run-{run_id}-v{version.number}.xlsx/pdf`, fallback `planning-v{version.number}.pdf`, `packing-list-{shipment_reference}.pdf` | Implicit generated filename | Planning workbook/PDF and strict packing-list PDF | Planning communication download routes | Yes | No ASF token by itself | Low | Keep. |
| `wms/models_domain/shipment.py` | Shipment QR generation | QR filename `qr_shipment_{shipment.reference}.png`; payload is tracking URL | Implicit runtime-generated | Shipment QR/label image | Shipment QR generation and label print contexts | Yes | Encodes deployment URL/reference, not an ASF label unless configured URL or reference contains one | Low | Keep for PR15. |
| `wms/models_domain/catalog.py` | Product QR generation | QR filename `qr_{self.sku}.png`; payload is product SKU | Implicit runtime-generated | Product QR labels | Product QR label print routes | Yes | Existing SKU defaults can include the ASF prefix, now owned by `identity.sku_prefix` from earlier work | Medium | Keep. Do not touch SKU prefix in PR15. |
| `wms/tests/views/tests_print_strict_fidelity.py` | Visible-output assertions | Assertions for `RESPONSABLE VOL ASF`, `ASF Flight Manager`, `RESP. DOUANE ASF`, `ASF Customs agent`, and MessMed contact line | Test-only assertion of visible document output | Tests for shipment/customs print fidelity | Test suite only | No | Pins current ASF print output | Medium | Update only in the implementation PR that changes these HTML surfaces. |
| `wms/tests/print/tests_print_pack_engine.py` and related print-pack tests | Test fixture payloads | Fixture party/product values like `ASF` or product `brand` in test data | Test-only fixture data | Test pack rendering/mapping | Test suite only | No | Test data may include ASF as a party/product value | Low | Do not use as PR15 driver unless an assertion pins visible identity. |

Focused search found no in-scope `Contact.asf_id`, `id_asf`, `ASF ID`, or `ID ASF` labels in print/PDF templates or print/PDF generation code. The contact identifier work from PR13a/PR13b should remain untouched.

## 3. Implicit Identity Surfaces

### PDF / Document Metadata

No application code was found writing PDF `title`, `author`, `producer`, `subject`, or `creator` metadata through `pypdf` or another PDF library. The app merges PDF bytes with `pypdf` but does not add metadata.

Implicit metadata still exists at the source-document layer:

- `data/print_templates/*.xlsx` workbooks have `creator='Edouard Gonnu'` and `lastModifiedBy='Edouard Gonnu'`.
- `data/planning_templates/Planning-maquette.xlsx` has `creator='Perso'` and `lastModifiedBy='Edouard Gonnu'`.
- Microsoft Graph and desktop Excel conversion may inject producer/creator metadata during XLSX-to-PDF conversion. The repo does not currently set or scrub those values.

Risk: medium for print-pack workbooks because fallback XLSX files can leave the app and Graph PDFs may inherit or transform metadata. Low for planning visible branding because no visible ASF strings were found in the planning template.

### Generated Filenames and Paths

Generated filenames and paths do not hardcode `ASF` or `ASF WMS`, but some include operational references that may themselves contain configured prefixes or deployment-specific tokens:

- `print-pack-{pack_code}-{timestamp}.pdf`
- `{pack.code}-{document.doc_type}-{document.id}.xlsx/pdf`
- `print-pack-{artifact.pack_code}-{artifact.id}.pdf`
- `shipments/{shipment.reference}`, `cartons/{carton.code}`, `packs/{pack_code}`
- `print-pack-{pack_code}-{shipment.reference}.pdf`
- `planning-run-{run_id}-v{version.number}.xlsx/pdf`
- `planning-v{version.number}.pdf`
- `packing-list-{shipment_reference}.pdf`
- `qr_shipment_{shipment.reference}.png`
- `qr_{product.sku}.png`

These are implicit identity surfaces only when the referenced data carries identity. Product SKU is the main one to watch because the default SKU prefix was historically `ASF-`, but that is already owned by `identity.sku_prefix`.

### Headers, Footers, and Library Defaults

The app does not rely on WeasyPrint, ReportLab, wkhtmltopdf, xhtml2pdf, or pdfkit default headers/footers. Browser print headers/footers are controlled by the user's browser and are outside the repo.

Repo-owned headers/footers are in templates and XLSX assets:

- `templates/print/base_document.html` and `templates/print/base_a5.html` inject ASF footer identity when `hide_footer` is false.
- Shipment/customs/donation/packing partials embed `scan/logo.jpg` directly.
- XLSX print templates carry embedded images that are not text-searchable and should be treated as potential identity-bearing assets.

### Runtime Context Values

`build_org_context()` reconstructs document issuer identity from `settings.ORG_NAME`, `ORG_ADDRESS`, `ORG_CONTACT`, and `ORG_SIGNATORY`. Those values are not installation-config consumers today and should not be silently replaced with broad identity keys.

Shipment/carton documents also render party snapshots and model data. If a shipper, recipient, correspondent, donor, product brand, SKU, or shipment reference contains `ASF`, that is operational data rather than a document-brand default. These values are in scope for truthfulness, but they are not candidates for generic white-label substitution.

### Django Labels and Verbose Names

No in-scope print/PDF output was found rendering Django's auto-generated `Contact.asf_id` label or verbose name. Import/export column names and admin/form labels are out of this audit's document boundary.

## 4. Classification

| Category | Findings | Default action |
|---|---|---|
| Simple visible brand label | `Logo ASF`, `scan/logo.jpg` in print partials and base templates | Configure narrowly for document print surfaces. |
| Document issuer / organization identity | MessMed contact line, ASF addresses, `Aviation Sans Frontieres`, `Aviation Sans Frontières`, `ORG_*` context values | Configure through dedicated document issuer keys only after deciding exact issuer semantics. |
| Operational reference label | `RESP. DOUANE ASF`, `ASF Customs agent`, `RESPONSABLE VOL ASF`, `ASF Flight Manager` | Configure narrowly for print documents if non-ASF installations need equivalent role labels. |
| Legal / trust wording | `Association reconnue d'utilité publique...`, donation certificate wording, stamp/signatory context | Defer or handle in a legal/issuer PR. Do not treat as generic branding. |
| Persisted or imported identifier | Product SKU in QR labels, shipment/carton references in filenames and QR payloads | Keep. Do not alter stored/reference values in this work. |
| Integration / technical namespace | Microsoft Graph provider config, helper capability names, print pack code names | Keep unless visible output proves otherwise. |
| PDF/document metadata | Workbook creator/modifier metadata, possible Graph/Excel PDF producer metadata | Defer to binary-template/document-hygiene PR. |
| Generated filename | `print-pack-*`, `planning-run-*`, `packing-list-*`, `qr_*` | Keep unless a configured reference prefix leaks identity unintentionally. |
| Test-only assertion | `tests_print_strict_fidelity` assertions pin current ASF HTML output | Update only alongside implementation; do not loosen during audit. |
| Internal code name not visible to users | Print-pack route/function names, `CommunicationFamily.EMAIL_ASF`, API headers/User-Agent namespaces | Out of PR15 and mostly out of this audit. |

## 5. Boundary Analysis

Truly in-scope document/print/PDF outputs:

- `templates/print/*` rendered as printable HTML or browser-saved PDF.
- `data/print_templates/*.xlsx` rendered to Graph/local-helper PDF or returned as XLSX fallback/helper input.
- Generated print artifacts saved in Django storage or uploaded to OneDrive.
- Local helper job payloads that instruct a helper to render PDF/XLSX documents.
- Planning workbook/PDF downloads and strict packing-list PDFs.
- Product/shipment QR labels and label sheets intended for printing.
- Tests that assert visible print/PDF document output.

Adjacent but out of scope for PR15:

- Ordinary scan/admin/portal UI labels, table headers, filters, CRUD forms, and dashboards.
- Email subjects/bodies, including `CommunicationFamily.EMAIL_ASF` and `email_asf`.
- API headers, User-Agent values, and integration namespace strings.
- Contact identifier labels and `Contact.asf_id` persistence/import/export columns.
- `ASF-ORG-ROOT`, default shipper lookup, default shipper display names, and public-order shipper setup.
- PWA manifest, scan shell branding, legal/footer/trust-page implementation, and gettext catalogs.
- Product `brand` field values, unless they are defaulted by system code into a printed document.

### Ambiguous Matches

| Match / surface | Why ambiguous | Recommended handling |
|---|---|---|
| Billing dynamic layouts in `wms/print_layouts.py` and billing context in `wms/print_context.py` | The dynamic print template system supports billing-like layouts, but the inspected portal billing views are normal UI, not confirmed generated PDF/download routes. | Do not drive PR15 from billing until a confirmed print/export route is identified. |
| `wms/print_context.py` sample `ASF` values | They are preview/sample data, not persisted production document data. They can still appear in template previews. | Defer to a preview sample-data cleanup after core document identity. |
| Embedded XLSX images | Text search cannot prove whether each image is a logo/stamp. Several print-pack templates include embedded images in document header/signature contexts. | Inspect visually in the binary-template PR before changing assets. |
| Planning communication email subjects such as `email_asf` | Planning PDFs can be attached to communications, but these strings are email identity, not PDF/print identity. The user explicitly excluded `email_asf`. | Keep out of PR15. |
| Product `brand` mappings in print pack context | `brand` is product metadata and may legitimately be a user/product value. | Keep unless a system default injects ASF as product brand. |
| `docs/templates/*.html` and historical docs/audits | Some documents mention print contracts or older examples, but they are not runtime output templates. | Use only as background, not implementation scope. |
| Air France wording in customs note templates | It is in printed customs/output documents but is a partner/ops/legal statement, not an ASF identity string. | Defer to a later operational/legal copy audit, not PR15. |

## 6. Configuration Proposal, No Implementation

These are candidate keys only. No keys were added in this audit.

| Proposed key | Exact ASF default | Intended consumers | Forbidden consumers | Existing-key reuse decision |
|---|---|---|---|---|
| `installation.documents.issuer_logo_static_path` | `scan/logo.jpg` | `templates/print/base_document.html`, `templates/print/base_a5.html`, shipment/customs/packing/donation print partials, future XLSX template build pipeline | Shell logos, PWA icons, email logos, API headers, scan branding outside print | Do not reuse `identity.organization_brand_name` or `product_display_name`; this is an asset path for generated documents. |
| `installation.documents.issuer_contact_line` | `messmed@aviation-sans-frontieres-fr.org // +33 6 50 03 72 36` | Shipment/customs print headers and document footer contact line | Notification sender/reply-to, support email routing, Brevo sender name | Do not reuse `identity.contact_email`; the current document line includes phone and is not an email routing address. |
| `installation.documents.issuer_primary_address` | `Bat. 7200, Rue de la remise - 95700 Roissy En France` | Shipment/customs headers and document footer where this exact address currently appears | Default shipper address, legal pages, account request forms | Do not reuse `identity.organization_full_name`; address semantics are separate. |
| `installation.documents.issuer_registered_address` | `Orly Fret 768 - 94398 Orly Aérogare Cedex` | Footer and donation certificate only where this exact Orly address appears | Default shipper, portal account profile, shell masthead | Needs a document-issuer namespace because ASF currently has multiple address contexts. |
| `installation.documents.public_utility_statement_short` | `Association reconnue d'utilité publique depuis 1993` | Shipment/customs headers that currently show the short statement | Generic legal page, trust center, UI footer outside generated documents | Do not reuse broad legal identity without legal review. |
| `installation.documents.public_utility_statement_decree` | `Association reconnue d'utilité publique par décret du 12 novembre 1993` | `base_document.html` and `base_a5.html` footer only | PWA/legal/trust pages, shell footer | Separate from short statement because current ASF text differs by surface. |
| `installation.documents.customs_agent_label_fr` | `RESP. DOUANE ASF` | Shipment/customs print documents | Contact identifier labels, scan status labels, admin forms | Do not reuse `references.contact_identifier_label`; this is a document role label. |
| `installation.documents.customs_agent_label_en` | `ASF Customs agent` | Shipment/customs print documents | Email, tracking, API, model metadata | Same as above. |
| `installation.documents.flight_manager_label_fr` | `RESPONSABLE VOL ASF` | Shipment note print document | Planning provider labels, flight import defaults, UI status | Not safe to reuse planning identity; this is a printed signature role. |
| `installation.documents.flight_manager_label_en` | `ASF Flight Manager` | Shipment note print document | Planning provider labels, flight import defaults, UI status | Same as above. |
| `installation.documents.donation_signatory_name` | `M. Edouard Gonnu` | Donation certificate only | Admin user display, sender name, shell identity | Defer until donation/legal PR. |
| `installation.documents.donation_signatory_title` | `Responsable de la Messagerie Médicale` | Donation certificate only | Shell masthead, user roles, planning roles | Defer until donation/legal PR. |
| `installation.documents.donation_issuer_name` | `Aviation Sans Frontieres` | Donation certificate row that currently uses the unaccented legal name | Default shipper, public-order shipper, shell brand, portal copy | Do not reuse `identity.organization_brand_name`; `identity.organization_full_name` overlaps but should not be consumed without a dedicated document-issuer decision. |
| `installation.documents.donation_issuer_body_name` | `Aviation Sans Frontières` | Donation certificate body phrase that currently uses the accented name | Default shipper, shell brand, email sender | Keep separate if exact ASF output must preserve accent differences. |
| `installation.documents.stamp_static_path` | `scan/cachet.png` | Donation certificate and dynamic signature/stamp output | UI icons, logos, non-document assets | Defer until donation/legal PR. |

Why not reuse existing keys:

- `identity.organization_brand_name` is not safe for legal/issuer strings, `Aviation Sans Frontières`, or `Aviation Sans Frontières France`.
- `identity.product_display_name` is a product/shell label and is not a document issuer.
- `identity.organization_full_name` has a tempting default (`Aviation Sans Frontieres`) but would be unsafe as a broad replacement because current print surfaces use multiple legal, brand, branch, address, and accented/unaccented forms.
- `identity.contact_email` is insufficient for the document contact line because the current string includes phone and is not the same as email sender/reply-to routing.
- `references.contact_identifier_label`, `references.tracking_contact_identifier_label`, and `references.contact_identifier_generated_prefix` are unrelated to document issuer identity.
- `identity.sku_prefix` already owns SKU generation and should not be pulled into print identity except as operational data rendered on product labels.

## 7. Suggested PR15 Implementation Slice

Recommended PR15: **HTML print issuer header/footer and print role labels only**.

Proposed files to touch:

- `wms/config/installation.py`: add a narrow `documents` config namespace with only the fields needed by the HTML print slice.
- `wms/documents.py` or a new small document-identity helper: expose document issuer context without broad identity coupling.
- `wms/print_context.py`: pass document issuer context to relevant HTML print templates.
- `templates/print/partials/shipment_note_body.html`
- `templates/print/partials/customs_note_body.html`
- `templates/print/partials/packing_list_shipment_body.html`
- `templates/print/partials/packing_list_carton_body.html`
- `templates/print/base_document.html`
- `templates/print/base_a5.html`
- `templates/print/blocks/signatures.html` only if the PR includes the `Signature ASF` default.
- Tests near the existing behavior, especially `wms/tests/views/tests_print_strict_fidelity.py` and config/default/override tests under `wms/tests/config/`.

Proposed tests:

- Config defaults preserve exact current ASF strings.
- Config overrides render in shipment note HTML without changing shipment data.
- Config overrides render in customs note HTML without changing customs/shipment data.
- Packing-list HTML uses the configured document logo path while default remains `scan/logo.jpg`.
- Existing strict fidelity assertions are converted to default-value assertions and extended with an override case.
- No test should alter `Contact.asf_id`, import/export columns, default shipper, email, API headers, PWA, or XLSX templates.

Explicit exclusions:

- No edits to `data/print_templates/*.xlsx`.
- No Microsoft Graph conversion changes.
- No PDF metadata cleanup.
- No donation certificate signatory/legal/stamp changes.
- No `ORG_*` setting migration unless explicitly scoped.
- No broad search/replace.
- No Contact `asf_id`, `ASF ID`, `ID ASF`, `ASF-C`, `ASF-ORG-ROOT`, default shipper, email, API, PWA, scan branding, gettext, legal/footer/trust-page, or import/export changes.

Rollback risk: low for the HTML-only slice if defaults are exact and tests assert both default and override behavior. Operational risk becomes medium if legal/trust wording is included without a decision. XLSX/Graph output will still carry ASF identity after PR15, so first-client readiness remains incomplete until the binary-template slice lands.

## 8. Evidence Appendix

Representative discovery commands:

```bash
rg -n -i "weasyprint|reportlab|wkhtmltopdf|xhtml2pdf|pdfkit|pypdf|openpyxl|pillow|microsoft graph|graph|convert_excel|content\\?format=pdf|qrcode" pyproject.toml requirements.txt asf_wms/settings.py wms tools docs/repo-reference
```

```bash
rg -n -i "Logo ASF|Aviation Sans Fronti|RESP\\.|ASF Customs|ASF Flight|messmed@|utilité publique|Signature ASF|Cachet" templates/print wms/print_layouts.py wms/print_context.py wms/documents.py
```

```bash
rg -n -i "asf_id|id_asf|ASF ID|ID ASF" templates/print wms/views_print_docs.py wms/views_print_labels.py wms/views_print_templates.py wms/print_context.py wms/documents.py wms/print_layouts.py wms/product_label_printing.py data/print_templates tools/planning_comm_helper wms/planning wms/artifacts
```

```bash
rg -n "scan_shipment.*document|print_bundle|view_bundle|labels|product-labels|template|documents|communication.*pdf|packing-list.*pdf" wms/scan_urls.py wms/planning_urls.py api/v1/urls.py asf_wms/urls.py
```

```bash
rg -n "SHIPMENT_DOCUMENT_TEMPLATES|render_shipment_document|render_carton_document|SHIPMENT_VIEW_DOCUMENT_CONFIG|_build_inline_pdf_response|_build_pdf_response_from_xlsx_documents|generate_pack|render_pack_xlsx_documents|convert_excel_to_pdf_via_graph|merge_pdf_documents|impose_two_up_pdf_on_a4|build_local_helper" wms/views_print_docs.py wms/shipment_view_helpers.py wms/print_pack_engine.py wms/print_pack_pdf.py wms/local_document_helper.py
```

```bash
rg -n "planning_version_communication_workbook|planning_version_communication_pdf|planning_version_communication_packing_list_pdf|_build_workbook_file_response|_build_planning_pdf_file_response|_build_strict_packing_list_pdf_response|convert_workbook_to_pdf|export_planning_version_workbook" wms/views_planning.py wms/artifacts/planning.py wms/planning/exports.py tools/planning_comm_helper/excel_pdf.py tools/planning_comm_helper/planning_pdf.py
```

Structured workbook inspection was done with `openpyxl` because string grep cannot inspect XLSX cells/properties reliably. Relevant results:

- `data/print_templates/B__donation_certificate__shipment.xlsx`
  - `attestation donation!C11`: `Aviation Sans Frontieres`
  - `attestation donation!B15`: `d’Aviation Sans Frontières ...`
  - Embedded images: 2
- `data/print_templates/C__customs_note__shipment.xlsx`
  - `Feuil1!B2`: `Aviation Sans Frontieres - Bat. 7200...`, MessMed email/phone, public-utility statement
  - `Feuil1!C15`: `RESP. DOUANE ASF / ASF Customs agent`
  - Embedded images: 1
- `data/print_templates/C__shipment_note__shipment.xlsx`
  - `Feuil1!B2`: same issuer/contact block as customs note
  - `Feuil1!C15`: `RESP. DOUANE ASF / ASF Customs agent`
  - `Feuil1!A38`: `RESPONSABLE VOL ASF / ASF Flight Manager`
  - Embedded images: 1
- `data/print_templates/B__packing_list_shipment__shipment.xlsx`
  - No visible ASF-string cell hit
  - Embedded images: 1
- `data/print_templates/B__packing_list_carton__per_carton_single.xlsx`
  - No visible ASF-string cell hit
  - Embedded images: 1
- `data/print_templates/A__picking__single_carton.xlsx`
  - No visible ASF-string cell hit
  - Embedded images: 1
- `data/planning_templates/Planning-maquette.xlsx`
  - No visible search-term cell hit
  - No embedded images
  - Metadata: `creator='Perso'`, `lastModifiedBy='Edouard Gonnu'`

Representative path evidence:

- `templates/print/partials/shipment_note_body.html:5` embeds `scan/logo.jpg` with alt `Logo ASF`.
- `templates/print/partials/shipment_note_body.html:8-9` prints MessMed contact and ASF public-utility wording.
- `templates/print/partials/shipment_note_body.html:74` prints `RESP. DOUANE ASF / ASF Customs agent`.
- `templates/print/partials/shipment_note_body.html:122` prints `RESPONSABLE VOL ASF / ASF Flight Manager`.
- `templates/print/partials/customs_note_body.html:5,8,9,74` carries the same logo/contact/public-utility/customs identity pattern.
- `templates/print/partials/donation_certificate_body.html:5,16,20,41` carries logo, issuer name, body issuer phrase, and stamp image.
- `templates/print/base_document.html:79-82` and `templates/print/base_a5.html:79-82` carry ASF website/contact/address/public-utility footer strings.
- `templates/print/blocks/signatures.html:4` defaults to `Signature ASF`.
- `wms/print_layouts.py:53-56` embeds dynamic donation/signatory/stamp wording with `Aviation Sans Frontières`.
- `wms/documents.py:8-13` builds document org context from `settings.ORG_*`.
- `wms/print_context.py:238-366` builds shipment document context and sets `hide_footer` for several current document types.
- `wms/print_context.py:479-578` builds preview/sample document context, including sample `ASF` party values.
- `wms/print_pack_graph.py:129` downloads Microsoft Graph `/content?format=pdf`.
- `wms/print_pack_engine.py:617-748` renders XLSX documents, converts each to PDF, and produces generated print artifacts.
- `wms/print_pack_pdf.py:25-45` merges/imposes PDF bytes with `pypdf`.
- `wms/local_document_helper.py:29-61` builds helper job/document responses.
- `wms/views_print_docs.py:277-300` builds inline PDF responses from XLSX documents.
- `wms/views_print_labels.py:137-245` handles shipment label print/PDF/helper paths.
- `wms/product_label_printing.py:24-87` renders product label and QR label print responses.
- `wms/planning/exports.py:142` builds planning workbook/PDF basenames.
- `wms/views_planning.py:221-263` returns planning workbook/PDF and strict packing-list PDF files.
- `wms/models_domain/shipment.py:179` writes `qr_shipment_{self.reference}.png`.
- `wms/models_domain/catalog.py:157` writes `qr_{self.sku}.png`.

Validation note: no full test suite was run because this audit changed no runtime code.
