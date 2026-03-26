def delivery_mode(request):
    return (request.GET.get("delivery") or "").strip().lower() or "html"


def wants_external_pdf(request):
    return delivery_mode(request) == "pdf"


def wants_browser_print(request, *, default=False):
    mode = (request.GET.get("delivery") or "").strip().lower()
    if mode:
        return mode == "html"
    return default
