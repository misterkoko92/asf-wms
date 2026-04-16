def build_scan_list_url(base_url, params, *, page=None, updates=None, reset_keys=None):
    query = params.copy()

    for key in reset_keys or set():
        query.pop(key, None)

    for key, value in (updates or {}).items():
        if value in (None, "", False):
            query.pop(key, None)
        else:
            query[key] = str(value)

    if page is None or page <= 1:
        query.pop("page", None)
    else:
        query["page"] = str(page)

    encoded = query.urlencode()
    return f"{base_url}?{encoded}" if encoded else base_url
