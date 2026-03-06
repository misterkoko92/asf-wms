from django.conf import settings


def _get_trusted_proxy_ips() -> set[str]:
    configured = getattr(settings, "TRUSTED_PROXY_IPS", [])
    if isinstance(configured, str):
        configured = [part.strip() for part in configured.split(",") if part.strip()]
    return {str(value).strip() for value in configured if str(value).strip()}


def get_client_ip(request) -> str:
    remote_addr = (request.META.get("REMOTE_ADDR") or "").strip()
    forwarded = (request.META.get("HTTP_X_FORWARDED_FOR") or "").strip()
    if not forwarded:
        return remote_addr or "unknown"

    trusted_proxy_ips = _get_trusted_proxy_ips()
    if remote_addr not in trusted_proxy_ips:
        return remote_addr or "unknown"

    for part in forwarded.split(","):
        candidate = part.strip()
        if candidate:
            return candidate
    return remote_addr or "unknown"
