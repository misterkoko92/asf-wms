from .upload_utils import validate_upload


def validate_document_upload(request, *, doc_type_choices, file_field="doc_file"):
    doc_type = (request.POST.get("doc_type") or "").strip()
    valid_types = {choice[0] for choice in doc_type_choices}
    if doc_type not in valid_types:
        return None, "Type de document invalide."
    uploaded = request.FILES.get(file_field)
    if not uploaded:
        return None, "Fichier requis."
    validation_error = validate_upload(uploaded)
    if validation_error:
        return None, validation_error
    return (doc_type, uploaded), None
