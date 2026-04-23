import importlib
import importlib.util

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Valide la configuration runtime Sentry sans envoyer d'evenement par defaut."

    def add_arguments(self, parser):
        parser.add_argument(
            "--allow-missing",
            action="store_true",
            help="Retourne OK si SENTRY_DSN n'est pas configure.",
        )
        parser.add_argument(
            "--send-test",
            action="store_true",
            help="Envoie un message de test a Sentry. A utiliser uniquement apres validation du DSN.",
        )
        parser.add_argument(
            "--flush-timeout",
            type=float,
            default=2.0,
            help="Timeout de flush Sentry en secondes pour --send-test.",
        )

    def handle(self, *args, **options):
        dsn = getattr(settings, "SENTRY_DSN", "")
        if not dsn:
            if options["allow_missing"]:
                self.stdout.write(self.style.WARNING("Sentry runtime: SENTRY_DSN absent, skip OK."))
                return
            raise CommandError("SENTRY_DSN n'est pas configure.")

        if importlib.util.find_spec("sentry_sdk") is None:
            raise CommandError("Le paquet sentry-sdk n'est pas installe.")

        traces_sample_rate = getattr(settings, "SENTRY_TRACES_SAMPLE_RATE", None)

        self.stdout.write(
            "Sentry runtime snapshot: "
            f"environment={getattr(settings, 'SENTRY_ENVIRONMENT', '')}, "
            f"release={getattr(settings, 'SENTRY_RELEASE', '') or '-'}, "
            f"sample_rate={getattr(settings, 'SENTRY_SAMPLE_RATE', '')}, "
            f"traces_sample_rate={traces_sample_rate if traces_sample_rate is not None else '-'}, "
            f"send_default_pii={getattr(settings, 'SENTRY_SEND_DEFAULT_PII', False)}."
        )

        if options["send_test"]:
            sentry_sdk = importlib.import_module("sentry_sdk")
            sentry_sdk.capture_message("ASF WMS Sentry runtime check")
            sentry_sdk.flush(timeout=options["flush_timeout"])
            self.stdout.write(self.style.SUCCESS("Sentry runtime: test event sent."))
            return

        self.stdout.write(self.style.SUCCESS("Sentry runtime: OK."))
