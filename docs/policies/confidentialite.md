# Politique de confidentialite

Statut : **brouillon a valider juridiquement / RGPD avant publication**.

Version de travail : 2026-04-22.

Ce texte est une proposition de base pour les pages publiques et le portail ASF WMS.
Il doit etre relu par le referent RGPD, le DPO le cas echeant, et la personne
habilitee a valider les textes publics d'Aviation Sans Frontieres.

## 1) Qui traite vos donnees ?

Le service ASF WMS est utilise pour organiser les expeditions humanitaires de la
Messagerie Medicale d'Aviation Sans Frontieres.

Responsable de traitement pressenti :

- Aviation Sans Frontieres
- Branche / service : Messagerie Medicale
- Adresse : [a completer]
- Contact general : [a completer]
- Contact RGPD : [a completer]
- DPO ou referent RGPD : [a completer]

Ces informations doivent etre confirmees avant publication.

## 2) Pourquoi vos donnees sont-elles traitees ?

ASF WMS traite des donnees personnelles uniquement pour organiser, suivre et
documenter les expeditions humanitaires gerees par la Messagerie Medicale.

Les principales finalites sont :

- creer et gerer les comptes utilisateurs ;
- recevoir et instruire les demandes de compte portail ;
- identifier les associations expediteurs, destinataires et correspondants ;
- preparer les expeditions, colis, documents douaniers et suivis de livraison ;
- envoyer les notifications necessaires au service ;
- organiser les mises a bord et la planification des vols ;
- assurer la securite, la tracabilite, le support et le diagnostic des incidents.

## 3) Quelles donnees peuvent etre traitees ?

Selon votre role, ASF WMS peut traiter :

- identite : nom, prenom, fonction, association ou structure rattachee ;
- coordonnees : email, telephone, adresse postale, pays ;
- informations de compte : identifiant, role, permissions, historique applicatif ;
- informations d'expedition : reference, destination, contenu colis, quantites,
  documents, etapes de preparation et de livraison ;
- documents transmis : attestations, factures, listes de colisage, documents
  douaniers ou justificatifs utiles au dossier ;
- donnees techniques : dates, journaux applicatifs, erreurs, traces de traitement
  des emails et des documents.

Le service n'a pas vocation a collecter des donnees nominatives de patients, des
donnees bancaires ou des donnees concernant des mineurs. Si une telle donnee est
transmise par erreur, elle doit etre signalee pour correction, suppression ou
limitation d'acces lorsque cela est possible.

## 4) Les donnees sont-elles obligatoires ?

Certaines donnees sont necessaires pour traiter une demande ou une expedition :

- identite et coordonnees du demandeur ;
- structure expediteur ou destinataire ;
- destination et informations utiles a l'acheminement ;
- documents requis pour la preparation ou les formalites.

Si ces informations ne sont pas fournies, ASF peut ne pas etre en mesure de creer
un compte, traiter une expedition, produire les documents requis ou assurer le
suivi.

## 5) Bases legales pressenties

Les bases legales ci-dessous sont des hypotheses a valider.

| Finalite | Base legale pressentie |
|----------|------------------------|
| Gestion des comptes et habilitations | interet legitime de securiser le service |
| Traitement des demandes d'expedition | execution du service demande / interet legitime |
| Documents douaniers et conservation des dossiers | obligation legale ou interet legitime, a confirmer |
| Notifications transactionnelles | execution du service / interet legitime |
| Journaux de securite et diagnostic | interet legitime de securite et fiabilite |
| Gestion des demandes de droits RGPD | obligation legale |

Ces bases doivent etre confirmees par le validateur RGPD avant publication.

## 6) Qui peut acceder aux donnees ?

Les donnees sont accessibles uniquement aux personnes et services qui en ont besoin
pour leur mission :

- utilisateurs internes ASF habilites ;
- benevoles ou coordinateurs selon leurs droits applicatifs ;
- associations expediteurs pour leurs propres demandes ;
- destinataires ou correspondants pour les dossiers qui les concernent ;
- administrateurs techniques autorises ;
- sous-traitants techniques strictement necessaires au fonctionnement du service.

ASF ne vend pas les donnees personnelles et ne les utilise pas a des fins
publicitaires.

## 7) Sous-traitants et services tiers

ASF WMS peut s'appuyer sur des prestataires techniques :

- PythonAnywhere pour l'hebergement applicatif, la base et les medias ;
- Brevo ou le fournisseur email configure pour les emails transactionnels ;
- Microsoft Graph / OneDrive pour certains traitements documentaires ;
- services de statut de vol ou taux de change lorsque necessaire.

Certains prestataires ou destinataires peuvent impliquer des transferts hors Union
europeenne. Les garanties contractuelles et pays concernes doivent etre confirmes
et documentes avant publication definitive.

## 8) Combien de temps les donnees sont-elles conservees ?

Les durees ci-dessous sont des propositions de travail a valider avec les
contraintes douanieres, comptables et associatives :

- comptes internes : duree d'habilitation puis archivage limite ;
- contacts expediteurs, destinataires et correspondants : duree de relation active,
  puis archivage ou anonymisation selon le besoin operationnel ;
- expeditions, colis et documents douaniers : duree compatible avec les obligations
  douanieres, comptables et de preuve, a confirmer ;
- journaux techniques : duree limitee au diagnostic, a la securite et aux incidents ;
- exports temporaires : suppression rapide apres usage.

Les durees de reference internes sont documentees dans
`docs/policies/rgpd.md` et restent a valider.

## 9) Quels sont vos droits ?

Selon le contexte et la base legale applicable, vous pouvez demander :

- l'acces aux donnees vous concernant ;
- la rectification des donnees inexactes ou incompletes ;
- l'effacement lorsque la conservation n'est plus justifiee ;
- la limitation du traitement ;
- l'opposition pour motif legitime lorsque le traitement le permet ;
- la portabilite des donnees fournies, lorsque ce droit est applicable.

Pour exercer ces droits, contactez : [contact RGPD a completer].

Une reponse doit etre apportee dans les meilleurs delais et au plus tard dans le
delai legal applicable. En cas de demande complexe, le delai peut etre prolonge
dans les conditions prevues par le RGPD.

Vous pouvez egalement introduire une reclamation aupres de la CNIL :
https://www.cnil.fr/

## 10) Securite

ASF met en place des mesures techniques et organisationnelles proportionnees :

- acces par comptes et roles ;
- restriction des surfaces d'administration ;
- journalisation des operations sensibles ;
- protection des documents et exports ;
- controle des fichiers transmis lorsque le scan documentaire est active ;
- limitation des donnees partagees avec les prestataires.

Les utilisateurs doivent signaler toute erreur d'envoi, perte de document, acces
indu ou suspicion d'incident a [contact incident a completer].

## 11) Cookies et traceurs

ASF WMS utilise des cookies strictement necessaires au fonctionnement du service,
notamment pour la session, la securite et la protection CSRF.

Le service n'a pas vocation a utiliser des cookies publicitaires ou de suivi
marketing. Toute evolution sur les cookies ou traceurs devra etre documentee et
validee avant publication.

## 12) Mise a jour

Cette politique peut etre mise a jour pour tenir compte des evolutions du service,
des sous-traitants, des obligations legales ou des pratiques internes. La date de
version doit etre mise a jour a chaque modification substantielle.
