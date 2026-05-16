# HTML Print Footer Parameterization Design

## 1. Executive verdict

- Paramétrisation safe pour une PR suivante: oui, mais uniquement avec des clés installation étroites, des defaults ASF exacts et des tests de non-régression sur le rendu visible.
- Faut-il de nouvelles clés installation: oui. Le footer actuel porte un contrat contact/adresse/légal structuré qui n'existe pas dans les clés installation actuelles.
- `ORG_CONTACT`, `ORG_ADDRESS` et `ORG_NAME` sont rejetés pour le footer. `ORG_CONTACT` et `ORG_ADDRESS` sont des valeurs plates et inadaptées aux quatre lignes hétérogènes. `ORG_NAME` est déjà le nom long d'organisation consommé par `build_org_context()["org_name"]`; ce n'est pas une ligne footer.
- Impact gettext: oui. La ligne URL/email est hors gettext, les lignes `Siège` et `Magasin` sont dans `blocktrans`, et la ligne `Association reconnue...` est dans `trans`, pas `blocktrans`. Une implémentation future doit traiter ces trois cas séparément.
- Option recommandée: nouveau namespace `installation.print`, limité à des clés `html_footer_*` ligne par ligne. Ne pas introduire ces clés dans PR18.

## 2. Contexte

PR15 a remplacé la source de `org_name` dans `wms.documents.build_org_context()` par `installation.identity.organization_full_name`, tout en conservant la clé de contexte existante `org_name`. PR15 n'a pas introduit de contrat footer, de clé de contact print, de ligne légale print, ni de namespace installation dédié aux documents.

PR16 a audité le footer HTML print et a conclu que les deux bases `templates/print/base_document.html` et `templates/print/base_a5.html` contiennent les mêmes quatre lignes hardcodées. PR16 a rejeté l'option de réutiliser `ORG_CONTACT` et `ORG_ADDRESS` parce que ces settings sont plats, que les templates d'environnement ASF-like ne portent pas les chaînes structurées du footer, et que cette direction pousserait vers un fallback ASF caché dans le code.

PR17 a ajouté une couverture de caractérisation dans `wms/tests/views/tests_html_print_footer_identity.py`. Cette couverture verrouille le texte visible actuel du footer, le comportement `hide_footer=True`, le fait que `ORG_CONTACT` et `ORG_ADDRESS` ne changent pas le footer, et le fait que `ORG_NAME` alimente `build_org_context()["org_name"]` sans devenir une ligne du footer.

PR18 est design-only. Elle ne modifie aucun runtime, aucun template, aucune configuration, aucun test, aucun catalogue gettext, aucune migration, aucun fichier d'environnement, aucun binaire, aucun template XLSX, aucun flux Graph/print-pack, aucun certificat de don, aucun label rôle, aucun logo, aucun cachet, aucun identifiant ASF, aucun header API et aucune prose tracking.

## 3. Contrat footer actuel verrouillé

Les quatre lignes visibles verrouillées par PR17 sont:

1. `https://aviation-sans-frontieres.org/messmed // messmed@aviation-sans-frontières-fr.org`
2. `Siège: Bat 293, Porte 1150, Orly Fret 768 - 94398 Orly Aérogare Cedex - Tel: (33) 1 49 75 74 36`
3. `Magasin: Bat. 7200, Porte 2D520, rue de la Remise - 95700 ROISSY en France - Tél: (33) 1 74 25 03 22`
4. `Association reconnue d'utilité publique par décret du 12 novembre 1993`

Inspection Phase 1 confirme que le bloc footer de `base_document.html` et celui de `base_a5.html` sont strictement dupliqués ligne à ligne pour ces quatre lignes. Les deux templates diffèrent ailleurs, notamment sur le format de page, mais pas sur le contrat footer.

Le contrôle d'affichage est `hide_footer`: les deux templates rendent le footer via `{% if not hide_footer %}`. Une valeur absente ou fausse affiche le footer; une valeur vraie le masque.

Inventaire gettext ligne par ligne:

- Ligne 1 URL/email: simple `<div>`, hors gettext.
- Ligne 2 `Siège`: `{% blocktrans trimmed %}`.
- Ligne 3 `Magasin`: `{% blocktrans trimmed %}`.
- Ligne 4 `Association reconnue...`: `{% trans %}`. L'hypothèse initiale disant que cette ligne était dans `blocktrans` est incorrecte.

Le footer n'utilise aucune variable de contexte pour son texte. La seule variable utilisée dans le bloc est `hide_footer`.

Les variables de contexte disponibles via `build_org_context()` dans les contextes qui l'incluent sont:

- `org_name`: `installation.identity.organization_full_name`
- `org_address`: `settings.ORG_ADDRESS`
- `org_contact`: `settings.ORG_CONTACT`
- `org_signatory`: `settings.ORG_SIGNATORY`

Ces variables peuvent être utilisées dans certains corps de documents ou layouts dynamiques, mais elles ne sont pas consommées par les footers de `base_document.html` et `base_a5.html`.

## 4. Pourquoi ORG_CONTACT / ORG_ADDRESS / ORG_NAME ne suffisent pas

`ORG_CONTACT` et `ORG_ADDRESS` ne représentent pas le contrat actuel du footer. Le footer contient une ligne service URL/email, une ligne siège avec téléphone, une ligne magasin avec téléphone, et une ligne légale. Ce sont quatre responsabilités distinctes, pas deux champs plats.

Les templates d'environnement inspectés ne portent pas les valeurs du footer actuel. `asf_wms/settings.py` utilise des placeholders `ORG_NAME`, `ORG_ADDRESS`, `ORG_CONTACT` et `ORG_SIGNATORY`. `.env.example`, `deploy/pythonanywhere/asf-wms.env.template` et `deploy/pythonanywhere/asf-wms.messmed.env.template` utilisent une adresse exemple et `contact@example.com`, pas les lignes `https://aviation-sans-frontieres.org/messmed...`, `Siège...`, `Magasin...` et `Association reconnue...`.

Réutiliser `ORG_CONTACT` ou `ORG_ADDRESS` forcerait soit un préformatage hors code, soit une logique de fallback ASF cachée dans le code. Les deux directions sont rejetées: elles rendent le contrat fragile, implicite et difficile à tester.

`ORG_NAME` ne suffit pas non plus. Depuis PR15, `ORG_NAME` alimente `installation.identity.organization_full_name`, puis `build_org_context()["org_name"]`. Cette clé est un nom long d'organisation. Elle ne décrit ni URL/email public, ni siège, ni magasin, ni statut d'utilité publique.

Conclusion: `ORG_CONTACT`, `ORG_ADDRESS` et `ORG_NAME` restent rejetés pour la paramétrisation du footer. Aucune preuve contraire n'a été trouvée en Phase 1.

## 5. Impact gettext / blocktrans

L'impact gettext doit être analysé ligne par ligne, pas globalement.

Ligne URL/email:

- État actuel: hors gettext.
- Remplacement par variable: aucun effet d'extraction gettext direct.
- Stratégie recommandée: variable simple, rendue comme texte de configuration. Pas de modification `.po`.

Ligne `Siège`:

- État actuel: `blocktrans`.
- Remplacement par une variable complète: le msgid français complet n'est plus extrait depuis le template.
- Garder un `blocktrans` avec placeholder complet, par exemple une ligne entière interpolée, ne préserve pas l'extraction du texte intégral; cela déplace l'extraction vers une structure générique.
- Garder un `blocktrans` avec placeholders structurés pour adresse et téléphone préserverait une structure traduisible, mais exigerait des clés plus granulaires que le contrat PR18 recommandé, donc une autre décision de design.

Ligne `Magasin`:

- Même analyse que `Siège`: `blocktrans` actuel, perte ou transformation d'extraction si la ligne devient une variable complète.
- Le risque est identique: soit accepter une ligne installation-controlled hors extraction intégrale, soit concevoir une structure traduisible avec placeholders plus fins.

Ligne `Association reconnue...`:

- État actuel: `{% trans %}`, pas `blocktrans`.
- Remplacement par variable: le msgid légal disparaît de l'extraction template.
- Garder `trans` autour d'une variable n'a pas le même sens que traduire le literal actuel; cela ne préserve pas le msgid légal intégral.

Deux stratégies possibles pour une future implémentation:

- Stratégie A: sortir les lignes paramétrées de gettext et rendre des variables complètes. C'est simple, compatible avec des clés ligne par ligne, et le texte devient propriété de l'installation. Coût: les msgids `Siège`, `Magasin` et `Association reconnue...` ne sont plus extraits depuis ces templates.
- Stratégie B: conserver une structure gettext avec placeholders interpolés. Cette approche préserve une structure traduisible, mais elle suppose de découper les lignes en éléments plus fins ou d'accepter un msgid générique de type placeholder. Elle ne colle pas naturellement à des clés complètes ligne par ligne et demande une décision i18n plus large.

Recommandation par ligne:

- URL/email: Stratégie A sans hésitation; la ligne est déjà hors gettext.
- `Siège` et `Magasin`: préférer Stratégie A pour la première implémentation si les clés sont complètes ligne par ligne. Documenter explicitement la perte d'extraction intégrale et garder la décision de nettoyage `.po` dans une PR séparée. Si l'équipe veut absolument préserver une traduction structurelle, il faut rouvrir le design avec des clés plus granulaires avant d'implémenter.
- `Association reconnue...`: ne pas traiter comme un simple détail i18n. C'est une mention à valeur juridique. La première implémentation peut la rendre configurable ligne par ligne, mais la question de sa nature légale doit rester explicite.

La PR d'implémentation initiale ne devrait pas modifier `.po` directement. Elle devrait préserver le rendu visible ASF par défaut et noter le drift d'extraction. Une PR gettext séparée peut ensuite supprimer, conserver ou restructurer les entrées selon la décision i18n.

Finding Phase 1: `locale/en/LC_MESSAGES/django.po` contient les chaînes `Siège`, `Magasin` et `Association reconnue...`. Les références observées pointent vers `templates/print/base_a5.html`; aucune référence `templates/print/base_document.html` n'a été trouvée pour ces chaînes. Ce finding doit être pris en compte dans une décision gettext future. PR18 ne modifie pas les catalogues.

## 6. Options de design — comparaison obligatoire de 3 options

### Option A — étendre `installation.identity`

Exemples de clés:

- `identity.print_footer_public_contact_line`
- `identity.print_footer_headquarters_line`
- `identity.print_footer_warehouse_line`
- `identity.print_footer_legal_notice_line`

Cohérence sémantique: faible à moyenne. `identity` contient déjà des noms, marques et emails de contact généraux. Le footer print mélange contact opérationnel, adresses physiques, téléphone et mention juridique. Ce n'est pas seulement de l'identité.

Risque de fourre-tout: élevé. Une fois le footer print placé dans `identity`, les futures demandes de logo, certificats, labels rôles, contacts, mentions légales et wording public risquent toutes d'y être ajoutées.

Compatibilité avec la structure installation actuelle: techniquement simple, mais conceptuellement mauvaise. Le contrat documenté dit que `organization_full_name` ne crée pas de header/footer/logo/champ légal print plus large.

Préservation des defaults ASF exacts: possible avec des constantes exactes.

Mécanique d'override: simple, mais elle brouille les responsabilités entre identité organisationnelle et politique de rendu print.

Consommation côté tests: facile à tester, mais les tests donneraient une fausse impression que le footer est une extension naturelle de `identity`.

Pression future sur les slices XLSX/Graph, donation certificate, role labels: mauvaise. Donation certificate et mentions légales pourraient être aspirés dans `identity`; les role labels pourraient être confondus avec vocabulary; XLSX/Graph auraient besoin d'autres contrats. Cette option augmente le risque de mélange.

Verdict: rejetée.

### Option B — nouveau namespace `installation.documents`

Exemples de clés:

- `documents.html_footer_public_contact_line`
- `documents.html_footer_headquarters_line`
- `documents.html_footer_warehouse_line`
- `documents.html_footer_legal_notice_line`

Cohérence sémantique: moyenne. Le footer est bien une surface documentaire, mais `documents` est trop large: certificats, customs, billing, templates XLSX, pièces jointes, scans, Graph/PDF et artefacts planning peuvent tous revendiquer ce namespace.

Risque de fourre-tout: très élevé. `documents` deviendrait rapidement un tiroir pour tout ce qui est imprimé, généré, scanné ou attaché.

Compatibilité avec la structure installation actuelle: nouvelle surface importante. Elle contredit l'esprit des PR précédentes qui ont évité d'ouvrir un namespace documents avant une responsabilité claire.

Préservation des defaults ASF exacts: possible.

Mécanique d'override: claire pour les documents, mais trop large pour une première consommation.

Consommation côté tests: facile pour les footers, mais le nom invite à des tests non liés aux footers.

Pression future sur les slices XLSX/Graph, donation certificate, role labels: très forte. XLSX/Graph print-pack, donation certificate, planning workbook/PDF et metadata XLSX pourraient tous être poussés vers `documents`, alors qu'ils ont des contraintes et cadences différentes. Cette option rend plus difficile de garder des slices petites.

Verdict: rejetée.

### Option C — nouveau namespace `installation.print`

Exemples de clés:

- `print.html_footer_public_contact_line`
- `print.html_footer_headquarters_line`
- `print.html_footer_warehouse_line`
- `print.html_footer_legal_notice_line`

Cohérence sémantique: bonne si le namespace est explicitement limité à des contrats de rendu print. Le suffixe `html_footer_*` garde la portée au footer HTML actuel, pas au print global.

Risque de fourre-tout: réel mais contrôlable. `print` peut devenir large si on y ajoute labels, XLSX, Graph, logo, cachet et rôles sans gouvernance. Le risque est acceptable seulement si la première dataclass est nommée et documentée autour du footer HTML.

Compatibilité avec la structure installation actuelle: acceptable. C'est un nouveau domaine de configuration parce que les domaines existants ne conviennent pas. Il doit rester leaf, déclaratif, et sans effet runtime tant qu'une PR de consommation ne l'utilise pas.

Préservation des defaults ASF exacts: directe. Les quatre defaults peuvent reprendre les quatre lignes visibles verrouillées par PR17.

Mécanique d'override: claire. Une installation white-label remplace uniquement les lignes de footer, sans préformater `ORG_ADDRESS` ou `ORG_CONTACT` et sans fallback ASF caché.

Consommation côté tests: claire. PR17 peut rester verte aux defaults ASF, puis être adaptée pour vérifier que le footer rend les valeurs de `installation.print.html_footer_*`.

Pression future sur les slices XLSX/Graph, donation certificate, role labels: contrôlable si la règle est explicite. Les futures slices connues ne doivent pas tomber automatiquement dans ce namespace:

- XLSX/Graph print-pack: hors scope du footer HTML; décider plus tard si besoin d'un sous-contrat propre.
- Donation certificate: document juridique spécifique; ne pas le rattacher mécaniquement au footer.
- Role labels (`RESP. DOUANE ASF`, `ASF Customs agent`, `RESPONSABLE VOL ASF`, `ASF Flight Manager`): probablement vocabulary ou document-specific, pas footer.
- Logo, alt text, cachet: media/branding, pas footer text.
- Planning workbook/PDF: artefact planning, pas footer HTML.

Verdict: recommandée.

### Option D — namespace plus étroit `installation.print_html_footer`

Cette option serait encore plus stricte, mais elle ajouterait un namespace très spécialisé au niveau racine. Elle réduit le risque de fourre-tout, mais fragmente l'installation config trop tôt et ne s'aligne pas avec les familles existantes.

Verdict: non recommandée pour l'instant. Option C avec une dataclass interne étroite est plus lisible.

### Recommandation

Recommander exactement une option: Option C, nouveau namespace `installation.print`, limité dans sa première version à des clés `html_footer_*`. C'est le meilleur compromis entre sémantique, extensibilité contrôlée, et séparation nette avec `identity`, `documents`, `vocabulary`, `references`, `notifications` et les intégrations.

## 7. Clés proposées

Les clés proposées ci-dessous ne sont pas introduites par PR18. Elles décrivent une future PR.

1. `print.html_footer_public_contact_line`
   - Type: `str`
   - Default ASF exact: `https://aviation-sans-frontieres.org/messmed // messmed@aviation-sans-frontières-fr.org`
   - Portée: `templates/print/base_document.html` ligne footer 1 et `templates/print/base_a5.html` ligne footer 1.
   - Justification: ligne service/public contact distincte. Elle n'est ni `ORG_CONTACT`, ni `contact_email`, car elle combine URL, chemin service MessMed et email.

2. `print.html_footer_headquarters_line`
   - Type: `str`
   - Default ASF exact: `Siège: Bat 293, Porte 1150, Orly Fret 768 - 94398 Orly Aérogare Cedex - Tel: (33) 1 49 75 74 36`
   - Portée: `templates/print/base_document.html` ligne footer 2 et `templates/print/base_a5.html` ligne footer 2.
   - Justification: ligne siège complète, incluant libellé, adresse, téléphone et ponctuation. Elle est trop structurée pour `ORG_ADDRESS`.

3. `print.html_footer_warehouse_line`
   - Type: `str`
   - Default ASF exact: `Magasin: Bat. 7200, Porte 2D520, rue de la Remise - 95700 ROISSY en France - Tél: (33) 1 74 25 03 22`
   - Portée: `templates/print/base_document.html` ligne footer 3 et `templates/print/base_a5.html` ligne footer 3.
   - Justification: ligne magasin/logistique complète, distincte du siège. Elle ne doit pas être fusionnée avec une adresse organisationnelle générique.

4. `print.html_footer_legal_notice_line`
   - Type: `str`
   - Default ASF exact: `Association reconnue d'utilité publique par décret du 12 novembre 1993`
   - Portée: `templates/print/base_document.html` ligne footer 4 et `templates/print/base_a5.html` ligne footer 4.
   - Justification: mention légale/statutaire visible. Elle doit rester une ligne étroite et ne pas devenir un attribut légal global sans décision humaine.

Ces clés sont ligne par ligne. Il n'y a pas de bundle vague du type `footer_lines`, pas de format implicite, pas de fallback ASF caché et pas de dépendance aux settings `ORG_*`.

## 8. Stratégie d'override

Les defaults dans `main` doivent reproduire exactement le texte visible ASF actuel. Les tests doivent comparer le rendu visible décodé, comme PR17 le fait déjà, afin d'éviter de figer inutilement l'encodage HTML source tel que `&egrave;`.

La structure HTML doit rester aussi proche que possible de l'actuel: quatre `<div>` dans `<footer class="print-footer">`, sous le même contrôle `hide_footer`. Si une future implémentation modifie du HTML non visible ou l'extraction gettext, cela doit être annoncé dans le corps de PR et couvert par tests ciblés.

Mécanique d'override white-label:

- Les clés `installation.print.html_footer_*` portent les valeurs finales à afficher.
- Les defaults ASF exacts vivent dans `wms/config/installation.py`.
- Les overrides doivent passer par la configuration installation, pas par un préformatage de `ORG_ADDRESS` ou `ORG_CONTACT`.
- Une valeur absente ne doit pas déclencher un fallback ASF caché dans `build_org_context()` ou dans les templates. Le fallback doit être le default déclaré de la configuration installation.

Rappel: defaults dans `main` = comportement ASF exact.

## 9. Compatibilité avec les tests PR17

Les tests PR17 doivent rester verts aux defaults ASF. En phase foundation seule, ils ne doivent pas bouger: les templates restent hardcodés et les nouvelles clés ne sont pas consommées.

Au moment de la consommation template, les tests PR17 devront évoluer:

- conserver un test de rendu par défaut qui vérifie les quatre lignes ASF exactes;
- ajouter ou adapter un test override installation pour prouver que les quatre lignes du footer viennent des clés `print.html_footer_*`;
- conserver le test `hide_footer=True`;
- remplacer les assertions `ORG_CONTACT` / `ORG_ADDRESS` par une assertion de non-consommation de ces settings si la garantie reste utile;
- conserver la preuve que `ORG_NAME` alimente `org_name` sans être une ligne footer.

Il ne faut pas supprimer PR17 comme simple snapshot devenu gênant. PR17 est le filet de sécurité: il doit être transformé en tests de contrat default + override.

## 10. Plan de slicing pour les PRs d'implémentation

Découpage proposé:

- PR19: foundation seule. Introduire `InstallationPrint`, le champ `print` dans `InstallationConfig`, les quatre constantes defaults ASF exactes et les tests installation config associés. Ne rien consommer dans les templates. Ne pas modifier gettext. Ce slice prouve la configuration sans changer le runtime.
- PR20: consommation HTML footer commune pour `base_document.html` et `base_a5.html` dans une seule PR, si la duplication stricte reste confirmée. Justification: les deux footers sont identiques, le risque principal est gettext et il est commun; les séparer créerait deux PRs quasi identiques avec risque de divergence.
- PR21: tests de white-label override et durcissement éventuel autour de `hide_footer`, si PR20 devient trop large. Si PR20 garde une taille maîtrisée, PR21 peut être inutile.
- PR22: décision gettext/catalogues. Nettoyer ou restructurer `.po` seulement après décision explicite sur les lignes `blocktrans`/`trans`. Ne pas faire ce nettoyage mécaniquement dans PR19/PR20.

Recommandation finale de slicing:

1. Garder PR19 séparée et sans consommation runtime.
2. Fusionner la consommation `base_document.html` et `base_a5.html` dans PR20 uniquement si la stratégie gettext est acceptée avant écriture. La duplication stricte justifie une consommation commune.
3. Garder PR22 séparée pour gettext si les catalogues doivent bouger.

Chaque slice doit rester petit, incrémental et testable. Aucun slice ne doit ouvrir donation certificate, XLSX/Graph, planning, labels rôles, logo, cachet ou identifiants ASF.

## 11. Exclusions persistantes pour les PRs d'implémentation

Les futures PRs de paramétrisation footer ne doivent pas toucher:

- donation certificate;
- `wms/print_layouts.py`, sauf nécessité prouvée et documentée;
- XLSX/Graph print-pack;
- Microsoft Graph / local helper;
- logo, alt text, chemin d'image, cachet;
- role labels: `RESP. DOUANE ASF`, `ASF Customs agent`, `RESPONSABLE VOL ASF`, `ASF Flight Manager`;
- `Contact.asf_id`, `ASF ID`, `ID ASF`;
- `ASF-ORG-ROOT` / default shipper;
- API headers / User-Agent;
- `CommunicationFamily.EMAIL_ASF`;
- tracking prose;
- placeholder `admin_contacts_filters_card.html`;
- tout refactor large print/PDF;
- gettext catalogs sans décision dédiée;
- templates d'environnement sans décision d'override documentée.

## 12. Décisions non prises ici / questions ouvertes

PR18 ne tranche pas les points suivants:

- Le choix final du namespace par code. PR18 recommande `installation.print`, mais n'introduit aucune clé.
- La forme exacte de la dataclass future (`InstallationPrint`, sous-objet `html_footer`, ou champs plats `html_footer_*`).
- L'inclusion ou non des changements `.po` dans PR20/PR22. Phase 1 a trouvé que `locale/en/LC_MESSAGES/django.po` contient `Siège`, `Magasin` et `Association reconnue...`, avec références observées vers `templates/print/base_a5.html` seulement et aucune référence `base_document.html` trouvée. C'est un finding à traiter dans une future décision gettext, pas un sujet PR18.
- La stratégie gettext définitive pour les lignes `Siège` et `Magasin`: variables complètes hors extraction ou structure `blocktrans` à placeholders plus fins.
- La stratégie gettext définitive pour la ligne `Association reconnue...`, qui est dans `trans`, pas `blocktrans`.
- Le traitement de la mention d'utilité publique: simple ligne footer configurable ou attribut organisationnel à valeur juridique.
- Le comportement attendu pour une installation non-ASF sans équivalent légal à la mention d'utilité publique.
- Le fait de garder ou supprimer à terme les settings `ORG_ADDRESS`, `ORG_CONTACT` et `ORG_SIGNATORY`.
- La prise en charge éventuelle de footers XLSX/Graph/PDF non HTML.

## 13. Annexe

Lignes footer verrouillées par PR17:

1. `https://aviation-sans-frontieres.org/messmed // messmed@aviation-sans-frontières-fr.org`
2. `Siège: Bat 293, Porte 1150, Orly Fret 768 - 94398 Orly Aérogare Cedex - Tel: (33) 1 49 75 74 36`
3. `Magasin: Bat. 7200, Porte 2D520, rue de la Remise - 95700 ROISSY en France - Tél: (33) 1 74 25 03 22`
4. `Association reconnue d'utilité publique par décret du 12 novembre 1993`

Fichiers inspectés:

- `templates/print/base_document.html`
- `templates/print/base_a5.html`
- `wms/tests/views/tests_html_print_footer_identity.py`
- `wms/documents.py`
- `wms/print_context.py`
- `wms/print_renderer.py`
- `wms/views_print_docs.py`
- `wms/shipment_view_helpers.py`
- `wms/views_print_templates.py`
- `wms/config/installation.py`
- `docs/repo-reference/04-shared-contracts/08-installation-config.md`
- `asf_wms/settings.py`
- `.env.example`
- `deploy/pythonanywhere/asf-wms.env.template`
- `deploy/pythonanywhere/asf-wms.messmed.env.template`
- `locale/en/LC_MESSAGES/django.po`
