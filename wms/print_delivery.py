def delivery_mode(request):
    return (request.GET.get("delivery") or "").strip().lower() or "html"


def wants_external_pdf(request):
    return delivery_mode(request) == "pdf"
