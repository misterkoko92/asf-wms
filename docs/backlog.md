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
  - tags pré-seedés (`Destinataire`, `Expediteur`),
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

- [ ] Découper `wms/models.py` en modules par agrégat.
- [ ] Découper `wms/admin.py` et `wms/views_scan_shipments.py` pour baisser la complexité.
- [ ] Encadrer puis retirer progressivement les chemins legacy restants.
- [ ] Uniformiser libellés FR/accents et conventions métier.

## 5) Phase 3 - Observabilité et exploitation

- [ ] Dashboard technique (queue emails, litiges, blocages workflow).
- [ ] Journalisation métier structurée des transitions de statuts.
- [ ] Monitoring des SLA (planifié -> expédié -> reçu escale -> livré).
- [ ] Playbooks incidents enrichis et testés.

## 6) Cibles V2 (propositions)

- [ ] Moteur de workflow statuts configurable.
- [ ] Centre litiges (motifs, timeline, résolution guidée).
- [ ] SLA opérationnels + alertes proactives.
- [ ] Intégration planning/vols (capacité, planning prévisionnel).
- [ ] API v2 orientée intégration externe (CRM/BI/ops).
- [ ] Portail association enrichi (suivi dossier détaillé, notifications fines).
- [ ] Étude d'une application contacts transverse ASF (référentiel unique multi-missions).
