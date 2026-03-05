from __future__ import annotations

import html
import re

from django.utils.translation import get_language

# Legacy French UI fallback map for English rendering while templates/forms/messages
# are progressively migrated to native Django i18n tags.
_FRENCH_TO_ENGLISH = {
    "Portail association": "Association portal",
    "Nouvelle commande": "New order",
    "Destinataires": "Recipients",
    "Déconnexion": "Log out",
    "Tableau de bord": "Dashboard",
    "Voir les états": "View statuses",
    "Vue Stock": "Stock view",
    "Vue Kits": "Kits view",
    "Vue Colis": "Parcels view",
    "Vue Expéditions": "Shipments view",
    "Vue Exp&#233;ditions": "Shipments view",
    "Vue Commande": "Order view",
    "Vue Réception": "Receipts view",
    "Vue R&#233;ception": "Receipts view",
    "Réception": "Receiving",
    "R&#233;ception": "Receiving",
    "Réception palette": "Pallet receiving",
    "R&#233;ception palette": "Pallet receiving",
    "Réception association": "Association receiving",
    "R&#233;ception association": "Association receiving",
    "MAJ stock": "Stock update",
    "Préparation": "Preparation",
    "Pr&#233;paration": "Preparation",
    "Pr&eacute;paration": "Preparation",
    "Pr&#233;parer des kits": "Prepare kits",
    "Pr&eacute;parer des kits": "Prepare kits",
    "Pr&#233;parer des colis": "Prepare parcels",
    "Pr&eacute;parer des colis": "Prepare parcels",
    "Pr&#233;paration exp&#233;dition": "Shipment preparation",
    "Pr&eacute;paration exp&eacute;dition": "Shipment preparation",
    "Gestion": "Management",
    "Supprimer produit": "Remove product",
    "Admin Django": "Django admin",
    "Changer de compte": "Switch account",
    "Nouvelles demandes de compte en attente": "New pending account requests",
    "voir": "view",
    "Des changements sont disponibles. Recharge pour synchroniser.": "Changes are available. Reload to sync.",
    "Recharger": "Reload",
    "Caméra scan": "Scan camera",
    "Cam&#233;ra scan": "Scan camera",
    "Cam&eacute;ra scan": "Scan camera",
    "Fermer": "Close",
    "Scan en cours...": "Scanning...",
    "Capturer texte": "Capture text",
    "FAQ / Documentation": "FAQ / Documentation",
    "Etiquette Produit": "Product label",
    "Étiquette Produit": "Product label",
    "Etiquette produit": "Product label",
    "Étiquette produit": "Product label",
    "Imprimer etiquettes": "Print labels",
    "Imprimer QR": "Print QR",
    "Imprimer les deux": "Print both",
    "Filtrer": "Filter",
    "R&eacute;ception stock": "Stock receiving",
    "Réception stock": "Stock receiving",
    "Ajuster stock": "Adjust stock",
    "Ajuster": "Adjust",
    "Transf&eacute;rer stock": "Transfer stock",
    "Transférer stock": "Transfer stock",
    "Pr&eacute;parer carton": "Prepare carton",
    "Préparer carton": "Prepare carton",
    "Paramètres": "Settings",
    "Param&#232;tres": "Settings",
    "Design": "Design",
    "Contacts": "Contacts",
    "Produit": "Product",
    "Compte": "Account",
    "Commandes": "Orders",
    "Statut": "Status",
    "Créer": "Create",
    "Modifier": "Edit",
    "Supprimer": "Delete",
    "Annuler": "Cancel",
    "Enregistrer": "Save",
    "Télécharger": "Download",
    "T&#233;l&#233;charger": "Download",
    "Importer": "Import",
    "Exporter": "Export",
    "Recherche": "Search",
    "Mot de passe oublié": "Forgot password",
    "Mot de passe oubli": "Forgot password",
    "Première connexion": "First login",
    "Premi&#232;re connexion": "First login",
    "Connexion": "Sign in",
    "Déconnexion": "Log out",
    "Se connecter": "Sign in",
    "Connexion association": "Association login",
    "Utilisez votre email et votre mot de passe.": "Use your email and password.",
    "Pas de compte ? Envoyez une demande, elle sera validée par un administrateur ASF.": "No account? Submit a request, it will be validated by an ASF administrator.",
    "Demander un compte": "Request an account",
    "Mot de passe oublié / Première connexion": "Forgot password / First login",
    "Date réception": "Reception date",
    "Nombre de palettes": "Number of pallets",
    "Enregistrer la réception palette": "Save pallet receiving",
    "Ajouter donateur": "Add donor",
    "Ajouter transporteur": "Add carrier",
    "Nombre de cartons": "Number of parcels",
    "Nombre de hors format": "Number of out-of-format items",
    "Enregistrer la réception association": "Save association receiving",
    "Hors format": "Out-of-format",
    "Nom de l'association": "Association name",
    "Date demande transport": "Transport request date",
    "Transporteur": "Carrier",
    "Donateur": "Donor",
    "Reception palette": "Pallet receiving",
    "Reception association": "Association receiving",
    "Réception association": "Association receiving",
    "Réception palette": "Pallet receiving",
    "R&eacute;ception association": "Association receiving",
    "R&eacute;ception palette": "Pallet receiving",
    "Accès & rôles": "Access & roles",
    "Données de référence": "Reference data",
    "Suivi des expéditions (Gestion)": "Shipment tracking (Management)",
    "Documents & étiquettes": "Documents & labels",
    "Créer des colis multi-produits": "Create multi-product parcels",
    "Ajouter des cartons": "Add parcels",
    "Préparation (cartons)": "Preparation (parcels)",
    "Enregistrer en brouillon": "Save as draft",
    "Vue Commande (associations)": "Orders view (associations)",
    "Vue stock": "Stock view",
    "Vue Colis": "Parcels view",
    "Le menu": "The menu",
    "Exception:": "Exception:",
    "Avant utilisation, vérifier ces données :": "Before using the system, check this data:",
    "Actions disponibles:": "Available actions:",
    "Formats acceptés:": "Accepted formats:",
    "Conseil:": "Tip:",
    "Q:": "Q:",
    "R:": "A:",
    "Aucun": "No",
    "Aucune": "No",
}

_SORTED_TRANSLATIONS = tuple(
    sorted(_FRENCH_TO_ENGLISH.items(), key=lambda item: len(item[0]), reverse=True)
)

_WORD_TRANSLATIONS = {
    "accès": "access",
    "rôles": "roles",
    "données": "data",
    "référence": "reference",
    "références": "references",
    "suivi": "tracking",
    "expédition": "shipment",
    "expéditions": "shipments",
    "réception": "receiving",
    "réceptions": "receivings",
    "réceptionnées": "received",
    "réel": "actual",
    "réels": "actual",
    "périmètre": "scope",
    "périmètres": "scopes",
    "préparation": "preparation",
    "préparer": "prepare",
    "préparés": "prepared",
    "préparées": "prepared",
    "préparé": "prepared",
    "préparée": "prepared",
    "création": "creation",
    "créer": "create",
    "créé": "created",
    "créée": "created",
    "créés": "created",
    "créées": "created",
    "enregistrer": "save",
    "enregistre": "records",
    "enregistré": "recorded",
    "enregistrée": "recorded",
    "enregistrés": "recorded",
    "enregistrées": "recorded",
    "annuler": "cancel",
    "ajouter": "add",
    "ajouté": "added",
    "ajoutée": "added",
    "ajoutés": "added",
    "ajoutées": "added",
    "modifier": "edit",
    "modification": "edit",
    "modifications": "edits",
    "supprimer": "delete",
    "supprimé": "deleted",
    "supprimée": "deleted",
    "supprimés": "deleted",
    "supprimées": "deleted",
    "déclarer": "declare",
    "déconnexion": "log out",
    "connexion": "sign in",
    "compte": "account",
    "comptes": "accounts",
    "commande": "order",
    "commandes": "orders",
    "stock": "stock",
    "lot": "lot",
    "lots": "lots",
    "péremption": "expiry date",
    "entrepôt": "warehouse",
    "entrepôts": "warehouses",
    "étagère": "shelf",
    "bac": "bin",
    "destination": "destination",
    "destinations": "destinations",
    "destinataire": "recipient",
    "destinataires": "recipients",
    "expéditeur": "shipper",
    "expéditeurs": "shippers",
    "correspondant": "correspondent",
    "correspondants": "correspondents",
    "transporteur": "carrier",
    "transporteurs": "carriers",
    "donateur": "donor",
    "donateurs": "donors",
    "étiquette": "label",
    "étiquettes": "labels",
    "étiqueté": "labeled",
    "étiquetée": "labeled",
    "étiquetés": "labeled",
    "étiquetées": "labeled",
    "imprimer": "print",
    "télécharger": "download",
    "fichier": "file",
    "fichiers": "files",
    "ligne": "line",
    "lignes": "lines",
    "quantité": "quantity",
    "quantités": "quantities",
    "litige": "dispute",
    "litiges": "disputes",
    "clore": "close",
    "clos": "closed",
    "clôturé": "closed",
    "clôturée": "closed",
    "clôturés": "closed",
    "clôturées": "closed",
    "actif": "active",
    "active": "active",
    "actifs": "active",
    "actives": "active",
    "inactif": "inactive",
    "inactifs": "inactive",
    "horodatage": "timestamp",
    "journal": "log",
    "vérifier": "check",
    "vérifiez": "check",
    "gestion": "management",
    "paramètres": "settings",
    "tableau": "dashboard",
    "bord": "board",
    "retour": "back",
    "notes": "notes",
    "date": "date",
    "dates": "dates",
    "ville": "city",
    "pays": "country",
    "adresse": "address",
    "mobile": "mobile",
    "rapides": "fast",
    "cohérents": "consistent",
    "cohérentes": "consistent",
    "système": "system",
    "modèle": "model",
    "opérations": "operations",
    "maintenance": "maintenance",
    "public": "public",
    "privé": "private",
    "privée": "private",
    "staff": "staff",
    "base": "database",
    "avec": "with",
    "sans": "without",
    "dans": "in",
    "sur": "on",
    "pour": "for",
    "depuis": "from",
    "vers": "to",
    "avant": "before",
    "après": "after",
    "puis": "then",
    "tant": "as long",
    "que": "as",
    "est": "is",
    "sont": "are",
    "être": "be",
    "pas": "not",
    "le": "the",
    "la": "the",
    "les": "the",
    "du": "of the",
    "des": "of",
    "de": "of",
    "un": "a",
    "une": "a",
    "et": "and",
    "ou": "or",
    "où": "where",
    "si": "if",
    "plus": "more",
    "tout": "all",
    "tous": "all",
    "toutes": "all",
    "aucun": "no",
    "aucune": "no",
    "commande": "order",
    "commandes": "orders",
    "destinataire": "recipient",
    "destinataires": "recipients",
    "compte": "account",
    "réception": "receiving",
    "expédition": "shipment",
    "expéditions": "shipments",
    "colis": "parcels",
    "produit": "product",
    "produits": "products",
    "paramètres": "settings",
    "télécharger": "download",
    "imprimer": "print",
    "fermer": "close",
    "annuler": "cancel",
    "enregistrer": "save",
    "ajouter": "add",
    "modifier": "edit",
    "supprimer": "delete",
    "suivi": "tracking",
    "statut": "status",
    "statuts": "statuses",
    "date": "date",
    "quantité": "quantity",
    "stock": "stock",
    "entrepôt": "warehouse",
    "emplacement": "location",
    "association": "association",
    "correspondant": "correspondent",
    "expéditeur": "shipper",
    "expediteur": "shipper",
}

_SORTED_WORD_TRANSLATIONS = tuple(
    sorted(_WORD_TRANSLATIONS.items(), key=lambda item: len(item[0]), reverse=True)
)

_SCRIPT_OR_STYLE_BLOCK_RE = re.compile(
    r"(<script\b[^>]*>.*?</script>|<style\b[^>]*>.*?</style>)",
    flags=re.IGNORECASE | re.DOTALL,
)
_TEXT_NODE_RE = re.compile(r">([^<]+)<")


def _translate_fragment(content: str) -> str:
    translated = content
    for source, target in _SORTED_TRANSLATIONS:
        translated = translated.replace(source, target)
    return translated


def _apply_case(source: str, translated: str) -> str:
    if source.isupper():
        return translated.upper()
    if source[:1].isupper() and source[1:].islower():
        return translated[:1].upper() + translated[1:]
    return translated


def _translate_words(content: str) -> str:
    translated = content
    for source, target in _SORTED_WORD_TRANSLATIONS:
        pattern = re.compile(rf"(?<!\w){re.escape(source)}(?!\w)", flags=re.IGNORECASE)

        def _replace(match: re.Match[str]) -> str:
            return _apply_case(match.group(0), target)

        translated = pattern.sub(_replace, translated)
    return translated


def _translate_text_nodes(content: str) -> str:
    def _replace_text_node(match: re.Match[str]) -> str:
        raw = match.group(1)
        decoded = html.unescape(raw)
        translated = _translate_fragment(decoded)
        translated = _translate_words(translated)
        escaped = html.escape(translated, quote=False)
        return f">{escaped}<"

    return _TEXT_NODE_RE.sub(_replace_text_node, content)


def _translate_legacy_html(content: str) -> str:
    chunks = _SCRIPT_OR_STYLE_BLOCK_RE.split(content)
    translated_chunks = []
    for index, chunk in enumerate(chunks):
        if index % 2 == 1:
            translated_chunks.append(chunk)
        else:
            translated_chunks.append(_translate_text_nodes(chunk))
    return "".join(translated_chunks)


class RuntimeEnglishTranslationMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        language = (get_language() or "").lower()
        if not language.startswith("en"):
            return response
        if response.streaming:
            return response
        if "text/html" not in (response.get("Content-Type", "")).lower():
            return response

        charset = response.charset or "utf-8"
        try:
            raw = response.content.decode(charset)
        except (AttributeError, UnicodeDecodeError):
            return response

        translated = _translate_legacy_html(raw)
        if translated == raw:
            return response

        encoded = translated.encode(charset)
        response.content = encoded
        if response.has_header("Content-Length"):
            response["Content-Length"] = str(len(encoded))
        return response
