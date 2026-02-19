# Backlog

Backlog aligné avec l'audit global du **19/02/2026** (`docs/audit_2026-02-19.md`).

## 1) Baseline livrée (référence)

- Catalogue produits, catégories, tags, dimensions, QR.
- Imports produits/contacts/destinations.
- Stock par lots + traçabilité mouvements.
- Cycle colis avec état `étiquetté`.
- Cycle expédition avec suivi et litige (`is_disputed`).
- Flux brouillon expédition (`EXP-TEMP-XX`) et promotion auto vers référence finale.
- Portail associations (compte, destinataires, commandes).
- Synchro destinataires portail -> contacts WMS.
- Vue Suivi expéditions (filtres semaine/clos + clôture dossier).

## 2) Phase 0 - Stabilisation release (priorité immédiate)

- [ ] Repasser la suite complète de tests au vert (8 régressions actuelles).
- [ ] Harmoniser les tests avec les nouvelles règles:
  - tags pré-seedés (`Destinataire`, `Expéditeur`),
  - blocage portail sans destinataire de réception,
  - libellés accentués.
- [ ] Nettoyer le lot de changements courant (migrations 0048/0049, statiques portail) et sécuriser le process de merge.
- [ ] Formaliser la gate de release: `test`, `check --deploy`, `migrate-check`, `ruff`, `bandit`.

## 3) Phase 1 - Durcissement domaine contacts/portail

- [x] Clarifier la source de vérité destination (M2M `destinations`) et plan de retrait du FK legacy `destination`.
  - utilitaires dédiés de portée destinations (`contacts/destination_scope.py`)
  - commande d'audit/correction: `python manage.py audit_contact_destinations [--apply]`
- [x] Réduire la duplication `AssociationRecipient` (`name/structure_name`, `email/emails`, `phone/phones`) avec normalisation applicative.
- [x] Renforcer les invariants de synchro portail -> contacts (idempotence, non-régression).
- [x] Compléter les tests métier bout-en-bout:
  - portail -> commande -> validation admin -> expédition préremplie.

## 4) Phase 2 - Nettoyage architecture / legacy

- [x] Découper `wms/models.py` en modules par agrégat.
  - façade de compatibilité conservée dans `wms/models.py`
  - modules domaine: `wms/models_domain/catalog.py`, `inventory.py`, `shipment.py`, `portal.py`, `integration.py`
- [x] Découper `wms/admin.py` et `wms/views_scan_shipments.py` pour baisser la complexité.
  - extraction des enregistrements admin peu couplés vers `wms/admin_misc.py`
  - extraction des helpers de page expédition vers `wms/views_scan_shipments_support.py`
- [x] Encadrer puis retirer progressivement les chemins legacy restants.
  - endpoint legacy suivi expédition (`/scan/shipment/track/<reference>/`) encadré par feature-flag `ENABLE_SHIPMENT_TRACK_LEGACY`
  - headers de dépréciation ajoutés sur la route legacy + journalisation serveur
  - export contacts aligné sur la source de vérité `contact_destination_ids` (M2M prioritaire)
- [x] Uniformiser libellés FR/accents et conventions métier.
  - libellés harmonisés (expéditeur, étiquettes, accès, approuvé/refusé) sur scan/admin

## 5) Phase 3 - Observabilité et exploitation

- [x] Dashboard technique (queue emails, litiges, blocages workflow).
  - cartes dashboard ajoutées: queue email (pending/processing/failed/timeout), blocages workflow >72h, suivi SLA.
- [x] Journalisation métier structurée des transitions de statuts.
  - logs JSON `wms.workflow` pour transitions colis/expéditions, actions litige, événements de suivi et clôture dossier.
- [x] Monitoring des SLA (planifié -> expédié -> reçu escale -> livré).
  - segments SLA visibles dans le dashboard avec ratio dépassements / segments complétés.
- [x] Playbooks incidents enrichis et testés.
  - runbook mis à jour (queue, blocages workflow, SLA, logs) + tests ciblés ajoutés.

## 6) Cibles V2 (propositions)

- [ ] Moteur de workflow statuts configurable.
- [ ] Centre litiges (motifs, timeline, résolution guidée).
- [ ] SLA opérationnels + alertes proactives.
- [ ] Intégration planning/vols (capacité, planning prévisionnel).
- [ ] API v2 orientée intégration externe (CRM/BI/ops).
- [ ] Portail association enrichi (suivi dossier détaillé, notifications fines).
- [ ] Étude d'une application contacts transverse ASF (référentiel unique multi-missions).
