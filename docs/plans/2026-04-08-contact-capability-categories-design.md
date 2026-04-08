# Contact Capability Categories Design

## Goal

Ajouter deux catégories persistées de contact, `Partenaire` et `Autre`, avec le même comportement de base que `Transporteur`, tout en rendant la création manuelle plus évidente dans le cockpit scan.

## Scope

- ajouter deux capacités persistées:
  - `partner`
  - `other`
- exposer ces catégories dans le formulaire scan de gestion des contacts
- conserver le même contrat de création/édition que `donor` et `transporter`:
  - choix structure/personne
  - création sans runtime expéditeur/destinataire
  - persistance via `ContactCapability`
- faire réouvrir correctement ces fiches en édition
- clarifier dans l’UI scan où se trouve la création manuelle

## Design

- `ContactCapabilityType` devient la source de vérité pour `partner` et `other`, au même niveau que `donor`, `transporter`, et `volunteer`.
- le formulaire scan ajoute les types métier `partner` et `other`, avec les mêmes règles de validation et de visibilité dynamique que `transporter`:
  - nature obligatoire
  - si personne: prénom + nom obligatoires
  - si structure: nom de structure obligatoire
- l’enregistrement reste centré sur `save_contact_from_form()`:
  - aucun runtime expédition n’est créé
  - seule la capacité persistée est assurée
- la réouverture d’une fiche existante dans le cockpit infère désormais `partner` et `other` avant le fallback par défaut
- l’admin Django legacy continue à créer des `Contact` directement; les nouvelles catégories seront visibles via l’inline de capacités, sans réécriture du modèle `Contact`
- le cockpit scan garde son flux actuel, mais le texte d’introduction doit signaler explicitement que l’accordéon `Création de contact` est le point d’entrée de création manuelle

## Expected Outcome

- les équipes peuvent classer manuellement des contacts en `Partenaire` ou `Autre`
- cette classification est persistée proprement pour exploitation future
- la création manuelle est trouvable à la fois dans scan et dans l’admin Django
