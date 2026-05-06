from __future__ import annotations

from django.urls import reverse_lazy
from django.utils import timezone

from wms.models import PortalAccessRole, PortalOnboardingPreference
from wms.portal_access import PORTAL_SCOPE_SOURCE_LEGACY_ASSOCIATION

PORTAL_ONBOARDING_SEEN_SESSION_KEY = "portal_onboarding_seen"


SHIPPER_STEPS = [
    {
        "title": "Votre espace expéditeur",
        "body": (
            "Retrouvez ici votre compte, vos destinataires, vos demandes d'expédition "
            "ou de transport, le suivi, les documents et la facturation."
        ),
        "why": "Ces informations structurent les demandes envoyées à ASF.",
        "blockers": [
            "Compte expéditeur encore en revue ASF.",
            "Documents expéditeur non conformes ou non validés.",
            "Certaines actions restent bloquées tant que la revue ASF n'est pas terminée.",
        ],
    },
    {
        "title": "Créer un destinataire",
        "body": "Un destinataire actif est nécessaire avant toute demande d'expédition.",
        "why": "Il permet d'associer la demande à une destination et à un contact de réception.",
        "blockers": [
            (
                "Sans destinataire actif marqué comme contact de réception, la création "
                "de commande et l'accès aux stocks/produits restent bloqués."
            ),
        ],
        "action_label": "Ajouter un destinataire",
        "action_url": reverse_lazy("portal:portal_recipients"),
    },
    {
        "title": "Définir besoins et refus produits",
        "body": "Indiquez les produits demandés, autorisés ou refusés pour chaque destinataire.",
        "why": "Ces préférences guident ASF et évitent de préparer des produits inadaptés.",
        "blockers": [
            "Demandé et autorisé nécessitent une quantité cible et une période.",
            "Refusé ne doit pas avoir de quantité ni de période.",
            "Un produit explicitement refusé peut bloquer la préparation.",
        ],
        "action_label": "Gérer les destinataires",
        "action_url": reverse_lazy("portal:portal_recipients"),
    },
    {
        "title": "Créer une demande d'expédition / transport",
        "body": (
            "Dans le portail, une demande d'expédition ou de transport se crée via "
            "Nouvelle commande."
        ),
        "why": "Cette étape rassemble destination, destinataire, contenu et demande logistique.",
        "blockers": [
            "Destination obligatoire.",
            "Destinataire obligatoire.",
            "Le destinataire est filtré selon la destination choisie.",
            "Si aucun destinataire n'apparaît, vérifiez sa création et son rattachement.",
        ],
        "action_label": "Nouvelle commande",
        "action_url": reverse_lazy("portal:portal_order_create"),
    },
    {
        "title": "Déclarer la source des colis",
        "body": (
            "Précisez les colis déjà préparés, le dépôt entrepôt, l'enlèvement demandé, "
            "les colis prêts, les kits ou les produits ASF à préparer."
        ),
        "why": "ASF utilise ces données pour organiser la préparation et le transport.",
        "blockers": [
            "Une demande vide ne peut pas être envoyée.",
            (
                "Un enlèvement requiert contact, téléphone, adresse, nombre de colis, "
                "nombre de palettes et confirmation."
            ),
            "Les colis préparés par la structure doivent respecter les consignes ASF et peuvent être contrôlés.",
            "Les lignes à stock nul peuvent être indisponibles ou seulement indicatives.",
        ],
    },
    {
        "title": "Suivre et compléter",
        "body": (
            "Suivez les statuts commande et expédition, les corrections ASF, les documents "
            "et la facturation."
        ),
        "why": "Le tableau de bord indique la prochaine étape utile.",
        "blockers": [
            "Certaines actions documentaires dépendent de la validation ASF.",
            "Les corrections demandées doivent être traitées avant de poursuivre proprement.",
        ],
        "action_label": "Voir mes commandes",
        "action_url": reverse_lazy("portal:portal_dashboard"),
        "secondary_action_label": "Voir la facturation",
        "secondary_action_url": reverse_lazy("portal:portal_billing"),
    },
]

RECIPIENT_STEPS = [
    {
        "title": "Votre espace destinataire",
        "body": (
            "Votre espace regroupe la fiche structure, l'escale de livraison, les référents, "
            "les documents et les besoins produits."
        ),
        "why": "Ces informations aident ASF et les expéditeurs à préparer les demandes.",
        "blockers": [],
    },
    {
        "title": "Vérifier la fiche structure",
        "body": "Relisez l'identité, l'escale, l'adresse, les bénéficiaires, les notes et le statut.",
        "why": "Une fiche claire limite les échanges de correction avec ASF.",
        "blockers": [
            "Des informations incomplètes ou non validées peuvent ralentir le traitement ASF.",
        ],
        "action_label": "Modifier ma fiche",
        "action_url": reverse_lazy("portal:portal_recipient_profile"),
    },
    {
        "title": "Mettre à jour référents et documents",
        "body": "Maintenez les contacts et documents utilisés par ASF et les expéditeurs.",
        "why": "Les référents fiables accélèrent les validations et le suivi.",
        "blockers": [
            "Documents structure manquants.",
            "Documents non conformes.",
            "Revue ASF encore en attente.",
        ],
        "action_label": "Modifier ma fiche",
        "action_url": reverse_lazy("portal:portal_recipient_profile"),
    },
    {
        "title": "Déclarer besoins et refus produits",
        "body": "Renseignez les produits demandés, autorisés ou refusés, avec quantité et période.",
        "why": "Ces règles guident les préparations et évitent les produits inadaptés.",
        "blockers": [
            "Demandé et autorisé nécessitent une quantité et une période.",
            "Refusé ne doit pas avoir de quantité ni de période.",
            "Supprimer une règle retire seulement la préférence explicite.",
        ],
        "action_label": "Gérer les préférences",
        "action_url": reverse_lazy("portal:portal_recipient_preferences"),
    },
    {
        "title": "Comprendre l'impact côté ASF / expéditeur",
        "body": "Vos données guident les demandes expéditeurs et les préparations ASF.",
        "why": "Un refus explicite peut empêcher l'ajout du produit dans une préparation.",
        "blockers": [
            "Un produit refusé peut bloquer une préparation côté expéditeur ou ASF.",
        ],
    },
]


def _scope_key_and_target(scope):
    if scope is None:
        return "", {}
    association_profile_id = getattr(scope.association_profile, "id", None)
    recipient_organization_id = getattr(scope.recipient_organization, "id", None)
    shipper_id = getattr(scope.shipper, "id", None)
    if scope.source == PORTAL_SCOPE_SOURCE_LEGACY_ASSOCIATION and association_profile_id:
        return f"association_profile:{association_profile_id}", {
            "association_profile": scope.association_profile
        }
    if scope.role == PortalAccessRole.RECIPIENT_ADMIN and recipient_organization_id:
        return f"recipient:{recipient_organization_id}", {
            "recipient_organization": scope.recipient_organization
        }
    if scope.role == PortalAccessRole.SHIPPER_ADMIN and shipper_id:
        return f"shipper:{shipper_id}", {"shipper": scope.shipper}
    if association_profile_id:
        return f"association_profile:{association_profile_id}", {
            "association_profile": scope.association_profile
        }
    return "", {}


def _session_seen_keys(request) -> set[str]:
    raw_seen = request.session.get(PORTAL_ONBOARDING_SEEN_SESSION_KEY) or []
    if isinstance(raw_seen, dict):
        return {str(key) for key, value in raw_seen.items() if value}
    if isinstance(raw_seen, list | tuple | set):
        return {str(value) for value in raw_seen}
    return set()


def _mark_session_scope_seen(request, scope_key: str) -> None:
    if not scope_key:
        return
    seen_keys = _session_seen_keys(request)
    seen_keys.add(scope_key)
    request.session[PORTAL_ONBOARDING_SEEN_SESSION_KEY] = sorted(seen_keys)
    request.session.modified = True


def _preference_for_request(request):
    scope = getattr(request, "portal_scope", None)
    if scope is None:
        return None, ""
    scope_key, target = _scope_key_and_target(scope)
    if not scope_key or not target:
        return None, scope_key
    preference, _created = PortalOnboardingPreference.objects.get_or_create(
        user=request.user,
        role=scope.role,
        defaults=target,
        **target,
    )
    return preference, scope_key


def _payload_for_role(role: str) -> dict:
    if role == PortalAccessRole.RECIPIENT_ADMIN:
        return {
            "role": PortalAccessRole.RECIPIENT_ADMIN,
            "title": "Tutoriel destinataire",
            "steps": RECIPIENT_STEPS,
        }
    return {
        "role": PortalAccessRole.SHIPPER_ADMIN,
        "title": "Tutoriel expéditeur",
        "steps": SHIPPER_STEPS,
    }


def build_portal_onboarding_context(request):
    preference, scope_key = _preference_for_request(request)
    if preference is None:
        return None
    payload = _payload_for_role(preference.role)
    seen_in_session = scope_key in _session_seen_keys(request)
    payload.update(
        {
            "auto_open": bool(preference.show_on_next_login and not seen_in_session),
            "show_on_next_login": preference.show_on_next_login,
            "scope_key": scope_key,
        }
    )
    return payload


def mark_portal_onboarding_seen(request, *, show_on_next_login: bool):
    preference, scope_key = _preference_for_request(request)
    if preference is None:
        return None
    preference.show_on_next_login = bool(show_on_next_login)
    preference.last_seen_at = timezone.now()
    preference.save(update_fields=["show_on_next_login", "last_seen_at", "updated_at"])
    _mark_session_scope_seen(request, scope_key)
    return preference
