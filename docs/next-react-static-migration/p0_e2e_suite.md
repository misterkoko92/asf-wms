# P0 - Suite E2E de reference (parite Benev/Classique)

## Contexte du document

Matrice initiale definie en P0, puis synchronisee au 2026-02-23 avec les tests effectivement en place.

## Objectif

Valider la migration Next sans regression metier sur:

- flux scan critique,
- flux portal association,
- robustesse des erreurs bloquantes.

## Niveaux de validation cibles

- niveau 1: tests API (workflow bout en bout via endpoints UI),
- niveau 2: tests UI navigateur (Playwright sur `/app/*`),
- niveau 3: recette metier manuelle.

## Matrice scenarios et couverture actuelle

| ID | Parcours | Type | Couverture actuelle | Statut |
|---|---|---|---|---|
| E2E-001 | Dashboard triage | Happy path | API endpoint tests | COVERED_API |
| E2E-002 | Vue stock mobile | Happy path | API endpoint tests | COVERED_API |
| E2E-003 | MAJ stock produit existant | Happy path | `tests_ui_endpoints` | COVERED_API |
| E2E-004 | MAJ stock produit inconnu | Negatif | `tests_ui_endpoints` | COVERED_API |
| E2E-005 | MAJ stock sans emplacement | Negatif | `tests_ui_endpoints` | COVERED_API |
| E2E-006 | Creation colis multi-lignes | Happy path | indirect via creation expedition | PARTIAL_API |
| E2E-007 | Creation expedition complete | Happy path | `tests_ui_endpoints` + E2E API | COVERED_API |
| E2E-008 | Save draft expedition | Happy path | non implemente en UI/API dediee | TODO |
| E2E-009 | Expedition avec contact incompatible | Negatif | `tests_ui_endpoints` | COVERED_API |
| E2E-010 | Affectation colis deja affecte ailleurs | Negatif | `tests_ui_endpoints` | COVERED_API |
| E2E-011 | Suivi progression nominale | Happy path | `tests_ui_endpoints` + E2E API | COVERED_API |
| E2E-012 | Suivi transition interdite | Negatif | `tests_ui_endpoints` | COVERED_API |
| E2E-013 | Litige puis resolution | Edge | partiel (bloquage par litige couvert) | PARTIAL_API |
| E2E-014 | Cloture expedition complete | Happy path | `tests_ui_endpoints` + E2E API | COVERED_API |
| E2E-015 | Cloture expedition incomplete | Negatif | `tests_ui_endpoints` | COVERED_API |
| E2E-016 | Portal creation commande | Happy path | `tests_ui_endpoints` + E2E API | COVERED_API |
| E2E-017 | Portal commande sans produit | Negatif | `tests_ui_endpoints` | COVERED_API |
| E2E-018 | Portal upload docs non approuve | Negatif | non couvert dans suite UI API actuelle | TODO |

## Assertions de persistance (obligatoires)

- tables mutables:
  - `ProductLot`, `StockMovement`,
  - `Carton`, `CartonStatusEvent`,
  - `Shipment`, `ShipmentTrackingEvent`,
  - `Order`, `OrderLine`, `OrderDocument`,
  - `PrintTemplate`, `PrintTemplateVersion`.
- absence de mutation en cas d'erreur bloquante.
- tracabilite utilisateur + horodatage.

## References tests (etat reel)

- `api/tests/tests_ui_serializers.py`
- `api/tests/tests_ui_endpoints.py`
- `api/tests/tests_ui_e2e_workflows.py`
- `docs/next-react-static-migration/2026-02-23_p2_e2e_suite_increment5.md`

## Dette restante avant validation finale parite

- lancer Playwright sur routes `/app/*` (tests UI reels),
- couvrir explicitement les scenarios TODO/PARTIAL ci-dessus,
- ajouter tests offline/sync (PWA) quand le socle offline sera implemente,
- executer recette metier manuelle complete ecran par ecran.

## Cadence recommandee

- a chaque PR P2/P3:
  - `api.tests.tests_ui_serializers`
  - `api.tests.tests_ui_endpoints`
  - `api.tests.tests_ui_e2e_workflows`
- nightly:
  - suite API complete + (des que dispo) suite Playwright.
