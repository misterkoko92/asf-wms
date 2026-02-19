from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand, CommandError

from contacts.models import ContactType
from wms.models import AssociationProfile, AssociationRecipient
from wms.portal_permissions import ASSOCIATION_PORTAL_GROUP_NAME


class Command(BaseCommand):
    help = (
        "Audit des profils association du portail: cohérence user/contact, "
        "permissions, email et règles minimales de fonctionnement."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--fail-on-issues",
            action="store_true",
            help="Retourne un code d'erreur s'il existe au moins une anomalie.",
        )

    def handle(self, *args, **options):
        fail_on_issues = options["fail_on_issues"]
        issue_count = 0

        group = Group.objects.filter(name=ASSOCIATION_PORTAL_GROUP_NAME).first()
        profiles = (
            AssociationProfile.objects.select_related("user", "contact")
            .prefetch_related("contact__addresses")
            .order_by("id")
        )
        active_delivery_contact_ids = set(
            AssociationRecipient.objects.filter(
                is_active=True,
                is_delivery_contact=True,
            ).values_list("association_contact_id", flat=True)
        )

        self.stdout.write(
            self.style.MIGRATE_HEADING(
                f"Audit profils association: {profiles.count()} profil(s) analysé(s)."
            )
        )

        for profile in profiles:
            profile_issues = []
            user = profile.user
            contact = profile.contact
            if contact.contact_type != ContactType.ORGANIZATION:
                profile_issues.append("contact non organisation")
            if not contact.is_active:
                profile_issues.append("contact inactif")
            if not user.is_active:
                profile_issues.append("utilisateur inactif")
            if (user.email or "").strip() != (contact.email or "").strip():
                profile_issues.append("email user/contact incohérent")
            if contact.get_effective_address() is None:
                profile_issues.append("adresse manquante")
            if contact.id not in active_delivery_contact_ids:
                profile_issues.append("aucun destinataire portail avec contact réception actif")
            if group and not user.groups.filter(pk=group.pk).exists():
                profile_issues.append("groupe Association_Portail manquant")

            if profile_issues:
                issue_count += len(profile_issues)
                self.stdout.write(
                    self.style.WARNING(
                        f"- Profile #{profile.id} ({user.username} / {contact.name}): "
                        + "; ".join(profile_issues)
                    )
                )

        User = get_user_model()
        if group:
            orphan_users = (
                User.objects.filter(groups=group)
                .filter(association_profile__isnull=True)
                .order_by("username")
            )
            for user in orphan_users:
                issue_count += 1
                self.stdout.write(
                    self.style.WARNING(
                        f"- Utilisateur {user.username}: groupe Association_Portail sans profil association"
                    )
                )
        else:
            issue_count += 1
            self.stdout.write(
                self.style.WARNING("- Groupe Association_Portail absent")
            )

        if issue_count == 0:
            self.stdout.write(self.style.SUCCESS("Aucune anomalie détectée."))
            return

        self.stdout.write(
            self.style.WARNING(f"{issue_count} anomalie(s) détectée(s).")
        )
        if fail_on_issues:
            raise CommandError("Audit en échec: anomalies détectées.")
