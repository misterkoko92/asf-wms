# P0 - Suite E2E de référence (parité Benev/Classique)

## Objectif

Définir la suite E2E cible qui valide la migration Next sans régression métier.

Acteurs prioritaires:

- responsable entrepôt,
- magasinier,
- admin qualité,
- utilisateur portail association.

## Workflows critiques retenus

1. Dashboard opérationnel.
2. Stock mobile: vue + MAJ.
3. Création colis.
4. Création expédition.
5. Affectation colis à expédition.
6. Suivi expédition.
7. Clôture expédition.
8. Parcours portail commande + documents.

## Préconditions communes

- jeu de données seed:
  - produits avec stock varié,
  - destinations + correspondants,
  - contacts expéditeur/destinataire/correspondant,
  - colis prêts et non affectés,
  - utilisateurs par rôle.
- environnement:
  - legacy disponible,
  - next parallèle activable via flag.

## Matrice scénarios

| ID | Parcours | Type | Préconditions | Étapes | Résultat attendu |
|---|---|---|---|---|---|
| E2E-001 | Dashboard triage | Happy path | user staff connecté | ouvrir dashboard, changer période, filtrer destination | KPI et widgets cohérents, aucun crash, liens actions valides |
| E2E-002 | Vue stock mobile | Happy path | user magasinier, stock présent | ouvrir stock, filtrer catégorie+entrepôt, trier alpha | liste conforme, tri/filtre stables, navigation fluide |
| E2E-003 | MAJ stock produit existant | Happy path | produit avec location par défaut | saisir produit, quantité, péremption, lot, valider | succès, mouvement stock visible, audit présent |
| E2E-004 | MAJ stock produit inconnu | Négatif | user staff | saisir produit absent, valider | erreur "Produit introuvable", aucune mutation |
| E2E-005 | MAJ stock sans emplacement | Négatif | produit sans `default_location` | soumettre formulaire valide | erreur bloquante "Emplacement requis", aucune mutation |
| E2E-006 | Création colis multi-lignes | Happy path | stock suffisant | ouvrir pack, saisir lignes, valider | colis créés, résultat pack affiché, statuts cohérents |
| E2E-007 | Création expédition complète | Happy path | contacts compatibles + cartons dispo | sélectionner destination/parties, lignes colis, créer | expédition créée, cartons affectés, statut synchronisé |
| E2E-008 | Save draft expédition | Happy path | destination valide | action `save_draft` | référence `EXP-TEMP-XX`, redirection édition |
| E2E-009 | Expédition avec contact incompatible | Négatif | contact hors destination | soumettre création | erreur de cohérence contact, pas de création |
| E2E-010 | Affectation colis déjà affecté ailleurs | Négatif | colis lié autre expédition | tentative affectation | erreur "Carton indisponible", aucune corruption |
| E2E-011 | Suivi progression nominale | Happy path | expédition prête | enchaîner étapes autorisées tracking | événements créés, statut expédition mis à jour |
| E2E-012 | Suivi transition interdite | Négatif | statut actuel incompatible | soumettre étape non autorisée | erreur de transition, pas d'événement |
| E2E-013 | Litige puis résolution | Edge | expédition en transit | `set_disputed`, vérifier blocage, `resolve_dispute` | progression bloquée puis remise `Prêt` |
| E2E-014 | Clôture expédition complète | Happy path | toutes étapes tracking complètes + no litige | action clôture | `closed_at` et `closed_by` renseignés |
| E2E-015 | Clôture expédition incomplète | Négatif | suivi incomplet | action clôture | refus clôture + message garde-fou |
| E2E-016 | Portal création commande | Happy path | profil association + destinataire actif | créer commande avec produits | commande créée, notifications envoyées |
| E2E-017 | Portal commande sans produit | Négatif | profil association | soumettre sans ligne | erreur "Ajoutez au moins un produit." |
| E2E-018 | Portal upload docs non approuvé | Négatif | order review_status != approved | upload doc | refus upload + message |

## Assertions de persistance (obligatoires)

- tables mutées attendues:
  - `ProductLot`, `StockMovement`,
  - `Carton`, `CartonStatusEvent`,
  - `Shipment`, `ShipmentTrackingEvent`,
  - `Order`, `OrderLine`, `OrderDocument`.
- absence de mutation en cas d'erreur bloquante.
- traçabilité utilisateur/horodatage présente.

## Pont avec tests d'intégration existants

Couverture déjà présente (non exhaustive):

- vues scan stock: `wms/tests/views/tests_views_scan_stock.py`
- vues scan expédition/suivi: `wms/tests/views/tests_views_scan_shipments.py`
- litige tracking: `wms/tests/views/tests_views_tracking_dispute.py`
- portail: `wms/tests/views/tests_views_portal.py`
- handlers expédition: `wms/tests/scan/tests_scan_shipment_handlers.py`
- handlers stock: `wms/tests/stock/tests_stock_handlers.py`
- formulaires: `wms/tests/forms/tests_forms.py`

## Dette de test à couvrir en migration Next

- E2E front réel sur `/app/*` (Playwright recommandé).
- tests offline mobile:
  - action en file locale,
  - resynchronisation,
  - gestion conflit.
- tests visuels de parité Benev/Classique (screenshot diff).

## Données/fixtures minimales

- 1 destination active avec correspondant imposé.
- 1 expéditeur compatible.
- 2 destinataires (1 compatible, 1 incompatible).
- 6 produits (stock OK, low, critique, sans location).
- 4 colis: 2 non affectés, 1 affecté, 1 expédié.
- 1 expédition livrée complète (clôturable).
- 1 expédition incomplète (non clôturable).

## Cadence d'exécution

- CI à chaque PR migration front/back:
  - smoke E2E (E2E-001, 003, 007, 011, 014, 016).
- nightly:
  - suite complète + scénarios négatifs.
