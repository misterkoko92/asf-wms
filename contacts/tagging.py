import re
import unicodedata


TAG_DONOR = ("donateur", "donateurs")
TAG_TRANSPORTER = ("transporteur", "transporteurs")
TAG_SHIPPER = ("expediteur", "expediteurs", "expéditeur", "expéditeurs")
TAG_RECIPIENT = (
    "destinataire",
    "destinataires",
    "beneficiaire",
    "beneficiaires",
    "bénéficiaire",
    "bénéficiaires",
)
TAG_CORRESPONDENT = ("correspondant", "correspondants")


def normalize_tag_name(value):
    text = str(value or "")
    if not text:
        return ""
    normalized = unicodedata.normalize("NFKD", text)
    normalized = "".join(
        char for char in normalized if not unicodedata.combining(char)
    )
    normalized = re.sub(r"\s+", " ", normalized).strip().lower()
    return normalized
