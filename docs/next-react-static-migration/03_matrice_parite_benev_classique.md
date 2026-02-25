# 03 - Matrice de parite Benev/Classique (maj 2026-02-25)

## Legende statut

- `TODO`: ni ecran Next exploitable, ni couverture de parite.
- `API_READY`: backend/UI API disponible et teste, mais ecran Next non implemente.
- `IN_PROGRESS`: ecran Next present et/ou branche partiellement, parite stricte non validee.
- `DONE`: parite fonctionnelle + visuelle validee.

## Resume global (snapshot)

- Ecrans Next disponibles aujourd'hui: `dashboard`, `stock`, `cartons`, `shipment-create`, `shipments-ready`, `shipments-tracking`, `shipment-documents`, `templates`, `portal-dashboard`.
- API UI disponible et testee pour: stock, cartons, expedition (ready/create/update/tracking/close), docs/labels, templates, portal mutations.
- Aucun ecran n'est encore `DONE` (parite stricte non validee).

## A. Scan - ecrans prioritaires et coeur metier

| Priorite | Legacy URL | Route Next cible | Etat Next reel | Etat API UI | Statut |
|---|---|---|---|---|---|
| P1 | `/scan/dashboard/` | `/app/scan/dashboard/` | ecran present, KPI/timeline/actions branches en live API | `GET /api/v1/ui/dashboard/` | IN_PROGRESS |
| P1 | `/scan/stock/` | `/app/scan/stock/` | ecran present (filtres recherche/categorie/entrepot/tri + table live + mutations update/out branchees) | `GET /api/v1/ui/stock/` | IN_PROGRESS |
| P1 | `/scan/stock-update/` | `/app/scan/stock/` (zone MAJ inline cible) | workflow UI mutation present et teste en navigateur | `POST /api/v1/ui/stock/update/` | IN_PROGRESS |
| P1 | `/scan/out/` | `/app/scan/stock/` (zone sortie cible) | workflow UI mutation present et teste en navigateur | `POST /api/v1/ui/stock/out/` | IN_PROGRESS |
| P1 | `/scan/shipment/` | `/app/scan/shipment-create/` | ecran present + mutations create(travail carton ou produit)/tracking/close branchees | `GET/POST/PATCH /api/v1/ui/shipments*` | IN_PROGRESS |
| P1 | `/scan/shipments-tracking/` | `/app/scan/shipments-tracking/` | route dediee presente, table live + filtres (semaine/clos) + workflow tracking branches et testes | `GET /api/v1/ui/shipments/tracking/` + `POST /api/v1/ui/shipments/<id>/tracking-events/` | IN_PROGRESS |
| P1 | `/scan/shipment/<id>/close` (logique legacy) | `/app/scan/shipments-tracking/` (integration transitoire) | workflow cloture present sur route dediee suivi | `POST /api/v1/ui/shipments/<id>/close/` | IN_PROGRESS |
| P1 | `/scan/pack/` | `/app/scan/shipment-create/` (integration transitoire) | creation colis inline via produit+quantite presente sur shipment-create | logique disponible via handlers legacy + API shipment lines | IN_PROGRESS |
| P1 | `/scan/cartons/` | `/app/scan/cartons/` | route dediee presente, table colis branchee et testee | `GET /api/v1/ui/cartons/` | IN_PROGRESS |
| P1 | `/scan/shipments-ready/` | `/app/scan/shipments-ready/` | route dediee presente, table expeditions branchee et testee | `GET /api/v1/ui/shipments/ready/` | IN_PROGRESS |
| P2 | `/scan/orders-view/` | `/app/scan/orders/` | route non creee | pas d'endpoint UI dedie | TODO |
| P2 | `/scan/orders/` | `/app/scan/order/` | route non creee | pas d'endpoint UI dedie | TODO |
| P2 | `/scan/receipts/` | `/app/scan/receipts/` | route non creee | pas d'endpoint UI dedie | TODO |
| P2 | `/scan/receive/` | `/app/scan/receive/` | route non creee | pas d'endpoint UI dedie | TODO |
| P2 | `/scan/receive-pallet/` | `/app/scan/receive-pallet/` | route non creee | pas d'endpoint UI dedie | TODO |
| P2 | `/scan/receive-association/` | `/app/scan/receive-association/` | route non creee | pas d'endpoint UI dedie | TODO |
| P2 | `/scan/settings/` | `/app/scan/settings/` | route non creee | pas d'endpoint UI dedie | TODO |
| P2 | `/scan/faq/` | `/app/scan/faq/` | route non creee | n/a (contenu statique) | TODO |
| P3 | `/scan/import/` | `/app/scan/import/` | route non creee | pas d'endpoint UI dedie | TODO |

## B. Scan - documents et templates

| Priorite | Legacy URL | Route Next cible | Etat Next reel | Etat API UI | Statut |
|---|---|---|---|---|---|
| P2 | `/scan/shipment/<id>/documents/upload/` | `/app/scan/shipment-documents/` | workflow charge/upload/suppression present | `GET/POST /api/v1/ui/shipments/<id>/documents/` | IN_PROGRESS |
| P2 | `/scan/shipment/<id>/documents/<id>/delete/` | `/app/scan/shipment-documents/` | suppression present | `DELETE /api/v1/ui/shipments/<id>/documents/<doc_id>/` | IN_PROGRESS |
| P2 | `/scan/shipment/<id>/labels/` | `/app/scan/shipment-documents/` | ouverture labels presente | `GET /api/v1/ui/shipments/<id>/labels/` | IN_PROGRESS |
| P2 | `/scan/shipment/<id>/labels/<carton_id>/` | `/app/scan/shipment-documents/` | ouverture label carton presente | `GET /api/v1/ui/shipments/<id>/labels/<carton_id>/` | IN_PROGRESS |
| P3 | `/scan/templates/` | `/app/scan/templates/` | liste templates + selection doc type presente | `GET /api/v1/ui/templates/` | IN_PROGRESS |
| P3 | `/scan/templates/<doc_type>/` | `/app/scan/templates/` | edition JSON + save/reset + versions visible | `GET/PATCH /api/v1/ui/templates/<doc_type>/` | IN_PROGRESS |

## C. Portal (associations)

| Priorite | Legacy URL | Route Next cible | Etat Next reel | Etat API UI | Statut |
|---|---|---|---|---|---|
| P1 | `/portal/` | `/app/portal/dashboard/` | ecran present (mix maquette + live API) | `GET /api/v1/ui/portal/dashboard/` | IN_PROGRESS |
| P1 | `/portal/orders/new/` | `/app/portal/dashboard/` (integration transitoire) | workflow creation commande present sur dashboard | `POST /api/v1/ui/portal/orders/` | IN_PROGRESS |
| P1 | `/portal/orders/<id>/` | `/app/portal/orders/detail/?id=<id>` | route non creee | partiel (dashboard expose liste, pas detail endpoint dedie) | TODO |
| P2 | `/portal/recipients/` | `/app/portal/dashboard/` (integration transitoire) | workflows create/update presents sur dashboard | `GET/POST/PATCH /api/v1/ui/portal/recipients*` | IN_PROGRESS |
| P2 | `/portal/account/` | `/app/portal/dashboard/` (integration transitoire) | workflow update compte present sur dashboard | `GET/PATCH /api/v1/ui/portal/account/` | IN_PROGRESS |
| P2 | `/portal/change-password/` | `/app/portal/change-password/` | conserve en legacy | n/a | TODO |
| P2 | `/portal/login/` | `/app/portal/login/` | auth reste Django legacy | n/a | TODO |
| P2 | `/portal/logout/` | `/app/portal/logout/` | auth reste Django legacy | n/a | TODO |
| P3 | `/portal/request-account/` | `/app/portal/request-account/` | route non creee | pas d'endpoint UI dedie | TODO |
| P3 | `/portal/set-password/<uid>/<token>/` | `/app/portal/set-password/?...` | route non creee | pas d'endpoint UI dedie | TODO |

## D. Routes dynamiques scan (strategie statique)

Principe cible: route stable + query params.

| Legacy | Cible Next | Statut |
|---|---|---|
| `/scan/shipment/<id>/edit/` | `/app/scan/shipment/edit/?id=<id>` | TODO |
| `/scan/shipment/track/<token>/` | `/app/scan/shipment/track/?token=<token>` | TODO |
| `/scan/shipment/track/<ref>/` | `/app/scan/shipment/track/?ref=<ref>` | TODO |
| `/scan/carton/<id>/doc/` | `/app/scan/carton/doc/?id=<id>` | TODO |
| `/scan/carton/<id>/picking/` | `/app/scan/carton/picking/?id=<id>` | TODO |

## E. Checklist de sortie pour passer un ecran en DONE

- [ ] memes champs obligatoires et memes valeurs par defaut
- [ ] memes validations bloquantes et memes erreurs metier
- [x] memes permissions par role (staff/association/admin/superuser) sur endpoints UI exposes
- [ ] memes statuts metier et transitions
- [ ] memes actions critiques disponibles (ou moins de clics, sans perte de controle)
- [ ] meme comportement documentaire (liens, PDF, labels)
- [ ] parite visuelle Benev/Classique validee

## F. Validation test (etat actuel)

- [x] tests contrats serializers: `api/tests/tests_ui_serializers.py`
- [x] tests endpoints UI: `api/tests/tests_ui_endpoints.py`
- [x] matrice role par role (admin/qualite/magasinier/benevole/livreur/association/superuser): `api/tests/tests_ui_endpoints.py`
- [x] E2E API bout en bout: `api/tests/tests_ui_e2e_workflows.py`
- [x] harness E2E navigateur `/app/*` disponible: `wms/tests/core/tests_ui.py::NextUiTests` (commande `make test-next-ui`)
- [x] workflows navigateur docs/templates (upload+delete documents, save+reset templates): `wms/tests/core/tests_ui.py::NextUiTests`
- [x] workflow navigateur stock mutations (update/out): `wms/tests/core/tests_ui.py::NextUiTests`
- [x] workflow navigateur filtres stock (recherche): `wms/tests/core/tests_ui.py::NextUiTests`
- [x] workflow navigateur dashboard live (timeline + actions): `wms/tests/core/tests_ui.py::NextUiTests`
- [x] workflow navigateur expedition mutations (create/tracking/close): `wms/tests/core/tests_ui.py::NextUiTests`
- [x] workflow navigateur creation colis inline (produit+quantite) sur shipment-create: `wms/tests/core/tests_ui.py::NextUiTests`
- [x] workflow navigateur route dediee vue expeditions (`/app/scan/shipments-ready/`): `wms/tests/core/tests_ui.py::NextUiTests`
- [x] workflow navigateur route dediee suivi expedition (`/app/scan/shipments-tracking/`) + presence liste live: `wms/tests/core/tests_ui.py::NextUiTests`
- [x] workflow navigateur route dediee vue colis (`/app/scan/cartons/`): `wms/tests/core/tests_ui.py::NextUiTests`
- [x] workflow navigateur portal mutations (order create, recipient create/update, account patch): `wms/tests/core/tests_ui.py::NextUiTests`
- [x] execution reguliere E2E navigateur sur environnement cible (GitHub Actions `next-ui-browser-e2e.yml`, Playwright Chromium)
- [ ] recette metier manuelle complete ecran par ecran
- [x] rollback global instantane vers legacy (`/ui/mode/legacy/`)
