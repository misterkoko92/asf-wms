# Politique RGPD et donnees sensibles

Statut : **brouillon operationnel a valider juridiquement**.

Ce document trace le cadre RGPD utilise par ASF WMS pour les donnees personnelles,
documents sensibles et transferts hors UE. Il sert de registre de travail pour les
releases et les decisions produit. Il ne remplace pas la validation du referent
RGPD, du DPO le cas echeant, ni des textes juridiques visibles par les utilisateurs.

## 1) Perimetre

Application concernee : ASF WMS, utilisee pour la Messagerie Medicale d'Aviation
Sans Frontieres.

Surfaces concernees :

- `/scan/` : operations internes entrepot ASF.
- `/portal/` : associations expediteurs et destinataires.
- `/benevole/` : coordination benevoles.
- `/planning/` : planification vols et expeditions.
- `/admin/` : administration Django reservee aux utilisateurs internes autorises.
- API interne protegee par cle d'integration.

Scopes volontairement hors de ce brouillon :

- validation juridique finale des mentions legales, CGU et politique de
  confidentialite publiques ;
- choix de licence du code source ;
- audit de donnees de production, logs reels ou contrats fournisseurs.

## 2) Roles et responsabilites

Hypothese a valider :

- Responsable de traitement : Aviation Sans Frontieres, pour les traitements lies
  a la Messagerie Medicale.
- Operateurs internes : responsables entrepot, coordinateurs, administrateurs et
  benevoles autorises.
- Sous-traitants techniques : hebergeur, fournisseur email, services de conversion
  ou stockage documentaire, et APIs externes utilisees par le produit.

Decisions ouvertes :

- nom du referent RGPD ou DPO ;
- statut juridique precis applicable a la branche Messagerie Medicale ;
- canal officiel de contact pour demandes RGPD ;
- validateur humain des textes publics avant publication.

## 3) Registre des traitements

| Traitement | Finalite | Categories de donnees | Personnes concernees | Base legale a valider |
|------------|----------|-----------------------|----------------------|-----------------------|
| Gestion des comptes internes | Authentifier et autoriser les utilisateurs ASF | nom, email, role, historique d'acces applicatif | salaries, benevoles, administrateurs | interet legitime / obligation organisationnelle |
| Gestion des expediteurs | Identifier les associations qui expedient | nom d'association, contacts, email, telephone, adresse | associations partenaires, contacts expediteurs | execution du service / interet legitime |
| Gestion des destinataires | Preparer les expeditions internationales | nom structure, contacts, pays, adresse, email, telephone | destinataires, correspondants locaux | execution du service / interet legitime |
| Preparation colis | Tracer le contenu et la destination des colis | contenu colis, quantites, destination, documents associes | contacts lies aux expeditions | execution du service / obligations douanieres |
| Documents d'expedition | Produire et conserver les pieces douanieres | attestations, factures, listes de colisage, documents uploades | expediteurs, destinataires, correspondants | obligations legales / execution du service |
| Emails transactionnels | Informer les parties d'une action ou d'un statut | email, nom, objet/message, statut d'envoi | utilisateurs, expediteurs, destinataires | execution du service / interet legitime |
| Planification vols | Organiser les mises a bord et livraisons | volontaires, destinations, references colis, vols | benevoles, coordinateurs, contacts expedition | interet legitime / execution du service |
| Journaux techniques | Diagnostiquer erreurs et incidents | identifiants techniques, timestamps, erreurs, acteurs applicatifs | utilisateurs applicatifs | interet legitime / securite |

Points sensibles connus :

- les documents scannes et documents douaniers peuvent contenir des donnees
  personnelles ou commerciales sensibles ;
- le contenu colis peut mentionner du materiel medical ou des medicaments ;
- les destinataires sont souvent hors UE, donc les flux peuvent impliquer des
  transferts internationaux ;
- le contexte produit indique qu'aucune donnee patient nominative, bancaire ou
  concernant des mineurs n'est attendue. Toute exception doit etre traitee comme
  une escalation RGPD.

## 4) Sous-traitants et services tiers

| Service | Usage | Donnees potentiellement exposees | Localisation / transfert | Statut |
|---------|-------|----------------------------------|--------------------------|--------|
| PythonAnywhere | Hebergement application, base et media | toutes donnees stockees en production | fournisseur UK/US a confirmer contractuellement | a valider |
| Brevo | Emails transactionnels | emails, noms, contenu des notifications | fournisseur FR/UE a confirmer | a valider |
| Microsoft Graph / OneDrive | Conversion XLSX vers PDF, stockage partage | documents d'expedition, modeles, exports | fournisseur US/UE selon tenant Microsoft 365 | a valider |
| AF-KLM Flight Status | Statut vols | numeros de vols, dates, donnees operationnelles non personnelles en principe | API externe | a valider |
| ECB | Taux de change | aucune donnee personnelle attendue | API publique | faible risque |
| GitHub Actions | CI et audit de code | code, logs de CI, pas de donnees prod attendues | fournisseur US | verifier absence de secrets/donnees prod |

Regles de minimisation :

- ne jamais placer de dump de production, documents reels ou secrets dans GitHub ;
- ne pas envoyer de documents ou donnees personnelles a une API externe sans
  finalite explicite et validation RGPD ;
- pseudonymiser ou anonymiser les donnees avant toute future fonctionnalite IA ;
- documenter tout nouveau sous-traitant dans cette table avant release.

## 5) Transferts hors UE

Transferts probables :

- destinataires, correspondants et structures dans des pays hors UE ;
- fournisseur hebergement ou stockage selon contrat effectif ;
- APIs ou services americains selon configuration Microsoft/GitHub.

Controle attendu avant exposition large du portail :

- identifier les pays destinataires frequents et les categories de donnees
  partagees ;
- confirmer les clauses contractuelles ou garanties applicables aux fournisseurs ;
- limiter les donnees exportees aux champs necessaires a l'expedition ;
- tracer toute exception ou risque accepte avec une date de revue.

## 6) Durees de conservation

Les durees ci-dessous sont des propositions de travail. Elles doivent etre
validees avec les contraintes douanieres, comptables et associatives.

| Donnees | Conservation proposee | Raison | Action a echeance |
|---------|-----------------------|--------|-------------------|
| Comptes utilisateurs internes actifs | duree d'habilitation + 1 an | securite et continuites operations | desactiver puis anonymiser si non necessaire |
| Associations expediteurs actives | duree relation + 5 ans | historique operationnel et litiges | archiver ou anonymiser contacts inactifs |
| Destinataires/correspondants actifs | duree relation + 5 ans | operations recurrentes et douane | archiver ou anonymiser contacts inactifs |
| Expeditions et colis | 10 ans a confirmer | douane, audit, historique humanitaire | conserver references, anonymiser contacts si possible |
| Documents douaniers/factures/attestations | 10 ans a confirmer | obligations douanieres/comptables possibles | suppression securisee apres echeance |
| Emails transactionnels en queue | jusqu'a traitement + 90 jours d'historique technique | diagnostic incidents | purge ou reduction des payloads |
| Logs applicatifs | 90 jours par defaut | diagnostic et securite | rotation/purge automatique |
| Exports temporaires | 30 jours maximum | limitation d'exposition | suppression automatique ou controle manuel |

Regle produit : toute nouvelle donnee personnelle doit avoir une finalite, une
duree de conservation et une strategie de suppression/anonymisation avant mise en
production.

## 7) Droits des personnes

Canal de demande : **a definir**.

Procedure minimale pour droit d'acces ou portabilite :

1. Identifier la personne et le contexte : utilisateur interne, contact expediteur,
   contact destinataire, correspondant, benevole.
2. Rechercher les donnees dans les comptes, contacts, expeditions, documents,
   emails et journaux applicatifs.
3. Exporter uniquement les donnees relatives a la personne, dans un format lisible
   et securise.
4. Faire relire l'export par un responsable habilite avant envoi.
5. Tracer la date de demande, la date de reponse, le perimetre et le responsable.

Procedure minimale pour rectification :

1. Verifier le demandeur et son droit a modifier la donnee.
2. Corriger depuis la surface metier la plus proche lorsque possible.
3. Conserver une trace d'audit si la modification a un impact operationnel ou
   douanier.

Procedure minimale pour effacement/anonymisation :

1. Verifier si une obligation douaniere, comptable ou de securite impose la
   conservation.
2. Si suppression impossible, anonymiser les champs personnels lorsque le dossier
   doit rester conservable.
3. Supprimer les fichiers temporaires et exports associes.
4. Tracer la decision, la justification et la date de prochaine revue si le risque
   est accepte.

Backlog technique lie :

- ajouter une procedure ou commande `export_personal_data <email>` ;
- ajouter une procedure ou commande `delete_personal_data <email>` ou
  `anonymize_personal_data <email>` ;
- definir une purge ou revue periodique des contacts inactifs.

## 8) Textes publics et consentements

Avant generalisation du portail public, les elements suivants doivent etre valides
et accessibles :

- mentions legales : `docs/policies/mentions-legales.md` ;
- politique de confidentialite : `docs/policies/confidentialite.md` ;
- CGU du portail : `docs/policies/cgu-portail.md` ;
- mentions courtes de formulaires : `docs/policies/mentions-information-formulaires.md` ;
- information sur les sous-traitants et transferts hors UE ;
- information sur les droits d'acces, rectification, effacement, limitation,
  opposition et portabilite ;
- contact officiel pour demandes RGPD.

Si une creation de compte portail implique une acceptation de CGU, le produit doit
conserver au minimum :

- version du texte accepte ;
- date d'acceptation ;
- utilisateur ou demande de compte associee ;
- source de l'acceptation.

La procedure interne proposee pour les demandes d'exercice des droits est
documentee dans `docs/policies/droits-des-personnes.md`.

## 9) Securite et journalisation

Regles attendues :

- limiter les comptes admin et les permissions aux besoins reels ;
- ne pas journaliser de secrets, tokens, mots de passe, documents complets ou
  donnees medicales detaillees ;
- preferer les identifiants internes et references de dossiers dans les logs ;
- proteger les exports locaux et les supprimer apres usage ;
- verifier que les erreurs envoyees a un futur outil de monitoring ne contiennent
  pas de donnees personnelles inutiles.

## 10) Violations de donnees

En cas de suspicion de fuite, perte de donnees, acces non autorise ou erreur
d'envoi :

1. Contenir : couper l'acces fautif, revoquer le secret ou suspendre le flux.
2. Evaluer : identifier donnees, personnes, volume, periode, cause et preuves.
3. Corriger : patch, rollback, rotation de secrets, purge d'exports ou correction
   de droits.
4. Decider avec le referent RGPD si notification CNIL et information des personnes
   sont requises.
5. Tracer l'incident, les decisions et les actions correctives.

## 11) Checklist de validation humaine

P1-02 ne peut etre clos que si les points suivants sont valides ou explicitement
acceptes comme risque date :

- [ ] referent RGPD ou DPO identifie ;
- [ ] responsable de traitement confirme ;
- [ ] bases legales validees par traitement ;
- [ ] durees de conservation validees ;
- [ ] sous-traitants et transferts hors UE verifies ;
- [ ] mentions legales validees ;
- [ ] politique de confidentialite validee ;
- [ ] CGU validees si le portail est ouvert a des tiers ;
- [ ] procedure droits des personnes validee ;
- [ ] backlog export/suppression/anonymisation accepte ou planifie.

## 12) Sources de cadrage

Sources officielles utilisees pour structurer ces brouillons :

- CNIL - information des personnes et transparence :
  https://www.cnil.fr/fr/conformite-rgpd-information-des-personnes-et-transparence
- CNIL - exemples de mentions d'information :
  https://www.cnil.fr/fr/passer-laction/rgpd-exemples-de-mentions-dinformation
- CNIL - registre des activites de traitement :
  https://www.cnil.fr/fr/RGPD-le-registre-des-activites-de-traitement
- CNIL - durees de conservation :
  https://www.cnil.fr/fr/passer-laction/les-durees-de-conservation-des-donnees
- CNIL - droits des personnes :
  https://www.cnil.fr/fr/passer-laction/les-droits-des-personnes-sur-leurs-donnees
- Service-Public - mentions obligatoires d'un site professionnel :
  https://entreprendre.service-public.fr/vosdroits/F37351
