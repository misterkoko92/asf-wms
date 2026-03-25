# Portal And Benevole Navigation Adaptation Design

**Date:** 2026-03-25

## Goal

Adapt `portal/` and `benevole/` to the same navigation language now validated on `scan/`, without copying the `scan` sidebar shell.

The target is:
- the same `utility / primary / local` separation,
- the same calmer navigation grammar,
- and a lighter authenticated shell for smaller surfaces.

## Context

`scan/` is now the reference legacy shell for global navigation:
- utility controls live in the masthead,
- primary product sections are separated from actions,
- and local workflow controls remain inside pages.

`portal/` and `benevole/` still expose their authenticated navigation mostly as button rows in:
- `templates/portal/base.html`
- `templates/benevole/base.html`

That creates three problems:
- navigation still looks like actions,
- logout keeps the same visual weight as primary sections,
- and `portal` still mixes a main CTA with peer navigation items.

## Scope

### In Scope

- authenticated shell adaptation for `templates/portal/base.html`
- authenticated shell adaptation for `templates/benevole/base.html`
- shared legacy navigation language based on the `scan` contract
- responsive desktop/mobile behavior
- shell-level tests for both surfaces

### Out of Scope

- `scan/` changes
- Django admin shell changes
- volunteer auth pages
- portal auth pages
- translation work
- Next/React work
- page-local toolbars, action bars, or workflow controls

## Recommended Decision

Do not port the `scan` sidebar to `portal` or `benevole`.

Adopt the same navigation language with a lighter shell:
- masthead with utility controls,
- primary horizontal navigation for desktop,
- compact offcanvas on mobile,
- CTA separated from navigation where needed.

## Portal

### Shell Structure

- left: logo + short portal identity
- right: language + account + logout
- primary navigation: `Commandes`, `Facturation`, `Destinataires`, `Compte`
- distinct CTA: `Nouvelle commande`

### Rules

- `Nouvelle commande` is not a peer navigation item
- account remains both a primary section and a utility session menu
- logout stays utility-only
- no sidebar desktop

### Mobile

- offcanvas menu for primary navigation and CTA
- utility account/logout kept separate in the masthead

## Benevole

### Shell Structure

- left: logo + short volunteer identity
- right: language + account + logout
- primary navigation: `Accueil`, `Profil`, `Contraintes`, `Disponibilités`, `Récap`
- no dominant CTA

### Rules

- the shell stays lighter than `portal`
- logout stays utility-only
- the navigation should read as orientation, not as a task toolbar

### Mobile

- same offcanvas principle if the section rail becomes too tight
- no extra action cluster

## Shared Visual Language

Reuse from `scan/`:
- light masthead
- separated utility controls
- explicit active state
- softer primary navigation
- strict distinction between navigation and actions

Do not reuse from `scan/`:
- persistent desktop sidebar
- operator-density shell balance
- broader admin utility footprint

## Rollout

Recommended order:
1. document the adaptation contract
2. add a small `UI Lab` reference block if helpful
3. implement `portal`
4. implement `benevole`
5. validate with shell tests

## Success Criteria

- `portal` no longer reads as a button strip
- `portal` separates navigation from `Nouvelle commande`
- `benevole` keeps a calm authenticated shell
- logout is visually utility-only on both surfaces
- desktop/mobile remain clear without introducing a sidebar desktop shell
