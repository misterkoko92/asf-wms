from django.contrib.auth import get_user_model
from django.test import TestCase

from wms.models import VolunteerConstraint, VolunteerProfile


class VolunteerPlanningInputTests(TestCase):
    def test_constraint_stores_max_colis_vol(self):
        user = get_user_model().objects.create_user(
            username="volunteer@example.com",
            email="volunteer@example.com",
            password="pass1234",  # pragma: allowlist secret
        )
        profile = VolunteerProfile.objects.create(user=user)

        constraint = VolunteerConstraint.objects.create(
            volunteer=profile,
            max_colis_vol=4,
        )

        self.assertEqual(constraint.max_colis_vol, 4)
