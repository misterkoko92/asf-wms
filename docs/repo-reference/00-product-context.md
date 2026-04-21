# Product Context (asf-wms)

Lis ce document en premier avant toute intervention significative. Il décrit la raison d'être du projet, ses utilisateurs, son état réel en production et ses contraintes. Les autres fichiers de `docs/repo-reference/` décrivent le *comment* technique ; celui-ci décrit le *pourquoi* et le *pour qui*.

> Dernière mise à jour : 2026-04-21

## Mission et domaine

- **Association** : ASF (Aviation Sans Frontières — branche Messagerie Médicale, `messmed`)
- **Activité** : expédition de colis humanitaires internationaux, essentiellement médicaux
  - ~90 % de matériel médical
  - ~10 % incluent des médicaments (contexte pharmaceutique sensible)
- **Deux types d'usage** :
  1. Expéditions au nom d'ASF
  2. Service offert à d'autres associations qui utilisent la plateforme pour leurs propres expéditions
- **Bénéficiaires finaux** : associations humanitaires partenaires et leurs bénéficiaires dans les pays d'arrivée
- **Cadre réglementaire** :
  - **Douanes France** (export)
  - **Douanes pays destinataire** (import, variable selon le pays)
  - **RGPD** (données personnelles de contacts, bénévoles, destinataires)
  - **Médicaments** : réglementation pharmaceutique possible sur certaines expéditions

## Production

- **URL** : https://messmed.pythonanywhere.com/
- **Hébergement** : PythonAnywhere, **offre gratuite**
  - Contrainte : 1 seul processus web, pas de worker séparé, CPU throttlé, disque 512 Mo
  - Tâches de fond via `scheduled tasks` PythonAnywhere (commandes management en polling)
- **Base de données** : MySQL fourni par PythonAnywhere (taille inconnue, estimée petite)
- **Media files** : filesystem local PythonAnywhere
- **Pas d'environnement de staging** — tout va directement en production après merge

## Processus de déploiement

- Branches de développement créées par Codex ou Claude Code
- PR ouvertes avec CI GitHub Actions (ruff, mypy, pyright, bandit, tests, coverage 93 %)
- Quand la CI est verte, Edouard demande le merge à l'assistant
- Nettoyage des branches après merge
- Déploiement effectif : étape manuelle sur PythonAnywhere (à clarifier — probablement `git pull` + `migrate` + reload webapp)

## Utilisateurs et interfaces

| Interface | URL | Utilisateurs |
|-----------|-----|--------------|
| `/scan/` | PWA entrepôt | Responsable entrepôt ASF + bénévoles préparateurs (interne ASF) |
| `/portal/` | Self-service | Associations expéditrices + destinataires à l'étranger |
| `/benevole/` | Coordination | Bénévoles qui font la mise à bord (embarquement des colis) |
| `/planning/` | Planification vols | Coordinateurs internes ASF |
| `/admin/` | Django admin | 2 utilisateurs internes ASF (Edouard + 1 autre) |

### Population

- **~30 bénévoles actifs** (rotation probable)
- **~20 associations partenaires expéditrices**
- **~100 destinataires** (associations à l'étranger)
- **~300 contacts uniques** en base (estimation)
- **Profils numériques variables** — bénévoles pas forcément à l'aise avec le numérique, aisance numérique des associations étrangères très variable

## Volume actuel

- **~15 expéditions / semaine**
- **~170 colis / mois**
- **Implication** : volume faible. Les problématiques de *scalabilité pure* (cache Redis, Celery, object storage, sessions cached, sharding) ne sont **pas prioritaires**. Les problématiques de *fiabilité*, *traçabilité*, *conformité* et *ergonomie* dominent.

## Données manipulées (pertinent pour RGPD)

| Catégorie | Exemples | Sensibilité |
|-----------|----------|-------------|
| Contacts expéditeurs | Nom asso, emails, téléphones | Standard |
| Contacts destinataires | Nom, adresse, téléphone, email, pays | Standard + transferts hors UE probables |
| Bénévoles | Compte, rôle, emails | Standard |
| Contenu colis | Description matériel médical, médicaments | **Sensible** (pharma + douane) |
| Documents scannés | Attestations, factures, documents douaniers | **Sensible** |
| Données bancaires | Non détectées en base (à confirmer) | — |
| Données de santé | Non — pas de patients individuels | — |
| Mineurs | **Non** | — |

**Points critiques RGPD** :
- Transferts hors UE (destinataires dans pays non-UE) → encadrement contractuel nécessaire
- Sous-traitants : PythonAnywhere (US/UK), Brevo (FR), Microsoft Graph (US — OneDrive), AF-KLM API
- Durées de conservation : à définir (contraintes douanières = conservation longue probable des documents d'expédition)

## Équipe

- **Edouard (créateur)** : non-développeur, assisté par Codex et Claude Code
- Potentiellement 1-2 autres personnes à terme
- Bascule en cours vers **Claude Code 100 %** (Codex en retrait)

## Budget

- **Très contraint** : < 30 € / mois
- Idéal : 0 € (offres gratuites)
- Implication : éviter tout outil/service qui pousse sur un palier payant à court terme

## Intégrations externes

| Service | Usage | Criticité | Coût |
|---------|-------|-----------|------|
| **Brevo** | Envoi emails transactionnels (API REST) | Haute | Freemium (300 emails/jour gratuit) |
| **Microsoft Graph** (OneDrive) | Conversion XLSX→PDF et stockage partagé | Moyenne | Inclus licence Microsoft 365 de l'asso |
| **ECB (Banque centrale euro)** | Taux de change quotidiens pour facturation | Basse | Gratuit (API publique) |
| **Air France-KLM Flight Status** | Statut vols pour planning | Moyenne | Gratuit (opendata) |
| **WhatsApp Web (wa.me)** | Génération de liens de brouillon message | Basse | Gratuit |
| **API interne (`X-ASF-Integration-Key`)** | Intégrations tierces éventuelles | Optionnelle | — |

## État de la production et incidents

- Plusieurs bugs corrigés au fil de l'eau
- Plusieurs refontes de schéma DB (visible dans les migrations, 126+)
- Pas de stack de monitoring — les incidents sont remontés par les utilisateurs

## Features IA envisagées (à clarifier)

Edouard envisage des features IA à terme, orientations probables :

1. **Anticipation de la préparation des colis** — prédire à l'avance quels produits préparer (basé historique expéditions, saison, destination)
2. **Assistance à la gestion du planning d'expédition** — optimisation combinatoire vols/colis (ortools déjà présent dans les dépendances)

Non encore décidé. Contraintes probables :
- Budget très limité → prompt caching Anthropic indispensable
- Pas de données personnelles envoyées aux API externes sans pseudonymisation (RGPD)
- Traçage des appels IA via `IntegrationEvent` pour observabilité des coûts

## Priorités actuelles (2026-04-21)

**Objectif n°1** : finaliser une version production 100 % utilisable.

Cela implique : stabilité, conformité RGPD et douanière, ergonomie suffisante pour les profils non-techniques, traçabilité des actions sensibles. La performance et la scalabilité sont **secondaires** tant que le volume reste à ~170 colis/mois.

## Ce que ce contexte change pour les agents

Lorsque tu proposes une évolution ou un fix, garde en tête :

- **Volume faible** → pas de refacto pour la scalabilité
- **Budget serré** → prioriser outils gratuits (Sentry free tier, GitHub free, offres freemium suffisantes)
- **Solo + non-dev** → éviter les architectures qui demandent une équipe pour être maintenues
- **Humanitaire + douane** → la traçabilité (qui a fait quoi, quand) est un besoin fonctionnel, pas un luxe
- **RGPD + transferts hors UE** → toute nouvelle collecte de données doit être réfléchie
- **PythonAnywhere Free** → pas de worker séparé, pas de Redis, pas de cron natif au-delà des scheduled tasks
- **Pas de staging** → les changements risqués ont besoin d'un filet (feature flags, rollback rapide)
- **Bascule vers Claude Code 100 %** → les workflows devraient s'adapter (skills custom, hooks, slash commands pour automatiser les tâches répétitives d'Edouard)

## À clarifier

- Durées de conservation des données (contraintes douanières vs. RGPD)
- Procédure exacte de déploiement PythonAnywhere (documentée où ?)
- DPO de l'association (qui est référent RGPD ?)
- Statut juridique précis d'ASF Messagerie Médicale (branche autonome ? association loi 1901 ? reconnue d'utilité publique ?)
- Mentions légales et CGU existantes ? (hors repo ?)
