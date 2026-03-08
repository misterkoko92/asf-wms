from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from wms.models import PlanningRun, PlanningVersion


class PlanningModelTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="planner@example.com",
            email="planner@example.com",
            password="pass1234",  # pragma: allowlist secret
        )
        self.run = PlanningRun.objects.create(
            week_start="2026-03-09",
            week_end="2026-03-15",
            created_by=self.user,
        )

    def test_version_number_increments_per_run(self):
        v1 = PlanningVersion.objects.create(run=self.run, created_by=self.user)
        v2 = PlanningVersion.objects.create(run=self.run, created_by=self.user)

        self.assertEqual(v1.number, 1)
        self.assertEqual(v2.number, 2)

    def test_published_version_cannot_be_modified(self):
        version = PlanningVersion.objects.create(
            run=self.run,
            status="published",
            created_by=self.user,
        )

        version.change_reason = "Friday update"

        with self.assertRaises(ValidationError) as exc:
            version.full_clean()

        self.assertIn("__all__", exc.exception.message_dict)

    def test_based_on_link_is_persisted(self):
        original = PlanningVersion.objects.create(
            run=self.run,
            created_by=self.user,
        )

        cloned = PlanningVersion.objects.create(
            run=self.run,
            based_on=original,
            created_by=self.user,
        )

        self.assertEqual(cloned.based_on, original)
