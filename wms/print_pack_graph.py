import json
import uuid
from urllib import error, parse, request

from django.conf import settings


class GraphPdfConversionError(RuntimeError):
    """Raised when the Graph XLSX->PDF conversion cannot be completed."""


def _validate_https_url(url):
    parsed = parse.urlparse(url)
    if parsed.scheme != "https":
        raise GraphPdfConversionError("Graph endpoint must use HTTPS.")


def _read_graph_drive_id():
    drive_id = (getattr(settings, "GRAPH_DRIVE_ID", "") or "").strip()
    if not drive_id:
        raise GraphPdfConversionError("Missing GRAPH_DRIVE_ID for Graph conversion.")
    return drive_id


def _read_graph_credentials():
    tenant_id = (getattr(settings, "GRAPH_TENANT_ID", "") or "").strip()
    client_id = (getattr(settings, "GRAPH_CLIENT_ID", "") or "").strip()
    client_secret = (getattr(settings, "GRAPH_CLIENT_SECRET", "") or "").strip()
    if not tenant_id or not client_id or not client_secret:
        raise GraphPdfConversionError(
            "Missing Microsoft Graph credentials (GRAPH_TENANT_ID/GRAPH_CLIENT_ID/GRAPH_CLIENT_SECRET)."
        )
    return tenant_id, client_id, client_secret


def _request_graph_token(*, tenant_id, client_id, client_secret, timeout):
    url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
    _validate_https_url(url)
    payload = parse.urlencode(
        {
            "client_id": client_id,
            "client_secret": client_secret,
            "grant_type": "client_credentials",
            "scope": "https://graph.microsoft.com/.default",
        }
    ).encode("utf-8")
    req = request.Request(
        url,
        data=payload,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with request.urlopen(req, timeout=timeout) as response:  # nosec B310
            body = response.read().decode("utf-8")
    except error.URLError as exc:
        raise GraphPdfConversionError(f"Unable to fetch Graph token: {exc}") from exc

    try:
        token_payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise GraphPdfConversionError("Invalid Graph token response payload.") from exc

    access_token = token_payload.get("access_token")
    if not access_token:
        raise GraphPdfConversionError("Graph token response does not include access_token.")
    return access_token


def get_client_credentials_token(timeout=30):
    tenant_id, client_id, client_secret = _read_graph_credentials()
    return _request_graph_token(
        tenant_id=tenant_id,
        client_id=client_id,
        client_secret=client_secret,
        timeout=timeout,
    )


def _decode_http_error(exc):
    if not isinstance(exc, error.HTTPError):
        return str(exc)
    try:
        body = exc.read().decode("utf-8", errors="ignore")
    except Exception:
        body = ""
    return body or str(exc)


def _upload_workbook_item(*, token, drive_id, xlsx_bytes, filename, timeout):
    safe_filename = str(filename or "").strip() or "workbook.xlsx"
    upload_path = f"tmp/print_pack/{uuid.uuid4()}-{safe_filename}"
    encoded_path = parse.quote(upload_path, safe="/")
    url = f"https://graph.microsoft.com/v1.0/drives/{drive_id}/root:/{encoded_path}:/content"
    _validate_https_url(url)

    req = request.Request(
        url,
        data=xlsx_bytes,
        method="PUT",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        },
    )
    try:
        with request.urlopen(req, timeout=timeout) as response:  # nosec B310
            body = response.read().decode("utf-8")
    except error.HTTPError as exc:
        message = _decode_http_error(exc)
        raise GraphPdfConversionError(
            f"Graph upload failed with HTTP {exc.code}: {message}"
        ) from exc
    except error.URLError as exc:
        raise GraphPdfConversionError(f"Graph upload failed: {exc}") from exc

    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise GraphPdfConversionError("Invalid Graph upload response payload.") from exc

    item_id = payload.get("id")
    if not item_id:
        raise GraphPdfConversionError("Graph upload response does not include item id.")
    return item_id


def _download_pdf_export(*, token, drive_id, item_id, timeout):
    url = (
        f"https://graph.microsoft.com/v1.0/drives/{drive_id}/items/{item_id}/content"
        "?format=pdf"
    )
    _validate_https_url(url)
    req = request.Request(
        url,
        method="GET",
        headers={
            "Authorization": f"Bearer {token}",
        },
    )
    try:
        with request.urlopen(req, timeout=timeout) as response:  # nosec B310
            return response.read()
    except error.HTTPError as exc:
        message = _decode_http_error(exc)
        raise GraphPdfConversionError(
            f"Graph PDF export failed with HTTP {exc.code}: {message}"
        ) from exc
    except error.URLError as exc:
        raise GraphPdfConversionError(f"Graph PDF export failed: {exc}") from exc


def _delete_workbook_item(*, token, drive_id, item_id, timeout):
    url = f"https://graph.microsoft.com/v1.0/drives/{drive_id}/items/{item_id}"
    _validate_https_url(url)
    req = request.Request(
        url,
        method="DELETE",
        headers={
            "Authorization": f"Bearer {token}",
        },
    )
    try:
        with request.urlopen(req, timeout=timeout):  # nosec B310
            return
    except (error.HTTPError, error.URLError):
        # Cleanup best-effort: conversion result should not fail on cleanup issues.
        return


def _graph_export_pdf(*, token, xlsx_bytes, filename, timeout):
    drive_id = _read_graph_drive_id()
    item_id = _upload_workbook_item(
        token=token,
        drive_id=drive_id,
        xlsx_bytes=xlsx_bytes,
        filename=filename,
        timeout=timeout,
    )
    try:
        return _download_pdf_export(
            token=token,
            drive_id=drive_id,
            item_id=item_id,
            timeout=timeout,
        )
    finally:
        _delete_workbook_item(
            token=token,
            drive_id=drive_id,
            item_id=item_id,
            timeout=timeout,
        )


def convert_excel_to_pdf_via_graph(*, xlsx_bytes, filename, timeout=30):
    if not xlsx_bytes:
        raise GraphPdfConversionError("Excel payload is empty.")
    if not filename:
        raise GraphPdfConversionError("Filename is required for Graph conversion.")

    token = get_client_credentials_token(timeout=timeout)
    pdf_bytes = _graph_export_pdf(
        token=token,
        xlsx_bytes=xlsx_bytes,
        filename=filename,
        timeout=timeout,
    )
    if not isinstance(pdf_bytes, (bytes, bytearray)) or not bytes(pdf_bytes).startswith(
        b"%PDF"
    ):
        raise GraphPdfConversionError("Graph conversion did not return a valid PDF payload.")
    return bytes(pdf_bytes)
