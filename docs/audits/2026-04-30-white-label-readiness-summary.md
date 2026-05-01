# White-Label Readiness Summary - 2026-04-30

Readiness score: **2/5**.

## Top 5 quick wins

1. Define a read-only installation configuration contract for identity, vocabulary, feature flags, and integrations.
2. Add tests that lock current ASF defaults before changing labels, email subjects, or document identity.
3. Move low-risk branding such as home page title/header and email subject prefix behind config, preserving ASF defaults.
4. Document a single-tenant pilot deployment checklist with generic env templates and integration capability requirements.
5. Add print-document fixture tests before touching donation, customs, shipment note, or packing-list text.

## Top 3 blockers

1. Core data/configuration has no tenant or installation boundary: `WmsRuntimeSettings` is singleton, core operational tables are global, and integration keys are global.
2. ASF identity and legal/logistics copy are embedded in high-trust surfaces: print documents, account emails, home branding, deployment templates, and default shipper binding.
3. Portal and billing still expose "Association" as a model/vocabulary contract, even though newer shipper/recipient scopes are more reusable.

## Recommended next 3 PRs

1. **Installation config foundation**: settings-backed identity/vocabulary/feature-flag resolver plus tests proving unchanged ASF defaults.
2. **Low-risk branding externalization**: home/shell labels and email subject prefix use installation config, with no print-document or workflow changes.
3. **Print identity safety net**: add fixture/snapshot tests for shipment note, customs note, donation certificate, packing list, and labels; then prepare a follow-up PR to externalize document identity.

## Recommended multi-tenancy path

Use **single-tenant per client deployment** for the next 6-12 months.

Do not introduce shared-DB `organization_id` tenancy now. Do not add an early tenant-scoping `Organization` model; use an installation configuration abstraction first. Reconsider shared tenancy only if pilots grow beyond a small number, need centralized cross-client operations, or require stronger shared-platform economics.
