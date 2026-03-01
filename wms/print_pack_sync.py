import os
from urllib import error, parse, request

from django.conf import settings

from .models import GeneratedPrintArtifact, GeneratedPrintArtifactStatus
from .print_pack_graph import get_client_credentials_token

PROCESS_RESULT_SELECTED = "selected"
PROCESS_RESULT_PROCESSED = "processed"
PROCESS_RESULT_FAILED = "failed"
PROCESS_RESULT_RETRIED = "retried"

DEFAULT_PROCESS_LIMIT = 20
DEFAULT_MAX_ATTEMPTS = 5


class PrintArtifactSyncError(RuntimeError):
    """Raised when a generated print artifact cannot be synced."""


def _safe_int(value, *, default, minimum):
    try:
        int_value = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, int_value)


def _resolve_timeout(timeout):
    return _safe_int(
        timeout if timeout is not None else getattr(settings, "GRAPH_REQUEST_TIMEOUT_SECONDS", 30),
        default=30,
        minimum=1,
    )


def _resolve_max_attempts(max_attempts):
    return _safe_int(max_attempts, default=DEFAULT_MAX_ATTEMPTS, minimum=1)


def _validate_https_url(url):
    parsed = parse.urlparse(url)
    if parsed.scheme != "https":
        raise PrintArtifactSyncError("OneDrive endpoint must use HTTPS.")


def _artifact_filename(artifact):
    filename = os.path.basename((artifact.pdf_file.name or "").strip())
    if not filename:
        filename = f"print-pack-{artifact.pack_code}-{artifact.id}.pdf"
    if not filename.lower().endswith(".pdf"):
        filename = f"{filename}.pdf"
    return filename


def _artifact_relative_dir(artifact):
    base_dir = (getattr(settings, "GRAPH_WORK_DIR", "") or "").strip().strip("/")
    parts = [base_dir] if base_dir else []
    if artifact.shipment and artifact.shipment.reference:
        parts.extend(["shipments", artifact.shipment.reference])
    elif artifact.carton and artifact.carton.code:
        parts.extend(["cartons", artifact.carton.code])
    else:
        parts.extend(["packs", (artifact.pack_code or "unknown").strip() or "unknown"])
    return "/".join(part for part in parts if part)


def _artifact_onedrive_path(artifact):
    relative_dir = _artifact_relative_dir(artifact)
    filename = _artifact_filename(artifact)
    if relative_dir:
        return f"{relative_dir}/{filename}"
    return filename


def _upload_artifact_pdf_to_onedrive(*, artifact, timeout):
    drive_id = (getattr(settings, "GRAPH_DRIVE_ID", "") or "").strip()
    if not drive_id:
        raise PrintArtifactSyncError("Missing GRAPH_DRIVE_ID for OneDrive upload.")
    if not artifact.pdf_file:
        raise PrintArtifactSyncError("Artifact has no PDF file to upload.")

    token = get_client_credentials_token(timeout=timeout)
    onedrive_path = _artifact_onedrive_path(artifact)
    encoded_path = parse.quote(onedrive_path, safe="/")
    url = f"https://graph.microsoft.com/v1.0/drives/{drive_id}/root:/{encoded_path}:/content"
    _validate_https_url(url)

    with artifact.pdf_file.open("rb") as stream:
        pdf_bytes = stream.read()
    if not pdf_bytes:
        raise PrintArtifactSyncError("Artifact PDF payload is empty.")

    req = request.Request(
        url,
        data=pdf_bytes,
        method="PUT",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/pdf",
        },
    )
    try:
        with request.urlopen(req, timeout=timeout) as response:  # nosec B310
            response.read()
            status_code = getattr(response, "status", 200)
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore")
        message = body or str(exc)
        raise PrintArtifactSyncError(
            f"OneDrive upload failed with HTTP {exc.code}: {message}"
        ) from exc
    except error.URLError as exc:
        raise PrintArtifactSyncError(f"OneDrive upload failed: {exc}") from exc

    if status_code not in (200, 201):
        raise PrintArtifactSyncError(
            f"OneDrive upload failed with unexpected status code {status_code}."
        )
    return onedrive_path


def _apply_sync_success(*, artifact, onedrive_path):
    artifact.status = GeneratedPrintArtifactStatus.SYNCED
    artifact.sync_attempts = artifact.sync_attempts + 1
    artifact.onedrive_path = onedrive_path
    artifact.last_sync_error = ""
    artifact.save(
        update_fields=["status", "sync_attempts", "onedrive_path", "last_sync_error"]
    )


def _apply_sync_failure(*, artifact, error_message, max_attempts):
    artifact.sync_attempts = artifact.sync_attempts + 1
    artifact.last_sync_error = str(error_message)
    if artifact.sync_attempts >= max_attempts:
        artifact.status = GeneratedPrintArtifactStatus.SYNC_FAILED
        outcome = PROCESS_RESULT_FAILED
    else:
        artifact.status = GeneratedPrintArtifactStatus.SYNC_PENDING
        outcome = PROCESS_RESULT_RETRIED
    artifact.save(update_fields=["status", "sync_attempts", "last_sync_error"])
    return outcome


def process_print_artifact_queue(
    *,
    limit=DEFAULT_PROCESS_LIMIT,
    include_failed=False,
    max_attempts=None,
    timeout=None,
):
    safe_limit = _safe_int(limit, default=DEFAULT_PROCESS_LIMIT, minimum=1)
    resolved_max_attempts = _resolve_max_attempts(max_attempts)
    resolved_timeout = _resolve_timeout(timeout)

    statuses = [GeneratedPrintArtifactStatus.SYNC_PENDING]
    if include_failed:
        statuses.append(GeneratedPrintArtifactStatus.SYNC_FAILED)

    artifacts = list(
        GeneratedPrintArtifact.objects.filter(status__in=statuses)
        .order_by("created_at", "id")[:safe_limit]
    )

    result = {
        PROCESS_RESULT_SELECTED: 0,
        PROCESS_RESULT_PROCESSED: 0,
        PROCESS_RESULT_FAILED: 0,
        PROCESS_RESULT_RETRIED: 0,
    }
    for artifact in artifacts:
        result[PROCESS_RESULT_SELECTED] += 1
        try:
            onedrive_path = _upload_artifact_pdf_to_onedrive(
                artifact=artifact,
                timeout=resolved_timeout,
            )
        except PrintArtifactSyncError as exc:
            outcome = _apply_sync_failure(
                artifact=artifact,
                error_message=exc,
                max_attempts=resolved_max_attempts,
            )
            result[outcome] += 1
            continue

        _apply_sync_success(artifact=artifact, onedrive_path=onedrive_path)
        result[PROCESS_RESULT_PROCESSED] += 1
    return result
