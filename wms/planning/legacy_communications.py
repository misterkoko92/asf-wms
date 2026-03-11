from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from html import escape

from wms.models import CommunicationChannel


class CommunicationFamily:
    WHATSAPP_BENEVOLE = "whatsapp_benevole"
    EMAIL_ASF = "email_asf"
    EMAIL_AIRFRANCE = "email_airfrance"
    EMAIL_CORRESPONDANT = "email_correspondant"
    EMAIL_EXPEDITEUR = "email_expediteur"
    EMAIL_DESTINATAIRE = "email_destinataire"


COMMUNICATION_FAMILY_ORDER = (
    CommunicationFamily.WHATSAPP_BENEVOLE,
    CommunicationFamily.EMAIL_ASF,
    CommunicationFamily.EMAIL_AIRFRANCE,
    CommunicationFamily.EMAIL_CORRESPONDANT,
    CommunicationFamily.EMAIL_EXPEDITEUR,
    CommunicationFamily.EMAIL_DESTINATAIRE,
)

COMMUNICATION_FAMILY_LABELS = {
    CommunicationFamily.WHATSAPP_BENEVOLE: "WhatsApp bénévoles",
    CommunicationFamily.EMAIL_ASF: "Mail ASF interne",
    CommunicationFamily.EMAIL_AIRFRANCE: "Mail Air France",
    CommunicationFamily.EMAIL_CORRESPONDANT: "Mail Correspondants",
    CommunicationFamily.EMAIL_EXPEDITEUR: "Mail Expéditeurs",
    CommunicationFamily.EMAIL_DESTINATAIRE: "Mail Destinataires",
}

COMMUNICATION_FAMILY_CHANNELS = {
    CommunicationFamily.WHATSAPP_BENEVOLE: CommunicationChannel.WHATSAPP,
    CommunicationFamily.EMAIL_ASF: CommunicationChannel.EMAIL,
    CommunicationFamily.EMAIL_AIRFRANCE: CommunicationChannel.EMAIL,
    CommunicationFamily.EMAIL_CORRESPONDANT: CommunicationChannel.EMAIL,
    CommunicationFamily.EMAIL_EXPEDITEUR: CommunicationChannel.EMAIL,
    CommunicationFamily.EMAIL_DESTINATAIRE: CommunicationChannel.EMAIL,
}

COMMUNICATION_FAMILY_RECIPIENTS = {
    CommunicationFamily.EMAIL_ASF: "ASF interne",
    CommunicationFamily.EMAIL_AIRFRANCE: "Air France",
}

DEFAULT_BODY_ASF = (
    "Bonjour à tous,<br><br>"
    "J'espère que vous allez bien !<br><br>"
    "Voici en pièce jointe le planning de la semaine {week}.<br><br>"
    "Bonne journée à tous,<br>"
    "Edouard<br>"
)

DEFAULT_BODY_AIRFRANCE = (
    "Bonjour,<br><br>"
    "Comme convenu, veuillez trouver ci-joint notre planning des expéditions prévues pour la semaine {week}.<br>"
    "Nous vous tiendrons informés en cas de mise à jour le cas échéant.<br><br>"
    "Encore merci à tous pour votre aide,<br><br>"
    "Cordialement,<br>"
    "Edouard<br>"
)

DEFAULT_BODY_DEST = (
    "Bonjour,<br><br>"
    "J'espère que vous allez bien.<br><br>"
    "Voici les informations d'expédition pour la destination : {destination}.<br><br>"
    "{table_html}<br><br>"
    "Cordialement,<br><br>"
    "Edouard<br>"
)

DEFAULT_BODY_EXPEDITEUR = (
    "Bonjour,<br><br>"
    "Nous tenons à vous informer des livraisons prévues la semaine prochaine pour vos colis :<br><br>"
    "{table_html}<br><br>"
    "Pouvez-vous demander à votre structure sur place de prendre contact avec notre correspondant "
    "afin d'organiser le transfert des colis ?<br><br>"
    "Coordonnées de notre correspondant :<br>{coord_correspondant}<br><br>"
    "Merci pour votre confiance.<br><br>"
    "Cordialement,<br><br>"
    "Edouard<br>"
)

DAY_NAMES = (
    "Lundi",
    "Mardi",
    "Mercredi",
    "Jeudi",
    "Vendredi",
    "Samedi",
    "Dimanche",
)

MONTH_NAMES = (
    "janvier",
    "février",
    "mars",
    "avril",
    "mai",
    "juin",
    "juillet",
    "août",
    "septembre",
    "octobre",
    "novembre",
    "décembre",
)

_NON_DIGIT_RE = re.compile(r"\D+")


@dataclass(frozen=True)
class LegacyCommRow:
    flight_date: date | None
    destination_city: str
    destination_iata: str
    flight_number: str
    departure_time: str
    shipment_reference: str
    cartons: int
    shipment_type: str
    shipper_name: str
    recipient_name: str
    volunteer_label: str
    volunteer_first_name: str
    volunteer_phone: str
    correspondent_label: str
    correspondent_contact: str
    shipper_contact: str
    recipient_contact: str


def family_label(family: str) -> str:
    return COMMUNICATION_FAMILY_LABELS.get(family, family)


def family_channel(family: str) -> str:
    return COMMUNICATION_FAMILY_CHANNELS[family]


def family_order_key(family: str) -> int:
    try:
        return COMMUNICATION_FAMILY_ORDER.index(family)
    except ValueError:
        return len(COMMUNICATION_FAMILY_ORDER)


def static_family_recipient_label(family: str) -> str:
    return COMMUNICATION_FAMILY_RECIPIENTS.get(family, "")


def format_be_number(value) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.endswith(".0"):
        text = text[:-2]
    digits = _NON_DIGIT_RE.sub("", text)
    if not digits:
        return ""
    if len(digits) >= 6:
        return digits[-6:]
    return digits.zfill(6)


def format_vol_display(value) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.upper().startswith("AF"):
        text = text[2:].strip()
    digits = _NON_DIGIT_RE.sub("", text)
    digits = digits.lstrip("0")
    if not digits:
        return ""
    return f"AF {digits}"


def format_date_fr_long_slash(value: date | None) -> str:
    if value is None:
        return ""
    return f"{DAY_NAMES[value.weekday()]} {value.strftime('%d/%m/%Y')}"


def format_date_fr_words(value: date | None) -> str:
    if value is None:
        return ""
    return f"{DAY_NAMES[value.weekday()]} {value.day} {MONTH_NAMES[value.month - 1]}"


def format_heure_hh_mm(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if "h" in text:
        return text
    if ":" not in text:
        return text
    hour, minute = (text.split(":", 1) + [""])[:2]
    return f"{int(hour)}h{minute[:2].zfill(2)}"


def format_correspondent_contact(reference: dict[str, object]) -> str:
    parts = []
    title = str(reference.get("contact_title") or "").strip()
    first_name = str(reference.get("contact_first_name") or "").strip()
    last_name = str(reference.get("contact_last_name") or "").strip().upper()
    identity = " ".join(part for part in (title, first_name, last_name) if part)
    if identity:
        parts.append(identity)
    emails = reference.get("notification_emails") or [""]
    email = str(emails[0] or "").strip() if emails else ""
    if email:
        parts.append(email)
    for key in ("phone", "phone2", "phone3"):
        value = str(reference.get(key) or "").strip()
        if value:
            parts.append(value)
    return " / ".join(parts)


def build_comm_table_html(rows: list[LegacyCommRow]) -> str:
    if not rows:
        return "<p><i>Aucun colis cette semaine.</i></p>"

    border_style = "border:1px solid #999;"
    headers = (
        "Date",
        "Destination",
        "N° Vol",
        "N° BE",
        "Colis",
        "Type",
        "Expéditeur",
        "Destinataire",
    )
    html = [
        f'<table cellpadding="6" cellspacing="0" style="border-collapse:collapse; table-layout:auto; {border_style}">'
    ]
    html.append("<tr>")
    for header in headers:
        html.append(
            f"<th style='background:#e6e6e6; white-space:nowrap; {border_style}'>{header}</th>"
        )
    html.append("</tr>")

    for row in rows:
        html.append("<tr>")
        for value in (
            format_date_fr_long_slash(row.flight_date),
            row.destination_city,
            format_vol_display(row.flight_number),
            format_be_number(row.shipment_reference),
            str(row.cartons),
            row.shipment_type,
            row.shipper_name,
            row.recipient_name,
        ):
            html.append(
                f"<td style='white-space:nowrap; {border_style}'>{escape(str(value), quote=True)}</td>"
            )
        html.append("</tr>")
    html.append("</table>")
    return "\n".join(html)


def build_subject_asf(*, week: int, year: int) -> str:
    return f"Planning SEMAINE {week} - {year}"


def build_subject_airfrance(*, week: int) -> str:
    return f"Aviation Sans Frontires / Planning S{week}"


def build_subject_destination(*, destination_city: str, week: int) -> str:
    return f"ASF / Expédition {destination_city} / Semaine {week}"


def build_subject_expediteur(*, party_name: str, destination_city: str, week: int) -> str:
    return f"{party_name} / Expédition {destination_city} / Semaine {week}"


def build_whatsapp_message(*, rows: list[LegacyCommRow]) -> str:
    primary = rows[0]
    first_name = (
        str(primary.volunteer_first_name or "").strip()
        or str(primary.volunteer_label or "").strip()
    )
    if first_name:
        first_name = first_name.split()[0]
    lines = [f"Bonjour {first_name or ' '}, voici tes mises à bord pour la semaine prochaine :"]
    for row in rows:
        lines.append(
            "• "
            f"{format_date_fr_words(row.flight_date)} : "
            f"{row.destination_city} // "
            f"{format_vol_display(row.flight_number)} // "
            f"{format_heure_hh_mm(row.departure_time)} // "
            f"BE {format_be_number(row.shipment_reference)} // "
            f"{row.cartons} colis {row.shipment_type}".rstrip()
        )
    total_cartons = sum(row.cartons for row in rows)
    lines.append(f"Total {primary.destination_iata} : {total_cartons} colis en simple")
    lines.append("")
    lines.append(
        "Merci de me confirmer si tu es OK. N'hésite pas à m'appeler si besoin pour ajuster."
    )
    lines.append("Merci beaucoup !")
    return "\n".join(lines)
