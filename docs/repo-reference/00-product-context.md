# Product Context (asf-wms)

Read this file first before any significant intervention.

This document explains **why the system exists**, **who depends on it**, **what production reality looks like**, and **which constraints matter more than technical elegance**.

The other files in `docs/repo-reference/` explain mainly the technical *how*.
This file explains the operational *why*.

> Last updated: 2026-04-27

---

# 1. Mission

ASF-WMS supports the humanitarian logistics activity of **Aviation Sans Frontières (ASF)**, primarily for the **Messagerie Médicale** branch.

Core mission:

- receive
- prepare
- consolidate
- track
- document
- ship

humanitarian parcels internationally, mainly medical.

This is not a generic e-commerce system.
This is an operational tool supporting real aid flows with real downstream consequences.

---

# 2. Real-World Activity

## Main shipment content

Approximate mix:

- ~90% medical equipment / consumables
- ~10% may involve medicines or sensitive healthcare items

Examples:

- hospital consumables
- diagnostic devices
- mobility equipment
- medical kits
- humanitarian supplies
- occasional regulated products

## Two operating models

### A. ASF own shipments

ASF sends aid under its own operations.

### B. Shared platform for partner associations

Other NGOs / associations use the platform to organize their own shipments through the ASF logistics network.

This means the system serves both:

- internal operators
- external partner organizations

---

# 3. End Users

## Internal users

### Warehouse / operations staff

Use `/scan/`

Need:

- speed
- reliability
- dense workflows
- minimal clicks
- operational clarity

### Planning / coordination users

Use `/planning/`

Need:

- shipment readiness truth
- allocation visibility
- exports
- communication support

### Volunteers

Use `/benevole/`

Need:

- simple flows
- availability input
- task clarity

---

## External users

### Partner associations

Use `/portal/`

Need:

- create requests
- manage recipients
- submit orders
- understand shipment status
- trust data accuracy

### Recipients / contacts abroad

May interact through shipment communication flows.

---

# 4. Production Reality

## Current live environment

Production URL:

`https://messmed.pythonanywhere.com/`

## Hosting

PythonAnywhere free-tier style constraints currently matter.

Practical limitations include:

- single web process
- no dedicated worker infrastructure
- constrained CPU
- constrained disk
- simple filesystem media storage
- scheduled tasks instead of robust background architecture

## Database

MySQL (hosted environment).

Assume modest scale infrastructure, not enterprise-grade elastic capacity.

## Deployment model

No true staging environment.

Changes generally reach production after CI + manual deployment workflow.

That means regressions are more expensive than in modern multi-env pipelines.

---

# 5. What Makes This System Special

## It is operational software

If a normal SaaS page fails, users get annoyed.

If this system fails, consequences may include:

- shipment delays
- customs friction
- missing documents
- stock confusion
- partner dissatisfaction
- lost volunteer time
- aid arriving late

## It mixes many domains

This repo combines:

- logistics
- warehousing
- planning
- document generation
- partner portal
- volunteer coordination
- notifications
- regulatory exports
- legacy Django monolith constraints

---

# 6. High-Value Invariants

Protect these unless explicitly redesigning them.

## Operational speed

Warehouse users repeat actions all day.

Never add friction casually.

## Data truth

Stock, cartons, shipments, references, statuses must remain coherent.

## Shipment readiness truth

A shipment must not appear ready when it is not physically ready.

## Traceability

Important actions should remain understandable after the fact.

## External trust

Portal users must see correct and comprehensible information.

## Print truth

Documents must match real shipment data.

---

# 7. Regulatory / Risk Context

Depending on shipment type or destination:

- French export customs requirements
- destination-country import constraints
- personal data / GDPR expectations
- possible pharmaceutical sensitivity
- address / identity accuracy needs

Never trivialize data integrity in these areas.

---

# 8. Product Philosophy

This system was built pragmatically around real operations.

Expect:

- legacy patterns
- mixed architecture generations
- useful shortcuts
- dense UI choices optimized for operators
- code that reflects history

Do not confuse “not modern” with “wrong”.

Many strange-looking choices may encode operational learning.

---

# 9. Change Philosophy

Prefer:

- safe incremental improvements
- clearer contracts
- better tests
- extraction of reusable logic
- operational UX wins
- performance wins on constrained infra

Avoid:

- vanity rewrites
- fashionable architecture migrations without payoff
- breaking stable operator habits casually
- adding infrastructure assumptions production cannot support

---

# 10. What An Agent Must Never Break

Never casually break:

- shipment creation/edit flows
- stock updates
- carton packing logic
- planning eligibility
- print labels / customs docs
- portal permissions
- recipient / contact integrity
- email routing
- operational navigation speed

---

# 11. Priority Order For Decisions

When tradeoffs exist, usually prefer:

1. Correct operational outcome
2. Data integrity
3. Reliability in production
4. Speed for frequent users
5. Maintainability
6. Elegance

Not the reverse.

---

# 12. Before Large Changes

Always ask:

- Who uses this flow in real life?
- How often?
- What happens if wrong for one day?
- Is there an existing hidden contract?
- Is production infra able to support the new design?
- Is this solving a real pain or only a code smell?

---

# 13. Relationship With Other Repo Docs

After reading this file, continue with:

1. `01-architecture-and-entrypoints.md`
2. `02-key-flows-and-living-tests.md`
3. `03-impact-map.md`
4. `04-shared-contracts.md`

This file gives context.
Those files guide execution.

---

# 14. Final Rule

This software exists to move humanitarian aid efficiently and safely.

Every technical decision should remain aligned with that purpose.
