from django import forms
from django.test import SimpleTestCase
from rest_framework import serializers, status

from api.v1.ui_api_errors import (
    _to_plain_errors,
    api_error,
    form_error_payload,
    serializer_field_errors,
)


class _RequiredNameSerializer(serializers.Serializer):
    name = serializers.CharField(required=True)


class _FieldErrorForm(forms.Form):
    email = forms.EmailField(required=True)


class _NonFieldErrorForm(forms.Form):
    email = forms.EmailField(required=False)

    def clean(self):
        cleaned_data = super().clean()
        raise forms.ValidationError("Global validation error")
        return cleaned_data


class UiApiErrorsTests(SimpleTestCase):
    def test_to_plain_errors_normalizes_nested_values(self):
        value = {
            "field": [1, {"nested": ["x", 2]}],
            "other": ("a", {"key": 3}),
        }

        self.assertEqual(
            _to_plain_errors(value),
            {
                "field": ["1", {"nested": ["x", "2"]}],
                "other": ["a", {"key": "3"}],
            },
        )

    def test_serializer_field_errors_returns_plain_payload(self):
        serializer = _RequiredNameSerializer(data={})
        self.assertFalse(serializer.is_valid())

        errors = serializer_field_errors(serializer)
        self.assertIn("name", errors)
        self.assertEqual(len(errors["name"]), 1)
        self.assertIsInstance(errors["name"][0], str)

    def test_form_error_payload_splits_field_and_non_field_errors(self):
        field_form = _FieldErrorForm(data={"email": "invalid-email"})
        self.assertFalse(field_form.is_valid())
        field_errors, non_field_errors = form_error_payload(field_form)
        self.assertIn("email", field_errors)
        self.assertEqual(non_field_errors, [])

        non_field_form = _NonFieldErrorForm(data={"email": "user@example.org"})
        self.assertFalse(non_field_form.is_valid())
        field_errors, non_field_errors = form_error_payload(non_field_form)
        self.assertEqual(field_errors, {})
        self.assertEqual(non_field_errors, ["Global validation error"])

    def test_api_error_builds_default_and_extended_payloads(self):
        default_response = api_error(message="Bad request", code="invalid_request")
        self.assertEqual(default_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(default_response.data["ok"], False)
        self.assertEqual(default_response.data["field_errors"], {})
        self.assertEqual(default_response.data["non_field_errors"], [])

        extended_response = api_error(
            message="Validation failed",
            code="validation_error",
            http_status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            field_errors={"email": ["Invalid email"]},
            non_field_errors=["Cannot continue"],
            extra={"trace_id": "trace-123"},
        )
        self.assertEqual(
            extended_response.status_code,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
        self.assertEqual(extended_response.data["trace_id"], "trace-123")
        self.assertEqual(
            extended_response.data["field_errors"],
            {"email": ["Invalid email"]},
        )
        self.assertEqual(
            extended_response.data["non_field_errors"],
            ["Cannot continue"],
        )
