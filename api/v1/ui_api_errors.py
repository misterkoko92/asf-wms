from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from django import forms
from rest_framework import status
from rest_framework.response import Response


def _to_plain_errors(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _to_plain_errors(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [str(item) if not isinstance(item, (Mapping, Sequence)) else _to_plain_errors(item) for item in value]
    return str(value)


def serializer_field_errors(serializer) -> dict[str, Any]:
    return _to_plain_errors(serializer.errors)


def form_error_payload(form: forms.Form) -> tuple[dict[str, list[str]], list[str]]:
    field_errors: dict[str, list[str]] = {}
    non_field_errors: list[str] = []
    for field, errors in form.errors.items():
        messages = [str(message) for message in errors]
        if field == "__all__":
            non_field_errors.extend(messages)
        else:
            field_errors[field] = messages
    return field_errors, non_field_errors


def api_error(
    *,
    message: str,
    code: str,
    http_status: int = status.HTTP_400_BAD_REQUEST,
    field_errors: dict[str, Any] | None = None,
    non_field_errors: list[str] | None = None,
    extra: dict[str, Any] | None = None,
) -> Response:
    payload: dict[str, Any] = {
        "ok": False,
        "code": code,
        "message": message,
        "field_errors": field_errors or {},
        "non_field_errors": non_field_errors or [],
    }
    if extra:
        payload.update(extra)
    return Response(payload, status=http_status)
