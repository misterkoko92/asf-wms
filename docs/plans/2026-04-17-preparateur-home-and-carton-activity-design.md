# Preparateur Home And Carton Activity Design

**Date:** 2026-04-17

## Goal

Adjust the legacy Django preparateur flow so the shared preparateur account opens on a dedicated
operator home that:

- requires choosing the active bénévole by name
- keeps `Bonjour Martin` visible in the scan shell until logout
- proposes two explicit actions:
  - préparer une commande
  - préparer des colis non affectés
- exposes `Voir dernier carton`
- keeps the existing carton-edit flow available
- adds durable bénévole-level traceability for carton preparation and carton edits
- improves the preparateur success pop-up with a top-right close control and a footer print action

## Current Context

The current `scan_root()` behavior redirects preparateur users directly to `scan_pack`. That works
for manual carton preparation, but it does not establish which bénévole is currently operating
behind the shared preparateur account.

The codebase already contains two useful anchors:

- `Carton.prepared_by`, which can hold the initial preparateur for a carton
- `scan_carton_edit`, which already supports editing an eligible carton

What is missing is:

- a session-level active bénévole identity
- a dedicated preparateur home
- a durable trace of carton edits that does not overwrite the initial preparateur
- a “last carton” query tied to bénévole activity rather than the shared login session

## Validated User Decisions

Validated during design review:

- the selected bénévole must be traced, not used only for display
- carton edits must add a new trace instead of replacing the initial preparateur
- `Voir dernier carton` must look across historical bénévole activity, not only the current session
- when several cartons appear in the success pop-up, the footer action must print all displayed
  packing lists
- `Préparer une commande` must default to the most critical and fully realizable order
- the order selector must show two groups:
  - `Les 3 commandes les plus critiques`
  - `Toutes les commandes`
- the second group is sorted A-Z on the shipper / expéditeur name
- “réalisable” means the whole order is immediately preparable with current stock

## Workflow Overview

### 1. Login And Identity Binding

For the preparateur group:

- `/scan/` no longer jumps straight to `scan_pack`
- `/scan/` opens a dedicated preparateur home
- the home requires choosing an active `VolunteerProfile`
- the selected profile is stored in session and rebound on every allowed preparateur page

If no bénévole is selected:

- action cards remain visible
- action buttons are disabled
- the page shows a short prompt to choose a bénévole first

### 2. Persistent Greeting

Once a bénévole is selected:

- the scan shell header shows `Bonjour Martin` in the upper-left area on all preparateur pages
- the greeting uses the selected profile first name when available
- the greeting disappears only when the session is cleared or the user logs out

### 3. Preparateur Actions

The home page exposes:

- `Préparer une commande`
- `Préparer des colis non affectés`
- `Voir dernier carton`

`Préparer des colis non affectés` reuses the existing manual preparation surface under `scan_pack`.

`Voir dernier carton` opens the latest carton linked to the selected bénévole activity. The lookup
prefers a non-shipped carton when one exists; otherwise it falls back to the latest carton overall.

## Bénévole Selector Contract

The selector uses active `VolunteerProfile` rows and displays labels in the format:

- `Martin DUPOND`

Sorting contract:

- `user.last_name` ascending
- then `user.first_name` ascending
- then stable `id`

This selector is the single source of truth for the current preparateur identity in the session.

## Preparing An Order

### Candidate Scope

The home page does not expose every order.

It exposes only orders that are:

- validated (`review_status=APPROVED`)
- not cancelled
- not already fully ready
- fully realizable now

### “Fully Realizable Now” Rule

The recommendation helper must not mutate stock or reservations during home-page rendering.

It computes an advisory `realisable_now` flag by checking that the remaining quantity of each order
line can be covered immediately by current warehouse stock. Orders already in
`RESERVED` or `PREPARING` count as realizable.

The actual preparation action still reuses the existing domain services and remains the final source
of truth. If stock changed between page render and click, the existing service error handling still
applies.

### Criticality Rule

For realizable orders, the recommendation order is:

1. requested delivery date ascending, with missing dates last
2. creation date ascending
3. stable id ascending

The first three rows become the `Les 3 commandes les plus critiques` optgroup.

The second optgroup, `Toutes les commandes`, contains all realizable orders sorted A-Z by the
shipper / expéditeur display name.

### Default Selection And Action

The home page defaults to:

- the first order in the `3 commandes les plus critiques` group
- otherwise the first order in the `Toutes les commandes` group

The CTA reuses the existing order-preparation workflow rather than creating a second preparation
engine. The selected-order action posts into the existing “prepare shipment and cartons” behavior.

## Preparing Unassigned Cartons

The second home action points to the current manual carton-preparation flow (`scan_pack`).

This keeps the existing UI and the current success modal, while adding the active bénévole context
to:

- the initial `prepared_by` attribution
- carton edit logging
- “last carton” lookup

## Carton Traceability

### Initial Preparation

`Carton.prepared_by` keeps its meaning: it stores the initial preparateur of the carton.

For the shared preparateur account, new cartons must use the selected bénévole user as
`prepared_by`, not the shared login account.

### Edit Trace

Add a dedicated carton-activity log for bénévole actions. The log records at least:

- carton
- volunteer profile
- action type (`prepared`, `edited`)
- authenticated actor account when available
- timestamp

The edit flow adds a new `edited` entry and does not overwrite `Carton.prepared_by`.

### Last Carton Lookup

`Voir dernier carton` uses the activity log first:

- latest bénévole activity wins
- if several cartons match, prefer the latest non-shipped carton
- otherwise return the latest carton overall

If a bénévole has no activity yet, the page stays on the preparateur home and shows an explicit
message.

## Success Pop-Up Changes

The existing preparateur success modal under `scan_pack` keeps its current carton summaries and
adds:

- a close button in the top-right modal header
- a footer print action

Footer label contract:

- one carton: `Imprimer`
- multiple cartons: `Imprimer tout`

Behavior:

- one carton: open its packing list
- multiple cartons: open all displayed packing lists

No second footer action is introduced in this first delivery. Per-carton print buttons inside the
modal remain out of scope unless later requested.

## Preparator Access Scope

The preparateur whitelist must expand only as far as needed for the validated workflow:

- dedicated preparateur home
- manual carton preparation
- carton detail / edit
- order preparation surface needed by the home CTA
- any existing follow-up page required by the reused order-preparation flow

The dashboard and the broad scan management surfaces remain blocked for the preparateur group.

## Tests

Coverage should prove:

- preparateur root opens the new home instead of `scan_pack`
- the bénévole selector renders `Prénom NOM` and sorts by surname A-Z
- the greeting persists across allowed preparateur pages
- home actions are disabled until a bénévole is selected
- the order selector renders the two validated optgroups
- the default selected order is the most critical realizable one
- the “all orders” group is sorted by shipper name A-Z
- `Voir dernier carton` prefers the latest non-shipped carton for the selected bénévole
- creating a carton under the shared preparateur account sets `prepared_by` to the selected
  bénévole user
- editing a carton adds a new bénévole activity entry and preserves the original `prepared_by`
- the success modal renders a top-right close button
- the success modal prints one or all packing lists according to the number of cartons displayed

## Repo-Reference Impact

This work changes a critical legacy scan workflow and the preparateur navigation contract. Before
closing the work:

- re-check `docs/repo-reference/03-impact-map.md` for scan-page propagation
- update `docs/repo-reference/04-shared-contracts.md` if the reduced preparateur navigation
  contract changes
- update any living tests or reference notes that describe the preparateur scan entry flow
