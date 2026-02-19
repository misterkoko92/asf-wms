# Documentation Index

Use this index as the entry point for project documentation.

Last functional alignment update: **February 19, 2026**.

## Product and scope

- `docs/mvp_spec.md`: current functional scope and business rules (cartons, shipments, tracking, disputes, draft flow).
- `docs/audit_2026-02-19.md`: global repository audit (quality, security, flows, risks, phased improvement plan, V2 options).
- `docs/backlog.md`: roadmap with delivered baseline and next priorities.
- `docs/phases_0_3_recap.md`: consolidated summary of delivered phases 0, 1, 2 and 3.

## Operations

- `docs/operations.md`: operations runbook, deployment flow, incident playbooks, and lifecycle rules.
- `docs/release_checklist.md`: release checklist used for production deployments.

## User-facing reference

- `templates/scan/faq.html`: in-app FAQ and workflow documentation for scan users.

## Data and templates

- `docs/import/products_template.csv`: import template for products.
- `docs/import/sample_products.csv`: sample product data.
- `docs/templates/`: printable template references.

## Repository layout (high-level)

- `asf_wms/`: Django project settings and root URLs.
- `wms/`: main domain app (stock, cartons, shipments, tracking).
- `api/`: API endpoints.
- `contacts/`: contact model, tagging, scoping rules for shipment workflows.
- `wms/tests/`, `api/tests/`, `contacts/tests/`: tests grouped by app.
