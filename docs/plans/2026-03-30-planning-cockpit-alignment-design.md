# Planning Cockpit Alignment Design

**Date:** 2026-03-30

## Goal

Reduce the operator cognitive load on the legacy Django planning pages while preserving the dedicated planning domain.

The target is not to merge planning business logic into `scan`. The target is to make planning feel like a first-class `scan` cockpit:
- same shell and navigation language
- clearer action hierarchy
- much lower density on the main version page
- dedicated planning lifecycle kept intact

## Context

The current planning surface already lives under:
- `wms/planning_urls.py`
- `wms/views_planning.py`
- `templates/planning/*`
- `wms/planning/*`

This surface has a valid domain boundary:
- planning runs
- planning versions
- publication lifecycle
- version diff
- artifacts and exports
- communication drafts tied to a version

That boundary was explicitly chosen during the planning module integration:
- planning should be absorbed into `asf-wms`
- but it remains a dedicated business module with its own run/version lifecycle
- Excel stays a transition artifact, not the core UI

Recent `scan` work introduced a clearer cockpit pattern on legacy Django pages:
- a stronger page header
- compact action groups
- visible priorities before detailed data
- section anchors
- fewer giant undifferentiated tables

The planning pages lag behind that pattern.

## Validated Direction

Validated during discussion:
- the main problem is density, especially on the planning version page
- the operator gets lost in the amount of information shown at once
- a full technical merge of planning into `scan` is not the preferred answer
- keeping planning dedicated at the domain level still makes sense
- the right move is to align the planning surface on the newer `scan` cockpit model

## Scope

### In Scope

- legacy Django templates and page composition for:
  - `/planning/`
  - `/planning/runs/<id>/`
  - `/planning/versions/<id>/`
- presenter/view-model reshaping needed to support a clearer cockpit layout
- reuse of the `scan` shell and page conventions
- targeted planning view tests and smoke-safe UI contract assertions
- planning-related docs updates if the cockpit reading contract changes

### Out of Scope

- merging planning routes into `wms/scan_urls.py`
- removing planning models, services, or URLs
- business-rule changes to solve, publish, clone, exports, or communication generation
- Next/React migration work
- translation work
- automatic sending of planning communications
- redesigning planning as a fully separate new UI system

## Problem Summary

## 1. Separate-Surface Friction

The planning pages currently use a dedicated base template in `templates/planning/base.html`.

That creates a subtle but real product split:
- custom local header
- no `scan` shell or sidebar context
- a feeling of leaving the main operator workspace

Even though planning is already entered from `Gestion > Planning`, the UI feels like a small side application rather than a planning cockpit inside the same WMS.

## 2. Version Page Density

`templates/planning/version_detail.html` renders nearly every major planning concern on the same page in a single long vertical stack:
- version header
- week view
- planning summary
- planning table
- unassigned table
- stats
- exports
- communications
- history

This density causes three concrete operator problems:
- there is no immediate answer to “what needs action now?”
- the primary work area is not visually distinguished from secondary analysis blocks
- communications and detailed analysis compete with core operational planning

## 3. Flat Table-Centric Main Workflow

The main planning block is still driven by a wide assignment table.

That table makes the operator read:
- flight date
- flight time
- flight number
- destination
- routing
- shipment reference
- volumes
- volunteer
- type
- shipper
- recipient
- action controls

before understanding the actual operational picture.

The page already computes flight groups in `wms/planning/version_dashboard.py`, but the main template still leads with a flat assignment grid instead of a flight-first cockpit.

## 4. Secondary Blocks Compete With The Main Flow

Several useful but secondary blocks are shown too prominently:
- week view
- detailed planning summary
- communications editor
- history and diff summary

These blocks are important, but they should not dominate first-glance reading.

## Approaches Considered

### 1. Minimal Visual Cleanup

Idea:
- keep the current planning shell
- retouch spacing and colors only

Pros:
- lowest implementation risk

Cons:
- does not solve the information hierarchy problem
- keeps planning feeling separate from the scan cockpit
- does not materially reduce operator confusion

### 2. Dedicated Planning Domain, Shared Scan Cockpit Language, Recommended

Idea:
- keep planning as its own module, routes, templates, presenters, and tests
- align the surface with the `scan` cockpit shell and hierarchy
- reorganize the version page around priorities, action blocks, and a flight-first main view

Pros:
- preserves the valid planning domain boundary
- removes the mini-app feeling
- matches recent scan UX improvements
- improves readability without reopening the business model

Cons:
- requires a non-trivial template and presenter reshaping
- needs careful UI contract test updates

### 3. Full Functional Merge Into Scan

Idea:
- move planning screens under `scan`
- collapse planning into general scan pages

Pros:
- strongest perception of a single workspace

Cons:
- weak fit for the actual planning lifecycle
- risks mixing shipment operations with planning versioning semantics
- adds structural debt by hiding a real domain boundary

## Recommended Decision

Take approach 2.

Planning remains a dedicated business module, but it should stop feeling like a separate product surface.

The design target is:
- dedicated planning domain
- shared scan shell
- action-first operator reading
- version page simplified around a primary cockpit flow

## Target Design

## 1. Shared Planning Surface Model

### Decision

Keep:
- `wms/planning_urls.py`
- `wms/views_planning.py`
- `wms/planning/*`
- `templates/planning/*`

Do not merge planning routes or business logic into `scan`.

### UI Rule

Replace the dedicated planning shell with the existing `scan` shell conventions.

Implications:
- planning pages should extend a scan-compatible base
- planning should remain visible as part of the same operator workspace
- navigation language, header composition, actions, and spacing should match recent `scan` cockpit patterns

### Product Outcome

The operator still opens planning as a dedicated area, but no longer feels they have switched to another mini-application.

## 2. Run List

### Current Weakness

`run_list` reads as a historical table first.

That makes the operator scan a list before knowing what deserves attention.

### Target Reading

The page should answer:
- which run needs action now?
- which run already produced a usable version?
- should I create a new run or open an existing one?

### Layout

Top to bottom:
1. cockpit page header
2. primary action: `Nouveau run`
3. compact `À traiter` block
4. full history table

### `À traiter` Block

This block should surface high-signal run states, for example:
- runs blocked by issues
- runs ready to solve
- recent runs with a draft version
- recent runs with a published version

The block can be card-based or a compact panel list, but it must be shorter and more actionable than the full table.

### History Table

Keep the complete run history table below, but make it secondary to the action block.

## 3. Run Detail

### Current Weakness

The page splits issues and versions, but does not strongly guide the operator toward the next action.

### Target Reading

The page should answer:
- is this run ready to solve?
- what blocks it?
- which version should I open next?

### Layout

Top to bottom:
1. cockpit page header with run status
2. single dominant CTA based on run state
3. `Contrôles` block for issues
4. `Versions` block with stronger CTA treatment

### CTA Rules

If the run is ready:
- emphasize `Générer le planning`

If the run is already solved:
- emphasize `Ouvrir la dernière version`

If the run has blocking issues:
- keep the issue block visually prominent

### Versions Block

Versions should be shown as a more readable operational list or card stack with:
- version number
- badge/status
- published/draft signal
- `Ouvrir`
- `Voir le diff` when relevant

The goal is to route the operator toward the version cockpit quickly.

## 4. Version Detail

This page is the main simplification target.

## 4.1 Reading Goal

The page should answer in this order:
- what needs action now?
- which flights and assignments should I adjust?
- what details can I inspect after the main review?

## 4.2 Page Structure

Top to bottom:
1. cockpit header
2. priorities block
3. section anchor nav
4. main planning block
5. non-assigned block
6. communications block
7. exports block
8. secondary analytical/detail blocks

## 4.3 Cockpit Header

Replace the current header table-heavy summary with:
- clear title: week + version + status
- compact metadata
- at most 2 to 4 immediately visible primary actions

Primary actions:
- `Publier la version`
- `Créer une nouvelle version`
- `Voir le diff`
- `Exporter`

The summary should read as compact KPI cards or short summary chips rather than a wide table.

## 4.4 Priorities Block

Add a high-signal priority area near the top of the page.

Recommended cards:
- unassigned shipments count
- communication drafts state
- draft/published version state
- manual adjustment count

These cards are not decorative. They should help the operator decide where to go next on the same page.

## 4.5 Section Navigation

Add a small section anchor nav similar to the newer `scan` dashboard:
- `Planning`
- `Non affectés`
- `Communications`
- `Exports`
- `Historique`
- `Détails`

This navigation is especially important because the page remains long even after simplification.

## 4.6 Main Planning Block

### Core Decision

The main planning block should become flight-first, not assignment-first.

### Why

The operator thinks in terms of:
- flight
- volunteer
- assigned shipments
- capacity consumed

not in terms of a raw cross-section table where each row repeats the flight context.

### Data Source

Prefer reusing the existing grouped presenter data already available via `flight_groups` in `wms/planning/version_dashboard.py`.

Do not invent a second competing presentation model if the existing grouped structure can support the cockpit.

### Layout

Render a stack of flight cards or flight panels.

Each flight panel should show:
- date
- time
- flight number
- destination
- routing if useful
- capacity used / capacity available
- volunteer(s)
- list of assigned shipments

Each shipment line inside the flight panel should remain actionable:
- modify assignment
- remove assignment

The current assignment editing controls can stay, but they should live within a more readable flight grouping.

## 4.7 Unassigned Block

The unassigned shipments block should stay visible relatively high on the page because it is a strong operational exception surface.

### Simplification Rule

Show the first-level columns that matter most:
- shipment reference
- destination
- volume
- reason
- action

Keep secondary shipment details available only if they materially help the assignment decision.

### Action Rule

`Ajouter au planning` remains relevant, but the form should feel like a local correction action, not a second full workflow.

## 4.8 Communications Block

### Current Weakness

The communications section is powerful but visually heavy because it renders:
- helper-install logic
- per-family controls
- editable draft forms
- per-draft actions

in one large block.

### Target Model

Split communications into two reading levels:

Level 1:
- family summary cards or compact family panels
- change status
- number of drafts
- generation/open-all actions

Level 2:
- per-draft editable detail only after opening a family

### Outcome

Communications remain version-centric and editable, but do not dominate the first screenful of the cockpit.

## 4.9 Secondary Detail Blocks

The following blocks remain useful but should become secondary:
- week view
- detailed planning summary
- history

### Default Rule

They should be collapsed or visually secondary by default.

The operator should not need to scroll through those blocks before reaching the main planning and communications work areas.

## 5. Keep Dedicated Planning Module Or Move Into Scan?

### Recommendation

Keep a dedicated planning module.

### Why The Dedicated Module Still Matters

Planning owns concepts that are not simple scan pages:
- run preparation
- solve lifecycle
- versioning
- publication
- per-version communication drafts
- artifacts and exports
- version diff

Those concepts justify a distinct business surface and dedicated routing.

### Why The Current Dedicated Surface Still Feels Wrong

The issue is not the domain boundary itself.

The issue is:
- separate shell
- weak cockpit hierarchy
- too much information at once

### Product Decision

Do not merge planning into `scan` technically.

Instead:
- keep planning dedicated in code and routes
- make it read and feel like a `scan` cockpit

## Testing And Documentation Impact

## Tests

Update planning view tests so they assert the new page contracts:
- shared scan shell usage
- cockpit header presence
- priority section presence
- section-nav presence
- flight-group main block presence
- secondary blocks collapsed or visually secondary by default

Keep planning smoke coverage as the business-flow safety net.

## Docs

If the cockpit contract changes materially, update the relevant operational wording in:
- `docs/operations.md`
- `docs/release_checklist.md`

If route ownership or planning cockpit expectations materially change, update the repository reference documents accordingly.

## Implementation Strategy

Implement the redesign in short, safe steps:
1. align planning with the scan shell and page grammar
2. simplify run list and run detail
3. reshape version detail around priorities and flight-first reading
4. compact communications and secondary details
5. update tests and docs together
