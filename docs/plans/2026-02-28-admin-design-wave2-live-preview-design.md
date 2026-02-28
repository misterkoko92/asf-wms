# Admin Design Wave 2 Live Preview Design

**Date:** 2026-02-28
**Status:** Approved in-session
**Owner:** Codex + product owner

## 1) Context

The current `Scan > Admin > Design` page already supports runtime theme settings, but:

- Priority tokens are grouped in a single block and are hard to navigate.
- The quick preview updates only after full save/reload.
- Some visual dependencies are too implicit (example observed: button border impact while changing primary color).
- We need broader runtime control for design without touching code.

## 2) Scope (validated)

### In scope

- Extend `Admin > Design` with a larger set of useful runtime variables.
- Reorganize variables by family using accordion sections.
- Add live quick preview updates on form change (no save required for preview).
- Make design behavior consistent across:
  - `scan`
  - `portal`
  - `home`
  - `login`
  - customized Django `admin`
- Verify that already implemented variables still work correctly.
- Keep print `picking` usable (no regression).

### Out of scope

- Any `frontend-next` / Next.js / React work.
- Full print design refactor for non-picking templates.

## 3) UX Direction (validated)

### 3.1 Accordion information architecture

Replace the current flat "priority variables" block with accordions:

1. `Foundations`
2. `Typography`
3. `Global colors`
4. `Buttons`
5. `Inputs`
6. `Cards/Panels`
7. `Navigation`
8. `Tables`
9. `Business states`

Default expanded sections:

- `Foundations`
- `Global colors`
- `Buttons`

All other sections are collapsed by default.

### 3.2 Guidance for non-design users

Each token must provide:

- concise label in plain language
- explicit impact hint (what changes where)
- tooltip/help text with concrete examples

Example guidance:

- `Button radius`: "0 = sharp corners, 8 = subtle roundness, 16 = very rounded, 999 = pill."
- `Card shadow`: "none = flat, soft = slight depth, medium/strong = higher visual emphasis."

When possible, prefer constrained inputs:

- `select` for modes/presets
- predefined ranges for number fields
- shadow presets + optional advanced text input

## 4) Variable Catalog Strategy

### 4.1 Keep backward compatibility

- Keep existing design fields and existing priority tokens fully supported.
- Keep `design_tokens` JSON as extensibility mechanism.
- Continue merged resolution order: defaults -> legacy columns -> `design_tokens`.

### 4.2 Extend catalog with useful groups

Wave 2 token families (representative list, non-exhaustive):

- Foundations: density, spacing scale, container/content width.
- Typography: heading/body sizes, line heights, font weights, letter spacing.
- Global colors: links, focus ring, disabled states, alt surfaces.
- Buttons: heights/paddings/radius/border width/icon gap/style mode.
- Inputs: paddings, border/focus colors, placeholder/help/error/success states.
- Cards/Panels: radius, border width/color, header bg/text.
- Navigation: item padding/radius/hover/active/dropdown tokens.
- Tables: header, row alt, hover, border, filter/sort colors.
- Business states: badges and semantic state triplets (bg/text/border).

## 5) Live Preview Behavior

### 5.1 Expected behavior

- Quick preview must update immediately on `input` and `change`.
- Save button persists settings to runtime store; preview should not require save.
- Invalid value should show inline feedback and skip preview application for the invalid field.

### 5.2 Technical direction

- Bind listeners on all design fields in `admin_design` form.
- Map form values to local preview CSS custom properties.
- Apply updates to preview wrapper only (no global page mutation before save).
- Keep existing reset/save semantics unchanged.

## 6) Conformance and Regression Strategy

### 6.1 Root issue to eliminate

Changing one variable (example: primary) must not unexpectedly alter unrelated aspects (example: button border) unless explicitly mapped by token design.

### 6.2 Token mapping rule

For interactive components, explicitly separate:

- background token
- text token
- border token

No accidental fallback chain should force border colors from primary when dedicated border tokens exist.

### 6.3 Coverage target

100% conformance for the validated scope:

- `scan`, `portal`, `home`, `login`, customized `admin`

Approach:

- audit template/static CSS usage for hardcoded values bypassing runtime tokens
- replace or bridge with tokenized variables
- verify semantic states and focus/hover/active behavior

## 7) Verification Plan

### 7.1 Automated checks

- Extend existing Django tests around `scan_admin_design`.
- Add assertions for:
  - grouped family rendering in accordions
  - live-preview hooks present in HTML/JS
  - CSS variable output for old and new tokens
  - no regression in existing tokens

### 7.2 Manual smoke matrix

Verify representative pages:

- scan dashboard/stock/orders/admin pages
- portal login/dashboard/order pages
- home and login pages
- Django admin pages with custom bootstrap layer
- print picking usability

### 7.3 Acceptance criteria

- Variables are grouped by family in accordions.
- Preview updates live without save.
- Existing variables still work as expected.
- Primary color changes no longer produce unintended button border side effects.
- All in-scope page families honor runtime design changes.
- Picking print flow remains usable.

## 8) Deployment Note (PythonAnywhere)

- Prepare rollout with low-risk incremental release.
- Keep admin reset-to-default available as fallback.
- Run post-deploy smoke checklist on in-scope pages.
- Exclude next/react path from rollout work.
