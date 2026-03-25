# Legacy Global Navigation Design

**Date:** 2026-03-25

## Goal

Improve the legacy global navigation so it is easier to scan, more visually appropriate, and more responsive across `scan`, `portal`, and `benevole`.

The target is not a cosmetic navbar repaint. The target is a clearer navigation model with:
- a lighter utility layer,
- a calmer primary navigation layer,
- and explicit separation between navigation, page actions, and local workflow controls.

## Context

The legacy UI waves and the `UI Lab` convergence series are complete.

The repository now has:
- a stable shared base for low-level controls and layout contracts,
- a documented set of convergence patterns in `scan/ui-lab/`,
- and an adoption note that already says future work should reuse those references through normal tickets instead of opening speculative new waves.

Navigation is now the main remaining cross-surface weakness:
- `scan` overloads the top level with product areas, workflow areas, admin access, and account utilities in one band,
- `portal` exposes navigation mostly as a row of action buttons,
- `benevole` is clearer than `portal` on active state, but still reads as a button strip more than a navigation system,
- `admin` uses a separate Django admin shell and should not be forced into the same product navigation model.

## Scope

### In Scope

- legacy navigation design for `templates/scan/base.html`
- legacy navigation design for `templates/portal/base.html`
- legacy navigation design for `templates/benevole/base.html`
- a future `UI Lab` demonstration for the recommended global navigation contract
- responsive behavior for desktop and mobile
- visual and structural rules that distinguish navigation from actions

### Out of Scope

- Django admin shell redesign
- Next/React work
- translation or wording parity work
- workflow-local toolbars and action bars
- page-level form actions
- a repo-wide retrofit wave triggered only by this design

## Problems To Solve

### Scan

The current `scan` navigation is the most overloaded:
- too many first-level entries,
- dropdowns used to compensate for weak hierarchy,
- account and admin mixed into the main product band,
- labels that are too long or too descriptive for top-level navigation,
- and a heavy "double panel" effect from header plus nav panel.

### Portal

The current `portal` shell is simpler, but it reads as a row of tertiary buttons rather than a structured navigation system.

It does not clearly distinguish:
- sections,
- the main action,
- and utility/account actions.

### Benevole

The current `benevole` shell has a usable active state, but it still relies on button-strip navigation and mixes logout into the same visual grammar as main sections.

## Approaches Considered

### 1. Visual refresh only

Idea:
- keep the existing information architecture,
- adjust spacing, colors, borders, and active states.

Pros:
- smallest implementation.

Cons:
- keeps the same hierarchy problems,
- leaves `scan` overloaded,
- and treats a structural issue like a paint issue.

### 2. Three-layer legacy navigation, recommended

Idea:
- define three distinct layers:
  - utility,
  - primary navigation,
  - local page controls.
- validate the pattern in `UI Lab`,
- then apply it first to `scan`,
- and adapt it to `portal` and `benevole`.

Pros:
- solves the real hierarchy problem,
- gives a shared legacy navigation language,
- stays compatible with the current Bootstrap-based stack,
- and keeps rollout incremental.

Cons:
- requires template changes, not just CSS.

### 3. Full app-shell redesign with persistent side navigation

Idea:
- move the legacy product to a broader admin/workspace shell with a sidebar or hybrid shell.

Pros:
- strong long-term navigation structure.

Cons:
- too large for the current legacy scope,
- risky on mobile,
- and likely to create more churn than value right now.

## Recommended Decision

Take approach 2.

The repository should adopt a three-layer navigation model across legacy shells:

1. Utility layer
   - brand
   - language switch
   - account
   - logout
   - optional superuser/admin access

2. Primary navigation layer
   - top-level product sections only
   - no workflow-local actions
   - no account utilities

3. Local page layer
   - page header
   - toolbar
   - section actions
   - workflow action bars

The global navigation must answer:
- where am I,
- where can I go next,
- and which items are global sections versus local actions.

## Information Architecture

### Shared Rule

Navigation is not action.

That means:
- navigation items should not look like a row of equivalent action buttons,
- main CTAs should remain separate from the main section rail,
- account and admin should remain utility-level concepts,
- and page-level filters or workflow controls should stay outside the global shell.

### Scan

Recommended first-level sections:
- `Tableau de bord`
- `Stocks`
- `Reception`
- `Preparation`
- `Expeditions`
- `Gestion`

Recommended removals from the first level:
- `Compte`
- `Admin`
- `Planning`
- verbose labels such as state-view descriptions

Recommended second-level treatment:
- `Stocks` contains the current "view state" pages
- `Reception` contains receiving flows
- `Preparation` contains kit, carton, and shipment preparation
- `Expeditions` contains tracking and related shipment-oriented follow-up
- `Gestion` contains operator/support back-office pages

Recommended utility treatment:
- `Compte` stays in the utility layer
- `Admin` stays in utility for superusers only
- `Planning` can remain a utility or adjacent jump link if it must stay globally reachable

### Portal

Recommended primary sections:
- `Commandes`
- `Facturation`
- `Destinataires`
- `Compte`

Recommended action separation:
- `Nouvelle commande` becomes a distinct CTA, not a peer navigation item.

Logout should move to the utility layer.

### Benevole

Recommended primary sections:
- `Accueil`
- `Profil`
- `Contraintes`
- `Disponibilites`
- `Recap`

Logout should move to the utility layer.

Auth pages should stay simpler and should not inherit the full authenticated navigation structure.

### Admin

Do not force Django admin into the same navigation model.

`admin-bootstrap.css` should keep acting as a visual bridge only.

## Visual Language

The visual goal is calmer and more editorial than the current button-strip feeling.

Recommended direction:
- keep the header light,
- reduce the "double panel" effect in `scan`,
- present primary navigation as a flexible section rail or soft tab row,
- use a clear active state,
- keep inactive items quieter,
- and reserve button styling for actual actions.

Recommended distinctions:
- navigation = links / tabs / section rail
- action = buttons
- utility = compact, secondary controls

Not recommended:
- dark admin-style navbar shells,
- over-decorated nav items,
- identical emphasis for navigation, CTAs, and logout,
- or new visual primitives outside the current legacy design language.

## Responsive Rules

The design is not desktop-only and not mobile-first in the sense of shrinking a desktop strip into a compressed stack. It must work cleanly on both.

### Scan

Desktop:
- visible primary section rail,
- clear separation from utility controls,
- shallow dropdown depth,
- strong active section state.

Mobile:
- use a dedicated menu container such as an offcanvas or focused collapse panel,
- keep utility controls separate,
- avoid long nested dropdown stacks,
- keep the current section and the way to open the menu obvious.

### Portal And Benevole

Desktop:
- compact horizontal primary navigation,
- CTA separated from main sections.

Mobile:
- allow a clean wrap if the item count remains low,
- otherwise move to the same dedicated menu approach as `scan`,
- never collapse into two rows of equally weighted mini-buttons.

## Implementation Strategy

The rollout should happen in three phases.

### Phase 1: Validate In UI Lab

Add a dedicated `Global navigation` demo to `scan/ui-lab/`:
- one recommended `scan` shell demo,
- optional lighter `portal` and `benevole` variants,
- no runtime business actions,
- desktop and mobile review target.

This keeps navigation design review out of production templates while the contract is still being validated.

### Phase 2: Apply To Scan

`scan` is the highest-value adoption target:
- it has the strongest hierarchy problem,
- it exercises both density and responsive constraints,
- and it can act as the source shell for later adaptations.

### Phase 3: Adapt To Portal And Benevole

After `scan` stabilizes:
- move `portal` from button-strip navigation to section navigation plus CTA,
- move `benevole` to the same calmer model, with a lighter authenticated shell.

## Verification Strategy

### Automated

- update `wms/tests/views/tests_scan_bootstrap_ui.py` for the `UI Lab` demo and `scan` shell
- update `wms/tests/views/tests_portal_bootstrap_ui.py` for `portal` shell expectations
- update `wms/tests/views/tests_views_volunteer.py` or another volunteer-facing shell test module for `benevole`

### Manual

Review:
- desktop wide
- narrow laptop
- tablet width
- mobile width

Focus checks:
- section discoverability
- active-state clarity
- separation of nav versus CTA
- utility placement
- collapsed/mobile menu readability

## Success Criteria

The design is successful if:
- the legacy product gains a shared navigation model across `scan`, `portal`, and `benevole`
- `scan` no longer overloads the first-level navigation
- `portal` and `benevole` stop reading as rows of action buttons
- mobile navigation becomes clearer instead of denser
- and the rollout happens incrementally, starting with `UI Lab` and `scan`, without opening another speculative full-repo wave
