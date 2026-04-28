# Documentation Index

Use this index as the entry point for project documentation.

Last full repo audit update: **April 22, 2026**.

## Product and scope

- `docs/mvp_spec.md`: current functional scope and business rules (cartons, shipments, tracking, disputes, draft flow).
- `docs/audit_2026-04-22_full_repo.md`: latest full repository audit.
- `docs/audit_2026-02-19.md`: historical global repository audit (quality, security, flows, risks, phased improvement plan, V2 options).
- `docs/backlog.md`: roadmap with delivered baseline and next priorities.
- `docs/deferred-follow-ups.md`: explicit follow-ups intentionally deferred during active implementation or product decisions.
- `docs/phases_0_3_recap.md`: consolidated summary of delivered phases 0, 1, 2 and 3.

## Agent guidance

- `docs/agent/prompts.md`: prompt runtime and standard workflow for agents.
- `docs/agent/playbooks.md`: task-specific execution playbooks for agents.

## Repository reference

- `docs/repo-reference/README.md`: canonical maintenance entry point for repo architecture, key flows, propagation checks, and shared contracts.
- `docs/repo-reference/01-architecture-and-entrypoints.md`: routing map, runtime layering, and first files to open by change type.
- `docs/repo-reference/02-key-flows-and-living-tests.md`: critical E2E or partial flows plus their living reference tests.
- `docs/repo-reference/03-impact-map.md`: propagation checklist for recurring maintenance changes.
- `docs/repo-reference/04-shared-contracts.md`: shared cross-screen and cross-surface contracts that must stay aligned.

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
