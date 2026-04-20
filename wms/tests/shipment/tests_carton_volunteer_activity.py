from django.contrib.auth import get_user_model
from django.test import TestCase

from wms.carton_activity import find_last_carton_for_volunteer, record_carton_volunteer_activity
from wms.models import (
    Carton,
    CartonStatus,
    CartonVolunteerActivity,
    CartonVolunteerActivityAction,
    VolunteerProfile,
)

TEST_PASSWORD = "pass1234"  # pragma: allowlist secret


class CartonVolunteerActivityTests(TestCase):
    def setUp(self):
        self.actor = get_user_model().objects.create_user(
            username="carton-activity-actor",
            password=TEST_PASSWORD,
            is_staff=True,
        )
        volunteer_user = get_user_model().objects.create_user(
            username="carton-activity-volunteer",
            password=TEST_PASSWORD,
            first_name="Martin",
            last_name="Dupond",
        )
        self.volunteer = VolunteerProfile.objects.create(user=volunteer_user, is_active=True)

    def test_record_carton_volunteer_activity_stores_prepared_and_edited_entries(self):
        carton = Carton.objects.create(
            code="CT-ACTIVITY-01",
            status=CartonStatus.PACKED,
            prepared_by=self.volunteer.user,
        )

        record_carton_volunteer_activity(
            carton=carton,
            volunteer=self.volunteer,
            action=CartonVolunteerActivityAction.PREPARED,
            actor=self.actor,
        )
        record_carton_volunteer_activity(
            carton=carton,
            volunteer=self.volunteer,
            action=CartonVolunteerActivityAction.EDITED,
            actor=self.actor,
        )

        self.assertEqual(
            CartonVolunteerActivity.objects.filter(
                carton=carton,
                volunteer=self.volunteer,
            ).count(),
            2,
        )
        latest_activity = CartonVolunteerActivity.objects.filter(carton=carton).first()
        self.assertEqual(latest_activity.action, CartonVolunteerActivityAction.EDITED)
        self.assertEqual(latest_activity.actor, self.actor)

    def test_find_last_carton_for_volunteer_prefers_latest_non_shipped_carton(self):
        packed_carton = Carton.objects.create(
            code="CT-ACTIVITY-PACKED",
            status=CartonStatus.PACKED,
            prepared_by=self.volunteer.user,
        )
        shipped_carton = Carton.objects.create(
            code="CT-ACTIVITY-SHIPPED",
            status=CartonStatus.SHIPPED,
            prepared_by=self.volunteer.user,
        )

        record_carton_volunteer_activity(
            carton=packed_carton,
            volunteer=self.volunteer,
            action=CartonVolunteerActivityAction.PREPARED,
            actor=self.actor,
        )
        record_carton_volunteer_activity(
            carton=shipped_carton,
            volunteer=self.volunteer,
            action=CartonVolunteerActivityAction.EDITED,
            actor=self.actor,
        )

        self.assertEqual(find_last_carton_for_volunteer(self.volunteer), packed_carton)

    def test_record_carton_volunteer_activity_ignores_missing_inputs_and_invalid_actor(self):
        saved_carton = Carton.objects.create(
            code="CT-ACTIVITY-SAVED",
            status=CartonStatus.PACKED,
            prepared_by=self.volunteer.user,
        )
        unsaved_carton = Carton(
            code="CT-ACTIVITY-UNSAVED",
            status=CartonStatus.DRAFT,
            prepared_by=self.volunteer.user,
        )
        unsaved_volunteer_user = get_user_model()(
            username="carton-activity-unsaved-volunteer",
            first_name="Noah",
            last_name="Ghost",
        )
        unsaved_volunteer = VolunteerProfile(user=unsaved_volunteer_user, is_active=True)

        self.assertIsNone(
            record_carton_volunteer_activity(
                carton=None,
                volunteer=self.volunteer,
                action=CartonVolunteerActivityAction.PREPARED,
            )
        )
        self.assertIsNone(
            record_carton_volunteer_activity(
                carton=unsaved_carton,
                volunteer=self.volunteer,
                action=CartonVolunteerActivityAction.PREPARED,
            )
        )
        self.assertIsNone(
            record_carton_volunteer_activity(
                carton=saved_carton,
                volunteer=None,
                action=CartonVolunteerActivityAction.PREPARED,
            )
        )
        self.assertIsNone(
            record_carton_volunteer_activity(
                carton=saved_carton,
                volunteer=unsaved_volunteer,
                action=CartonVolunteerActivityAction.PREPARED,
            )
        )

        activity = record_carton_volunteer_activity(
            carton=saved_carton,
            volunteer=self.volunteer,
            action=CartonVolunteerActivityAction.EDITED,
            actor="not-a-model",
        )

        self.assertIsNotNone(activity)
        self.assertIsNone(activity.actor)

    def test_find_last_carton_for_volunteer_falls_back_to_latest_shipped_activity(self):
        shipped_carton = Carton.objects.create(
            code="CT-ACTIVITY-SHIPPED-ONLY",
            status=CartonStatus.SHIPPED,
            prepared_by=self.volunteer.user,
        )
        record_carton_volunteer_activity(
            carton=shipped_carton,
            volunteer=self.volunteer,
            action=CartonVolunteerActivityAction.PREPARED,
            actor=self.actor,
        )

        self.assertEqual(find_last_carton_for_volunteer(self.volunteer), shipped_carton)
