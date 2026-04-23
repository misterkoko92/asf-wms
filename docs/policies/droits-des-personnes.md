# Procedure interne - Droits des personnes

Statut : **brouillon operationnel a valider juridiquement / RGPD**.

Version de travail : 2026-04-22.

Cette procedure decrit comment traiter une demande d'exercice de droits RGPD dans
le contexte ASF WMS. Elle doit etre validee par le referent RGPD ou DPO avant
usage officiel.

## 1) Droits couverts

Selon le contexte et la base legale applicable, une personne peut demander :

- l'acces aux donnees qui la concernent ;
- la rectification de donnees inexactes ou incompletes ;
- l'effacement lorsque la conservation n'est plus justifiee ;
- la limitation du traitement ;
- l'opposition lorsque le traitement le permet ;
- la portabilite des donnees fournies, lorsque ce droit est applicable.

Le droit applicable peut varier selon la base legale, les obligations douanieres,
comptables, de securite ou de preuve. Une demande ne signifie donc pas toujours
que la suppression immediate est possible.

## 2) Canal de reception

Canal cible : [adresse email RGPD a completer].

Canaux possibles :

- email direct ;
- formulaire de contact ;
- demande transmise par un utilisateur interne ;
- demande recue par courrier ou par une association partenaire.

Toute demande recue hors canal officiel doit etre transferee au referent RGPD et
tracee.

## 3) Delais

Objectif interne :

- accuser reception sous 7 jours ;
- repondre dans un delai maximum d'un mois ;
- si la demande est complexe, informer la personne dans le delai d'un mois de la
  prolongation et de sa raison.

Le delai exact et les cas de prolongation doivent etre confirmes avec le validateur
RGPD.

## 4) Journal de suivi

Chaque demande doit etre tracee dans un registre interne, hors depot public si elle
contient des donnees personnelles.

Champs recommandes :

- identifiant de demande ;
- date de reception ;
- canal ;
- demandeur ;
- type de droit demande ;
- personne concernee ;
- preuve d'identite ou verification effectuee, si necessaire ;
- perimetre recherche ;
- responsable interne ;
- date de reponse ;
- decision ;
- justification si refus total ou partiel ;
- actions realisees ;
- pieces transmises ;
- date de cloture.

## 5) Verification de l'identite

Avant de communiquer, corriger ou supprimer des donnees, verifier que le demandeur
est bien la personne concernee ou dispose d'un mandat valable.

Regles pratiques :

- ne demander une piece justificative que si l'identite ne peut pas etre verifiee
  autrement ;
- ne conserver qu'une trace minimale de la verification ;
- ne jamais envoyer de donnees personnelles a une adresse non verifiee ;
- si la demande concerne une structure ou association, verifier le role du
  demandeur dans cette structure.

## 6) Recherche des donnees

Selon le profil, rechercher dans :

- comptes utilisateurs et groupes ;
- demandes de compte public ;
- contacts et structures expediteurs ;
- destinataires, correspondants et autorisations ;
- expeditions, colis, documents et historiques ;
- emails transactionnels et files d'attente ;
- journaux techniques et evenements d'integration ;
- exports temporaires connus.

Ne pas exporter de dump complet de production pour repondre a une demande. Produire
un export cible, limite au perimetre de la demande.

## 7) Droit d'acces

Procedure :

1. Identifier la personne et son role.
2. Rechercher les donnees la concernant.
3. Ecarter ou masquer les donnees concernant des tiers lorsque necessaire.
4. Produire un export lisible et proportionne.
5. Faire relire l'export par une personne habilitee.
6. Transmettre par un canal securise.
7. Tracer la reponse et la date d'envoi.

Format recommande :

- PDF ou document lisible pour les informations narratives ;
- CSV ou JSON pour les donnees structurees si la personne le demande et si le
  format est adapte ;
- liste des categories de donnees, finalites, destinataires et durees de
  conservation lorsque pertinent.

## 8) Rectification

Procedure :

1. Identifier la donnee incorrecte.
2. Verifier la nouvelle valeur.
3. Corriger depuis la surface metier appropriee lorsque possible.
4. Conserver une trace si la correction affecte un dossier operationnel, douanier
   ou deja transmis.
5. Informer les destinataires internes ou tiers si la correction est necessaire et
   proportionnee.

## 9) Effacement ou anonymisation

Procedure :

1. Identifier toutes les donnees concernees.
2. Verifier les obligations de conservation applicables.
3. Distinguer les donnees supprimables, anonymisables et a conserver.
4. Supprimer les exports temporaires et fichiers non necessaires.
5. Anonymiser les donnees lorsque le dossier doit rester conserve.
6. Tracer la justification d'un refus partiel ou total.
7. Informer la personne de l'issue.

Exemples de limites possibles :

- dossier d'expedition encore actif ;
- obligation douaniere, comptable ou de preuve ;
- donnees concernant aussi d'autres personnes ou structures ;
- obligation de securite ou de conservation d'un journal minimal.

## 10) Opposition et limitation

Si la personne s'oppose a un traitement ou demande sa limitation :

1. Identifier le traitement vise.
2. Verifier la base legale.
3. Suspendre ou limiter ce qui peut l'etre sans compromettre une obligation
   applicable.
4. Documenter les motifs si le traitement doit continuer.
5. Informer la personne.

## 11) Portabilite

Le droit a la portabilite ne s'applique pas a toutes les donnees. Il concerne en
principe les donnees fournies par la personne, traitees de maniere automatisee, et
sur une base legale compatible avec ce droit.

Procedure :

1. Identifier les donnees fournies par la personne.
2. Exclure les donnees internes, deduites, historiques d'audit ou donnees de tiers
   lorsque necessaire.
3. Produire un format structure et lisible par machine lorsque possible.
4. Transmettre de maniere securisee.

## 12) Refus ou demande excessive

Une demande peut etre refusee ou limitee lorsqu'elle est manifestement infondee,
excessive, impossible a satisfaire sans porter atteinte aux droits d'autrui, ou
incompatible avec une obligation de conservation.

Tout refus total ou partiel doit etre :

- motive ;
- trace ;
- communique a la personne ;
- assorti de l'information sur la possibilite de reclamation aupres de la CNIL.

## 13) Violation de donnees detectee pendant une demande

Si la demande revele une fuite, une erreur d'envoi, un acces indu ou une perte de
donnees :

1. passer en procedure incident ;
2. prevenir le referent RGPD ;
3. contenir le risque ;
4. evaluer les personnes et donnees concernees ;
5. decider si une notification CNIL ou personnes concernees est requise ;
6. tracer les decisions et actions.

## 14) Backlog technique

Pour rendre cette procedure plus robuste, prevoir :

- une commande `export_personal_data <email>` ;
- une commande `anonymize_personal_data <email>` ou workflow equivalent ;
- une purge ou revue periodique des exports temporaires ;
- un registre interne des demandes, stocke hors depot public ;
- des modeles de reponse valides juridiquement.
