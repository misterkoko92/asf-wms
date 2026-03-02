# Remplacement De La Page Templates Par Un Editeur De Mapping XLSX

## Contexte

La page legacy `Gestion > Templates` (`/scan/templates/`) édite aujourd'hui des layouts HTML (`PrintTemplate`) devenus obsolètes pour le flux d'impression actuel, désormais basé sur les packs XLSX (`PrintPackDocument` + `PrintCellMapping`).

Objectif: remplacer totalement ce fonctionnement legacy par une interface opérationnelle pour piloter les templates XLSX et leurs mappings sans passage par le code.

Contraintes validées:
- Scope legacy uniquement (pas de migration Next dans cette phase).
- Suppression fonctionnelle de l'éditeur layout HTML sur ce parcours.
- Upload/remplacement du fichier `.xlsx` depuis l'interface.
- Edition batch des mappings (plusieurs changements en un enregistrement).
- Gestion explicite des cellules fusionnées.
- Versioning avec rollback complet (template + mappings).
- Pas de champ source manuel libre (liste fermée uniquement).

## Cible Fonctionnelle

### 1. Liste Templates (page `/scan/templates/`)

La page devient une liste des `PrintPackDocument`:
- pack, doc_type, variant
- fichier XLSX courant
- nombre de mappings
- version active
- dernière mise à jour / auteur
- action "Modifier"

Le modèle `PrintTemplate` n'est plus utilisé sur ce parcours.

### 2. Ecran Edition D'un Template XLSX

Un écran d'édition par `PrintPackDocument`:
- bloc méta (pack / doc / variant)
- bloc upload/remplacement `.xlsx`
- grille de mappings éditables en lot
- sauvegarde unique transactionnelle
- historique des versions avec restauration

Colonnes de la grille:
- worksheet
- colonne (dropdown)
- ligne (dropdown)
- cellule calculée (lecture seule)
- champ source (dropdown depuis catalogue backend)
- transform (`none`, `upper`, `date_fr`)
- required
- sequence
- état de validation

### 3. Cellules Fusionnées

Lors de l'édition/sauvegarde:
- si la cellule sélectionnée est incluse dans une plage fusionnée, normalisation vers la cellule d'ancrage (coin haut-gauche)
- affichage de la plage fusionnée détectée
- stockage du `cell_ref` normalisé dans `PrintCellMapping`

## Design Technique

### 1. Modèle De Versioning

Ajout d'un modèle `PrintPackDocumentVersion`:
- `pack_document` (FK)
- `version` (int séquentiel, unique par document)
- `xlsx_template_file` (fichier snapshot)
- `mappings_snapshot` (JSON list)
- `change_type` (`save`, `restore`)
- `change_note` (optionnel)
- `created_at`, `created_by`

Le runtime continue d'utiliser l'état courant:
- `PrintPackDocument.xlsx_template_file`
- `PrintCellMapping` actifs

Le modèle de version sert à:
- audit des changements
- rollback complet

### 2. Sauvegarde Transactionnelle

Un enregistrement de l'écran exécute dans une seule transaction:
1. validation du fichier uploadé (si présent)
2. validation/normalisation des mappings
3. mise à jour de l'état courant (fichier + mappings)
4. création de la version snapshot (`PrintPackDocumentVersion`)

### 3. Restauration

Action "Restaurer version N":
1. réapplique le fichier versionné
2. remplace les mappings actifs par le snapshot
3. crée une nouvelle version (type `restore`) pour traçabilité

### 4. Catalogue De Champs Sources

Catalogue backend fermé (pas de saisie libre) regroupé par namespaces:
- `shipment.*`
- `carton.*`
- `document.*`

Ce catalogue alimente le dropdown UI et la validation serveur.

## Sécurité Et Permissions

- route protégée `scan_staff_required` + superuser obligatoire (même niveau que l'ancien éditeur templates)
- upload limité aux `.xlsx` valides
- payload mappings validé côté serveur (worksheet/cell_ref/source_key/sequence)

## Migration Et Compatibilité

### 1. Migration Données

Ajout de la table `PrintPackDocumentVersion` et backfill initial:
- création d'une version initiale pour chaque `PrintPackDocument` existant
- snapshot de l'état courant (fichier DB si présent, sinon fallback canonique `data/print_templates/<pack>__<doc_type>__<variant>.xlsx` si disponible)
- snapshot mappings actifs

### 2. Compatibilité Runtime

Le moteur d'impression n'est pas modifié fonctionnellement:
- il lit toujours les mappings actifs + fichier courant
- la nouvelle UI ne change que la manière de les administrer

## Plan De Tests

### 1. Tests Vue Legacy

- liste `/scan/templates/` affiche les `PrintPackDocument`
- écran édition charge données attendues
- superuser requis

### 2. Tests Sauvegarde

- sauvegarde batch mappings
- upload + remplacement fichier
- validation cell refs/worksheets
- normalisation cellule fusionnée
- création version snapshot

### 3. Tests Restauration

- restauration version remet fichier + mappings
- création version `restore`

### 4. Tests Non Régression Runtime

- génération pack continue de fonctionner après modifications via UI
- mappings restaurés bien appliqués dans le rendu XLSX

## Décisions

- `/scan/templates/` devient l'éditeur primaire des templates XLSX pack.
- `PrintTemplate` (layout HTML) est retiré de ce flux.
- versioning systématique de chaque modification.
- aucun champ manuel libre en V1.
