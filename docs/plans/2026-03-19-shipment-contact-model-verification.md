# Shipment Contact Model Verification

Date: 2026-03-20

## Scope verified
- runtime expedition base sur `ShipmentShipper` / `ShipmentRecipientOrganization` / liens autorises, sans retour aux resolvers `org-roles` pour les flux expedition;
- scan expedition, preparation de commande, portail destinataires, cockpit admin shipment parties et readers snapshot;
- notifications expedition et rendering qui lisent des snapshots figes ou le registre shipment parties selon le cas;
- guardrails de retrait runtime `org-roles` sur le sous-domaine expedition.

## Verification fallout fixed during Task 11
- realignement des fixtures/tests encore branches uniquement sur `OrganizationRoleAssignment`, `ShipperScope` et `RecipientBinding` pour qu'ils provisionnent aussi le registre shipment parties quand le runtime expedition en depend;
- correction de `ScanShipmentForm.clean()` pour valider explicitement l'eligibilite de l'expediteur contre la destination, au lieu de faire confiance au `queryset` courant du champ;
- realignement du test de flux `prepare_order()` avec un expediteur shipment-party valide et un destinataire autorise, conformement au runtime introduit en Task 10;
- mise a jour des attentes emailing/portal vers le comportement courant: messages anglais natifs, fallbacks snapshot/live, notification admin encore presente sur la livraison.

## Commands executed and results

### 1) Focused regression slice after verification fallout
```bash
./.venv/bin/python manage.py test \
  wms.tests.shipment.tests_shipment_party_snapshot \
  wms.tests.forms.tests_forms \
  wms.tests.forms.tests_forms_org_roles_gate \
  wms.tests.views.tests_views.ScanViewTests \
  wms.tests.views.tests_views_portal.PortalAccountViewsTests \
  wms.tests.views.tests_views_portal.PortalOrdersViewsTests \
  wms.tests.emailing.tests_signals_extra \
  wms.tests.emailing.tests_signals_org_role_notifications \
  wms.tests.emailing.tests_email_flows_e2e -v 2
```
Result: `Ran 166 tests ... OK`

### 2) Shipment suite
```bash
./.venv/bin/python manage.py test wms.tests.shipment -v 2
```
Result: `Ran 89 tests ... OK`

### 3) Forms suite
```bash
./.venv/bin/python manage.py test wms.tests.forms -v 2
```
Result: `Ran 57 tests ... OK`

### 4) Portal suite
```bash
./.venv/bin/python manage.py test wms.tests.portal -v 2
```
Result: `Ran 59 tests ... OK`

### 5) Views suite
```bash
./.venv/bin/python manage.py test wms.tests.views -v 2
```
Result: `Ran 615 tests ... OK`

### 6) Emailing suite
```bash
./.venv/bin/python manage.py test wms.tests.emailing -v 2
```
Result: `Ran 80 tests ... OK`

### 7) Shipment guardrails + core flow
```bash
./.venv/bin/python manage.py test \
  wms.tests.core.tests_shipment_parties_guardrails \
  wms.tests.core.tests_flow -v 2
```
Result: `Ran 3 tests ... OK`

### 8) Global dependency / consistency check
```bash
uv run make check
```
Result: `No broken requirements found.`

## Residual risks
- cette verification finale suit exactement la matrice Task 11, mais ne relance pas la suite projet complete `wms.tests`;
- aucun passage Playwright ou recette manuelle operateur n'a ete rejoue ici sur scan/portail/admin apres la vague finale;
- le perimetre `org-roles` hors expedition reste volontairement present pour les usages legacy qui ne font pas partie de cette refonte.

## Go / No-Go
- **Go** pour la refonte shipment contact model sur le perimetre Django legacy couvert par la matrice ci-dessus.
