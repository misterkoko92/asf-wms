import subprocess
from datetime import timedelta
from pathlib import Path

from django.apps import apps
from django.conf import settings
from django.db.models import Q
from django.utils import timezone

from .document_scan import DocumentScanStatus
from .models import IntegrationDirection, IntegrationEvent, IntegrationStatus

DOCUMENT_SCAN_QUEUE_SOURCE = "wms.document_scan"
DOCUMENT_SCAN_QUEUE_TARGET = "antivirus"
DOCUMENT_SCAN_QUEUE_EVENT_TYPE = "scan_document"

DOCUMENT_SCAN_RESULT_SELECTED = "selected"
DOCUMENT_SCAN_RESULT_PROCESSED = "processed"
DOCUMENT_SCAN_RESULT_INFECTED = "infected"
DOCUMENT_SCAN_RESULT_FAILED = "failed"

DOCUMENT_SCAN_DEFAULT_LIMIT = 100
DOCUMENT_SCAN_DEFAULT_PROCESSING_TIMEOUT_SECONDS = 900

DOCUMENT_SCAN_BACKEND_CLAMAV = "clamav"
DOCUMENT_SCAN_BACKEND_NOOP = "noop"


def _safe_int(value, *, default, minimum):
    try:
        int_value = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, int_value)


def _scan_backend():
    backend = str(
        getattr(settings, "DOCUMENT_SCAN_BACKEND", DOCUMENT_SCAN_BACKEND_CLAMAV)
        or DOCUMENT_SCAN_BACKEND_CLAMAV
    ).strip().lower()
    if backend in {DOCUMENT_SCAN_BACKEND_CLAMAV, DOCUMENT_SCAN_BACKEND_NOOP}:
        return backend
    return DOCUMENT_SCAN_BACKEND_CLAMAV


def _clamav_command():
    raw = str(getattr(settings, "DOCUMENT_SCAN_CLAMAV_COMMAND", "clamscan") or "").strip()
    return raw or "clamscan"


def _scan_timeout_seconds():
    return _safe_int(
        getattr(settings, "DOCUMENT_SCAN_TIMEOUT_SECONDS", 30),
        default=30,
        minimum=5,
    )


def _processing_timeout_seconds(override_seconds=None):
    source = (
        getattr(
            settings,
            "DOCUMENT_SCAN_QUEUE_PROCESSING_TIMEOUT_SECONDS",
            DOCUMENT_SCAN_DEFAULT_PROCESSING_TIMEOUT_SECONDS,
        )
        if override_seconds is None
        else override_seconds
    )
    return _safe_int(
        source,
        default=DOCUMENT_SCAN_DEFAULT_PROCESSING_TIMEOUT_SECONDS,
        minimum=1,
    )


def _coerce_limit(limit):
    return _safe_int(limit, default=DOCUMENT_SCAN_DEFAULT_LIMIT, minimum=1)


def _scan_file_with_clamav(file_path):
    command = [_clamav_command(), "--no-summary", str(file_path)]
    try:
        completed = subprocess.run(  # nosec B603 B607
            command,
            capture_output=True,
            text=True,
            timeout=_scan_timeout_seconds(),
            check=False,
        )
    except FileNotFoundError:
        return DocumentScanStatus.ERROR, "Commande ClamAV introuvable."
    except subprocess.TimeoutExpired:
        return DocumentScanStatus.ERROR, "Scan antivirus expiré."
    except Exception as exc:  # pragma: no cover - defensive
        return DocumentScanStatus.ERROR, f"Erreur scan antivirus: {exc}"

    output = (completed.stdout or completed.stderr or "").strip()
    if completed.returncode == 0:
        return DocumentScanStatus.CLEAN, output
    if completed.returncode == 1:
        return DocumentScanStatus.INFECTED, output or "Fichier infecté détecté."
    return DocumentScanStatus.ERROR, output or "Erreur inconnue du scan antivirus."


def scan_uploaded_file(file_field):
    if not file_field:
        return DocumentScanStatus.ERROR, "Fichier absent."

    try:
        file_path = file_field.path
    except Exception:
        return (
            DocumentScanStatus.ERROR,
            "Stockage non local: chemin fichier indisponible pour scan.",
        )

    if not file_path:
        return DocumentScanStatus.ERROR, "Chemin fichier indisponible."

    resolved_path = Path(file_path)
    if not resolved_path.exists():
        return DocumentScanStatus.ERROR, "Fichier introuvable."

    backend = _scan_backend()
    if backend == DOCUMENT_SCAN_BACKEND_NOOP:
        return DocumentScanStatus.CLEAN, "Scan noop (backend de test)."
    return _scan_file_with_clamav(resolved_path)


def queue_document_scan(document_obj):
    if not document_obj or not getattr(document_obj, "pk", None):
        return False
    file_field = getattr(document_obj, "file", None)
    if not file_field:
        return False

    payload = {
        "model": document_obj._meta.label,
        "pk": int(document_obj.pk),
        "file_name": str(getattr(file_field, "name", "") or ""),
    }
    IntegrationEvent.objects.create(
        direction=IntegrationDirection.OUTBOUND,
        source=DOCUMENT_SCAN_QUEUE_SOURCE,
        target=DOCUMENT_SCAN_QUEUE_TARGET,
        event_type=DOCUMENT_SCAN_QUEUE_EVENT_TYPE,
        payload=payload,
        status=IntegrationStatus.PENDING,
    )
    return True


def _base_scan_queue_queryset():
    return IntegrationEvent.objects.filter(
        direction=IntegrationDirection.OUTBOUND,
        source=DOCUMENT_SCAN_QUEUE_SOURCE,
        event_type=DOCUMENT_SCAN_QUEUE_EVENT_TYPE,
    )


def _candidate_statuses(include_failed):
    statuses = [IntegrationStatus.PENDING]
    if include_failed:
        statuses.append(IntegrationStatus.FAILED)
    return statuses


def _queue_claim_filter(*, statuses, stale_processing_before):
    return Q(status__in=statuses) | Q(
        status=IntegrationStatus.PROCESSING,
        processed_at__lte=stale_processing_before,
    )


def _claim_queue_event(
    queue_queryset,
    *,
    event,
    statuses,
    stale_processing_before,
):
    return queue_queryset.filter(pk=event.pk).filter(
        _queue_claim_filter(
            statuses=statuses,
            stale_processing_before=stale_processing_before,
        )
    ).update(
        status=IntegrationStatus.PROCESSING,
        processed_at=timezone.now(),
        error_message="",
    )


def _resolve_document_instance(payload):
    if not isinstance(payload, dict):
        return None, "Payload de scan invalide."
    model_label = (payload.get("model") or "").strip()
    object_id = payload.get("pk")
    if not model_label:
        return None, "Payload sans modèle de document."
    if object_id in {None, ""}:
        return None, "Payload sans identifiant document."
    try:
        model_class = apps.get_model(model_label)
    except Exception:
        return None, f"Modèle document inconnu: {model_label}."
    if model_class is None:
        return None, f"Modèle document introuvable: {model_label}."
    document_obj = model_class.objects.filter(pk=object_id).first()
    if document_obj is None:
        return None, f"Document introuvable: {model_label}#{object_id}."
    return document_obj, ""


def _update_document_scan_state(document_obj, *, status, message):
    fields = []
    if getattr(document_obj, "scan_status", None) != status:
        document_obj.scan_status = status
        fields.append("scan_status")
    truncated_message = (message or "")[:255]
    if getattr(document_obj, "scan_message", "") != truncated_message:
        document_obj.scan_message = truncated_message
        fields.append("scan_message")
    now = timezone.now()
    document_obj.scan_updated_at = now
    fields.append("scan_updated_at")
    document_obj.save(update_fields=fields)


def process_document_scan_queue(
    *,
    limit=DOCUMENT_SCAN_DEFAULT_LIMIT,
    include_failed=False,
    processing_timeout_seconds=None,
):
    safe_limit = _coerce_limit(limit)
    timeout_seconds = _processing_timeout_seconds(processing_timeout_seconds)
    now = timezone.now()
    stale_processing_before = now - timedelta(seconds=timeout_seconds)
    statuses = _candidate_statuses(include_failed)

    queue_queryset = _base_scan_queue_queryset()
    selector_queryset = (
        queue_queryset.filter(
            _queue_claim_filter(
                statuses=statuses,
                stale_processing_before=stale_processing_before,
            )
        )
        .order_by("created_at", "id")[:safe_limit]
    )

    selected_events = []
    result = {
        DOCUMENT_SCAN_RESULT_SELECTED: 0,
        DOCUMENT_SCAN_RESULT_PROCESSED: 0,
        DOCUMENT_SCAN_RESULT_INFECTED: 0,
        DOCUMENT_SCAN_RESULT_FAILED: 0,
    }

    for event in selector_queryset:
        claimed = _claim_queue_event(
            queue_queryset,
            event=event,
            statuses=statuses,
            stale_processing_before=stale_processing_before,
        )
        if not claimed:
            continue
        event.status = IntegrationStatus.PROCESSING
        selected_events.append(event)
        result[DOCUMENT_SCAN_RESULT_SELECTED] += 1

    for event in selected_events:
        document_obj, resolution_error = _resolve_document_instance(event.payload or {})
        if resolution_error:
            event.status = IntegrationStatus.FAILED
            event.error_message = resolution_error
            event.processed_at = timezone.now()
            event.save(update_fields=["status", "error_message", "processed_at"])
            result[DOCUMENT_SCAN_RESULT_FAILED] += 1
            continue

        scan_status, scan_message = scan_uploaded_file(getattr(document_obj, "file", None))
        _update_document_scan_state(
            document_obj,
            status=scan_status,
            message=scan_message,
        )

        event.payload = {
            **(event.payload or {}),
            "scan_status": scan_status,
            "scan_message": (scan_message or "")[:255],
            "scanned_at": timezone.now().isoformat(),
        }
        event.processed_at = timezone.now()

        if scan_status == DocumentScanStatus.CLEAN:
            event.status = IntegrationStatus.PROCESSED
            event.error_message = ""
            result[DOCUMENT_SCAN_RESULT_PROCESSED] += 1
        elif scan_status == DocumentScanStatus.INFECTED:
            event.status = IntegrationStatus.PROCESSED
            event.error_message = "Fichier infecté: accès bloqué."
            result[DOCUMENT_SCAN_RESULT_INFECTED] += 1
        else:
            event.status = IntegrationStatus.FAILED
            event.error_message = (scan_message or "Erreur scan antivirus.")[:255]
            result[DOCUMENT_SCAN_RESULT_FAILED] += 1

        event.save(update_fields=["status", "error_message", "processed_at", "payload"])

    return result
