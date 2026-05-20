from datetime import date

SCAN_FAQ_CHANGE_LOG_ENTRIES = [
    {
        "date": date(2026, 5, 20),
        "pr_number": None,
        "summary": (
            "Onboarding portail : escales desservies obligatoires, demandes "
            "Autre escale tracées, contacts opérationnels complets pour "
            "expéditeurs/destinataires et création de commande bloquée tant "
            "que le compte expéditeur n'est pas prêt."
        ),
    },
    {
        "date": date(2026, 5, 19),
        "pr_number": 219,
        "summary": (
            "Commandes scan : correction de la validation de la répartition "
            "multi-expéditions pour accepter une expédition 14 colis ou une "
            "répartition 10/4 quand les champs visibles sont cohérents."
        ),
    },
    {
        "date": date(2026, 5, 19),
        "pr_number": None,
        "summary": (
            "Commandes scan : création d'expédition rendue idempotente, préparation "
            "multi-expéditions avec répartition manuelle des colis par expédition, "
            "warnings poids/volume par défaut et Picking Général expédition."
        ),
    },
    {
        "date": date(2026, 5, 11),
        "pr_number": None,
        "summary": (
            "Portail commande : champs quantité protégés contre les changements au scroll, "
            "brouillon restaurable avec effacement explicite, mail nouvelle commande "
            "relié à la file scan, et alerte scan quand un destinataire ajouté attend "
            "validation ASF."
        ),
    },
    {
        "date": date(2026, 5, 7),
        "pr_number": None,
        "summary": (
            "Demande de compte expéditeur : premier destinataire optionnel avec "
            "documents destinataire, et filtre des produits commandés dans la "
            "création de commande portail."
        ),
    },
    {
        "date": date(2026, 5, 6),
        "pr_number": 198,
        "summary": (
            "Authentification : déconnexion portail/bénévole vers leur connexion, "
            "déconnexion/changement de compte scan vers l'accueil production et "
            "session conservée après changement de mot de passe."
        ),
    },
    {
        "date": date(2026, 5, 5),
        "pr_number": None,
        "summary": (
            "Préférences produits portail : validation groupée des lignes modifiées, "
            "compteur de changements et rejet sans sauvegarde partielle si une erreur survient."
        ),
    },
    {
        "date": date(2026, 5, 5),
        "pr_number": None,
        "summary": (
            "Création de commande portail : consignes colis ASF, palette obligatoire "
            "en enlèvement, complément Stock ASF optionnel et type d'expédition "
            "calculé en récapitulatif."
        ),
    },
    {
        "date": date(2026, 5, 5),
        "pr_number": None,
        "summary": (
            "Ajustements portail destinataire et expéditeur : navigation destinataire, "
            "préférences produits lisibles, filtres catégories et jours d'ouverture "
            "des enlèvements."
        ),
    },
    {
        "date": date(2026, 5, 5),
        "pr_number": None,
        "summary": (
            "Tutoriels guidés du portail expéditeur et destinataire, affichage automatique "
            "contrôlé par utilisateur et explication des principaux blocages de flux."
        ),
    },
    {
        "date": date(2026, 4, 29),
        "pr_number": None,
        "summary": (
            "Préparation d'expéditions sans colis affiliés, création batch de dossiers "
            "et impression des dossiers papier avec étiquettes préparatoires."
        ),
    },
    {
        "date": date(2026, 4, 29),
        "pr_number": 187,
        "summary": (
            "Correction ouverture automatique de la modale pour ajouter un produit "
            "inconnu dans le rangement préparateur."
        ),
    },
    {
        "date": date(2026, 4, 29),
        "pr_number": 186,
        "summary": (
            "Rangement préparateur clarifié avec modes Entrée en stock et Déplacement "
            "de stock, batch validé explicitement et correction des emplacements par défaut."
        ),
    },
    {
        "date": date(2026, 4, 29),
        "pr_number": 185,
        "summary": (
            "Correction mobile des tableaux scan : les colonnes compactes restent "
            "lisibles et le défilement horizontal reste local au tableau."
        ),
    },
    {
        "date": date(2026, 4, 28),
        "pr_number": 184,
        "summary": (
            "Nouveau flux préparateur Rangement avec scan produit, récap batch, "
            "mise à jour de stock et création de produit inconnu."
        ),
    },
    {
        "date": date(2026, 4, 24),
        "pr_number": 179,
        "summary": (
            "Cockpit catalogue produits/kits, ajustements scan stock, réception, "
            "préparation, expédition, masthead et FAQ."
        ),
    },
]


def build_scan_faq_change_log_entries():
    entries = []
    for entry in sorted(
        SCAN_FAQ_CHANGE_LOG_ENTRIES,
        key=lambda item: (item["date"], item.get("pr_number") or 0),
        reverse=True,
    ):
        pr_number = entry.get("pr_number")
        entries.append(
            {
                **entry,
                "pr_label": f"PR #{pr_number}" if pr_number else "PR à renseigner avant merge",
            }
        )
    return entries
