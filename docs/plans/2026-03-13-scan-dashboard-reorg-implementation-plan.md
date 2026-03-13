# Scan Dashboard Reorg Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Reorganiser le dashboard scan legacy pour introduire des KPI dates explicites, un graphique expeditions par destination avec filtre de statut, et un calcul live des `equivalent_units` coherent avec le planning.

**Architecture:** Garder la vue Django legacy `scan_dashboard` comme point d'entree unique, mais refactoriser sa logique en helpers de bornes de dates, KPI et aggregation graphique. Conserver le filtre `destination` existant pour les widgets historiques, et ajouter des formulaires GET locaux pour `KPI` et `Graphique expéditions` dans le template legacy.

**Tech Stack:** Django 4.2, templates Django, ORM Django, tests `manage.py test`, logique d'equivalence `wms.unit_equivalence`.

---

Skill refs during execution: `@superpowers:test-driven-development`, `@superpowers:verification-before-completion`, `@superpowers:systematic-debugging`.

### Task 1: Couvrir les nouveaux KPI et les bornes de dates

**Files:**
- Modify: `wms/tests/views/tests_views_scan_dashboard.py`

**Step 1: Write the failing tests**

Ajouter des tests qui couvrent:
- fallback KPI sur la semaine courante du lundi au dimanche inclus;
- `Nb Commandes reçues` base sur `Order.created_at`;
- `Nb commandes en traitement` base sur `Order.status in {reserved, preparing}`;
- `Nb commandes a valider / corriger` base sur `Order.review_status in {pending_validation, changes_requested}`;
- `Nb Colis créés` base sur `Carton.created_at`;
- `Nb Colis affectés` base sur `CartonStatusEvent.new_status = assigned`;
- `Nb Expéditions prêtes` base sur `Shipment.ready_at`;
- fallback semaine courante quand `kpi_start > kpi_end`.

Exemples d'assertions attendues:

```python
kpi_cards = {card["label"]: card["value"] for card in response.context["kpi_cards"]}
self.assertEqual(kpi_cards["Nb commandes en traitement"], 2)
self.assertEqual(kpi_cards["Nb commandes a valider / corriger"], 2)
self.assertEqual(kpi_cards["Nb Colis affectés"], 1)
self.assertEqual(kpi_cards["Nb Expéditions prêtes"], 1)
```

**Step 2: Run test to verify it fails**

Run:
- `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_views_scan_dashboard.ScanDashboardViewTests -v 2`

Expected: FAIL sur les nouvelles assertions `kpi_cards`, sur les nouvelles cles de contexte de dates, ou sur la logique de fallback.

**Step 3: Commit**

```bash
git add wms/tests/views/tests_views_scan_dashboard.py
git commit -m "test(scan): cover dashboard kpi date filters"
```

### Task 2: Implementer les bornes de dates et les KPI cote vue

**Files:**
- Modify: `wms/views_scan_dashboard.py`

**Step 1: Add reusable date-bound helpers**

Introduire des helpers explicites, par exemple:

```python
def _current_week_date_bounds():
    today = timezone.localdate()
    week_start = today - timedelta(days=today.weekday())
    return week_start, week_start + timedelta(days=6)


def _parse_date_window(start_raw, end_raw):
    default_start, default_end = _current_week_date_bounds()
    ...
    return start_date, end_date, start_at, end_at
```

Le helper doit:
- parser des `YYYY-MM-DD`;
- produire des bornes `datetime` locales inclusives;
- fallback sur lundi-dimanche si invalide ou inverse.

**Step 2: Replace legacy `period` KPI logic**

Supprimer la dependance a `PERIOD_*`, `_period_start()` et `_normalize_period()` pour la carte KPI, puis construire `kpi_cards` a partir des nouvelles bornes:

```python
kpi_cards = [
    _build_card(label=_("Nb Commandes reçues"), value=orders_received_count, ...),
    _build_card(label=_("Nb commandes en traitement"), value=orders_processing_count, ...),
    _build_card(label=_("Nb commandes a valider / corriger"), value=orders_review_count, ...),
    _build_card(label=_("Nb Colis créés"), value=cartons_created_count, ...),
    _build_card(label=_("Nb Colis affectés"), value=cartons_assigned_count, ...),
    _build_card(label=_("Nb Expéditions prêtes"), value=shipments_ready_count, ...),
]
```

Utiliser:
- `Order.status`
- `Order.review_status`
- `CartonStatusEvent`
- `Shipment.ready_at`

**Step 3: Expose template context**

Ajouter au contexte:
- `kpi_cards`
- `kpi_start`
- `kpi_end`
- `kpi_period_label` si utile pour l'affichage ou l'aide

Retirer du contexte ce qui n'est plus necessaire pour la carte KPI:
- `period`
- `period_choices`
- `period_label`
- `activity_cards`

**Step 4: Run tests**

Run:
- `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_views_scan_dashboard.ScanDashboardViewTests -v 2`

Expected: PASS sur les tests KPI nouvellement ajoutes. D'autres tests template/UI peuvent encore casser a ce stade.

**Step 5: Commit**

```bash
git add wms/views_scan_dashboard.py
git commit -m "feat(scan): add dashboard kpi date windows"
```

### Task 3: Couvrir le nouveau graphique expeditions par destination

**Files:**
- Modify: `wms/tests/views/tests_views_scan_dashboard.py`

**Step 1: Write the failing tests**

Ajouter des tests qui couvrent:
- alignement par defaut de `chart_start/chart_end` sur les bornes KPI;
- filtre `shipment_status`;
- aggregation par destination;
- somme des `equivalent_units` par destination;
- fallback si `shipment_status` est invalide.

Preparer les donnees de test minimales:
- deux expeditions sur une destination avec contenu colis different;
- une expedition sur une autre destination;
- des `CartonItem` et `ShipmentUnitEquivalenceRule` pour obtenir une somme `equivalent_units` non triviale.

Exemple d'assertions:

```python
chart_rows = response.context["shipment_chart_rows"]
self.assertEqual(chart_rows[0]["shipment_count"], 2)
self.assertEqual(chart_rows[0]["equivalent_units"], 5)
self.assertEqual(response.context["shipment_status"], ShipmentStatus.PACKED)
```

**Step 2: Run test to verify it fails**

Run:
- `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_views_scan_dashboard.ScanDashboardViewTests -v 2`

Expected: FAIL sur les nouvelles lignes `shipment_chart_rows` et/ou sur les champs de contexte du filtre graphique.

**Step 3: Commit**

```bash
git add wms/tests/views/tests_views_scan_dashboard.py
git commit -m "test(scan): cover dashboard shipment chart filters"
```

### Task 4: Implementer l'aggregation graphique et le calcul live des `equivalent_units`

**Files:**
- Modify: `wms/views_scan_dashboard.py`

**Step 1: Add chart filter helpers**

Ajouter:
- un helper de normalisation `shipment_status`;
- un tuple `DASHBOARD_CHART_SHIPMENT_STATUS_CHOICES` derive de `ShipmentStatus.choices` avec option vide `Tous les états`;
- un helper de construction de libelle destination.

Exemple:

```python
def _normalize_shipment_status(raw_value):
    allowed = {choice[0] for choice in ShipmentStatus.choices}
    value = (raw_value or "").strip()
    return value if value in allowed else ""
```

**Step 2: Add live equivalent-unit computation**

Introduire un helper qui calcule les unites equivalentes pour une expedition a partir de ses cartons:

```python
def _build_shipment_equivalence_items(shipment):
    items = []
    for carton in shipment.carton_set.all():
        for carton_item in carton.cartonitem_set.all():
            items.append(
                ShipmentUnitInput(
                    product=carton_item.product_lot.product,
                    quantity=carton_item.quantity,
                )
            )
    return items
```

Puis sommer avec:

```python
equivalent_units = resolve_shipment_unit_count(
    items=_build_shipment_equivalence_items(shipment),
    rules=equivalence_rules,
)
```

Charger les regles actives une seule fois par requete.

**Step 3: Replace chart-by-status with chart-by-destination**

Construire `shipment_chart_rows` comme une liste de dictionnaires tries par volume:

```python
{
    "destination_label": "ABJ - ABIDJAN",
    "shipment_count": 2,
    "equivalent_units": 5,
    "shipment_percent": 100.0,
    "equivalent_percent": 83.3,
}
```

La base doit etre:
- `Shipment.objects.filter(archived_at__isnull=True)`
- filtre date sur `created_at` avec `chart_start/chart_end`
- filtre `status` si fourni

Ajouter aussi au contexte:
- `chart_start`
- `chart_end`
- `chart_status_choices`
- `shipment_status`
- `shipments_total`
- `shipment_equivalent_total`

**Step 4: Run tests**

Run:
- `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_views_scan_dashboard.ScanDashboardViewTests -v 2`

Expected: PASS sur les tests KPI et graphique. Les tests HTML peuvent encore casser tant que le template n'est pas adapte.

**Step 5: Commit**

```bash
git add wms/views_scan_dashboard.py
git commit -m "feat(scan): aggregate dashboard shipment chart by destination"
```

### Task 5: Adapter le template dashboard et la couverture UI

**Files:**
- Modify: `templates/scan/dashboard.html`
- Modify: `wms/tests/views/tests_scan_bootstrap_ui.py`
- Modify: `wms/tests/views/tests_views_scan_dashboard.py`

**Step 1: Write the failing UI assertions**

Ajouter des assertions qui verifient:
- absence du selecteur legacy `id_period` dans la premiere carte;
- presence de `id_kpi_start` et `id_kpi_end` dans la carte KPI;
- presence de `id_shipment_status`, `id_chart_start` et `id_chart_end` dans la carte graphique;
- presence du nouveau titre `KPI`;
- rendu des colonnes/series du graphique par destination.

Exemples:

```python
self.assertContains(response, 'for="id_kpi_start"')
self.assertContains(response, 'for="id_chart_start"')
self.assertContains(response, 'name="shipment_status"')
self.assertNotContains(response, 'name="period"')
```

**Step 2: Run tests to verify they fail**

Run:
- `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui wms.tests.views.tests_views_scan_dashboard -v 2`

Expected: FAIL sur les nouveaux controles et le nouveau rendu HTML.

**Step 3: Update the template minimally**

Dans `templates/scan/dashboard.html`:
- retirer le champ `period` de la premiere carte;
- conserver `destination`;
- remplacer `activity_cards` par `kpi_cards`;
- ajouter un formulaire local a la carte KPI;
- ajouter un formulaire local a la carte graphique;
- rendre le graphique par destination avec deux pistes/barres ou deux colonnes lisibles par ligne.

Conserver les classes deja testees autant que possible:
- `scan-card card border-0`
- `scan-dashboard-filter-row`
- `scan-dashboard-filter-actions-inline`
- `scan-dashboard-field`

Ajouter de nouvelles variantes si necessaire plutot que casser les hooks existants.

**Step 4: Run tests**

Run:
- `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui wms.tests.views.tests_views_scan_dashboard -v 2`

Expected: PASS.

**Step 5: Commit**

```bash
git add templates/scan/dashboard.html wms/tests/views/tests_scan_bootstrap_ui.py wms/tests/views/tests_views_scan_dashboard.py
git commit -m "feat(scan): update dashboard kpi and shipment chart layout"
```

### Task 6: Verification finale et nettoyage

**Files:**
- Modify: none expected

**Step 1: Run focused verification**

Run:
- `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_views_scan_dashboard wms.tests.views.tests_scan_bootstrap_ui -v 2`
- `uv run ruff check wms/views_scan_dashboard.py wms/tests/views/tests_views_scan_dashboard.py wms/tests/views/tests_scan_bootstrap_ui.py`
- `git diff --check`

Expected:
- tests PASS;
- `ruff` PASS;
- `git diff --check` sans erreur d'espaces ou fin de ligne.

**Step 2: Final commit if verification changed files**

Si un formatteur ou une correction mineure modifie encore des fichiers:

```bash
git add -A
git commit -m "chore(scan): finalize dashboard reorg"
```
