from datetime import date

SCAN_FAQ_CHANGE_LOG_ENTRIES = [
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
