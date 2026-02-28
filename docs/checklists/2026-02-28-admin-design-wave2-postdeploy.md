# Post-Deploy Checklist - Admin Design Wave 2 (PythonAnywhere)

Estimated duration: 10 minutes
Scope: `scan`, `portal`, `home`, `login`, Django `admin`, and print `picking` usability.
Out of scope: `frontend-next` / Next/React routes.

## 0) Inputs

- `BASE_URL`: production URL (example: `https://<user>.pythonanywhere.com`)
- One superuser account
- One portal account

## 1) Fast smoke script (1-2 min)

Anonymous checks:

```bash
cd /home/<user>/asf-wms
BASE_URL="https://<user>.pythonanywhere.com" \
./deploy/pythonanywhere/check_design_wave2_postdeploy.sh
```

Authenticated checks (optional but recommended):

```bash
cd /home/<user>/asf-wms
SESSION_COOKIE="sessionid=<copied-from-browser>" \
BASE_URL="https://<user>.pythonanywhere.com" \
./deploy/pythonanywhere/check_design_wave2_postdeploy.sh
```

Expected result:
- Summary ends with `0 fail`.

## 2) Manual visual validation (6-7 min)

### A) Admin Design page

Path: `/scan/admin/design/` (superuser)

Checks:
- Accordion families are present (Foundations, Typography, Global colors, Buttons, Inputs, Cards/Panels, Navigation, Tables, Business states).
- Help/tooltips are visible next to fields.
- `Apercu rapide (live)` updates immediately when editing values, without clicking `Enregistrer`.
- Test the specific bug case:
  - Change `Btn primaire - fond` and `Btn primaire - bordure` to two clearly different colors.
  - In preview, button border color stays independent from background.

### B) Runtime propagation across pages

After saving on admin design:

- `/scan/dashboard/`
- `/scan/stock/`
- `/portal/login/`
- `/portal/` (portal dashboard, logged-in portal user)
- `/password-help/`
- `/admin/wms/stockmovement/` (superuser)

Checks on each page:
- Colors and typography are applied (no fallback visual mismatch).
- Primary button border stays consistent with `Btn primaire - bordure` token.
- No broken layout or unreadable text.

### C) Picking print usability

From `scan` flow, open a generated picking page:
- `Liste picking - kits` or `Liste picking - carton`

Checks:
- Table remains readable.
- Borders and text contrast are acceptable for print/PDF.
- No clipped content.

## 3) Rollback (under 1 min)

If a critical UI issue is detected:

1. Go to `/scan/admin/design/`.
2. Click `Reinitialiser (valeurs recommandees)`.
3. Re-check `/scan/dashboard/` and `/portal/login/`.

## 4) Sign-off

- [ ] Smoke script passed (`0 fail`)
- [ ] Admin design accordions + live preview validated
- [ ] Primary border separation validated
- [ ] Pages validated: scan/portal/home/login/admin
- [ ] Picking print remains usable
- [ ] No rollback required
