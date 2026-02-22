# 04 - Bascule progressive, A/B testing et rollback

## 1) Principes de déploiement

- **Legacy first**: l'existant reste la référence tant que non validé.
- **Bascule par feature flag utilisateur**: activation contrôlée.
- **Rollback immédiat**: retour à legacy sans redéploiement.
- **Aucune migration destructive** avant validation finale.

## 2) Stratégie de coexistence

## 2.1 Routage

- Legacy:
  - `/scan/*`
  - `/portal/*`
- Nouveau front:
  - `/app/scan/*`
  - `/app/portal/*`

## 2.2 Switch global disponible à tout moment

- Depuis le header: `Interface actuelle` <-> `Nouveau front`.
- Préférence persistée par utilisateur.
- Override temporaire possible par paramètre URL (`?ui=legacy`).

## 3) Plan de bascule en 4 vagues

## Vague 1 - Groupe technique interne

- Utilisateurs: admin technique + qualité.
- Périmètre: dashboard, stock, création expédition.
- Durée mini: 2-3 jours.
- Critère: 0 bug bloquant.

## Vague 2 - Pilote métier restreint

- Utilisateurs: responsable entrepôt + 1-2 magasiniers.
- Périmètre: flux E2E complet.
- Durée mini: 5 jours ouvrés.
- Critère: KPI au moins équivalents au legacy.

## Vague 3 - Extension progressive

- Activation par rôle/site.
- Support renforcé + corrections rapides.
- Critère: stabilité confirmée.

## Vague 4 - Nouveau front par défaut

- `next` devient mode par défaut pour nouveaux comptes.
- Legacy reste disponible en fallback.

## 4) A/B testing (simple et utile)

## Segmentation

- Groupe A: legacy.
- Groupe B: next.

## Mesures comparées

- clics moyen par action clé,
- temps de création expédition,
- taux d'erreur validation,
- délai clôture,
- taux retour arrière entre écrans.

## Décision

- Maintien du next si KPI >= legacy et satisfaction métier validée.

## 5) Monitoring minimal obligatoire

- Erreurs front (JS runtime + API).
- Erreurs backend sur endpoints next.
- Latence API P95.
- Sync offline en échec.
- Taux d'abandon par écran.

## 6) Runbook rollback

## Déclencheurs rollback

- Incident bloquant opérationnel.
- Régression de validation métier.
- indisponibilité partielle prolongée.

## Procédure

1. Forcer `ui_mode=legacy` globalement (flag serveur).
2. Conserver les données créées (pas de rollback DB).
3. Bloquer temporairement l'accès `/app/*` si nécessaire.
4. Ouvrir ticket de correction et requalification.
5. Rebasculer progressivement après correctif.

## 7) Politique de suppression legacy

Interdite tant que ces conditions ne sont pas remplies:

- 100% flux critiques validés sur next,
- 0 incident bloquant sur une période continue définie,
- validation finale explicite de ta part.
