DEFAULT_LAYOUTS = {
    "shipment_note": {
        "blocks": [
            {
                "id": "line1",
                "type": "text",
                "text": "<strong>BON D'EXPEDITION</strong> / <strong>N&#176; <span style=\"color:#d11; font-weight:800;\">{{ shipment_ref }}</span></strong> / <strong>N&#176; DECLARATION DOUANE</strong> <span style=\"display:inline-block; min-width:28mm; border-bottom:1px solid #000; height:4mm;\"></span>",
            },
            {
                "id": "line2",
                "type": "text",
                "text": "<strong>DESTINATION :</strong> {{ destination_city|default:destination_address }} / <span style=\"color:#d11; font-weight:800;\">{{ destination_iata|default:\"-\" }}</span> / Date de vol <span style=\"display:inline-block; min-width:28mm; border-bottom:1px solid #000; height:4mm;\"></span> / N&#176; Vol <span style=\"display:inline-block; min-width:28mm; border-bottom:1px solid #000; height:4mm;\"></span>",
            },
            {"id": "summary", "type": "summary_triplet"},
            {
                "id": "contacts",
                "type": "contacts_row",
                "title_shipper": "EXPEDITEUR",
                "title_recipient": "DESTINATAIRE",
                "title_correspondent": "CORRESPONDANT",
                "show_company": True,
                "show_person": True,
                "show_address": True,
                "show_phone": True,
                "show_email": True,
                "labels": {
                    "company": "Societe",
                    "person": "Nom",
                    "address": "Adresse",
                    "phone": "Tel",
                    "email": "Mail",
                },
                "style": {
                    "border_color": "#000",
                    "border_width": "1px",
                    "font_size": "9pt",
                    "label_width": "20mm",
                    "column_gap": "4mm",
                    "inner_gap_row": "1mm",
                    "inner_gap_col": "2mm",
                    "title_weight": "800",
                    "label_weight": "700",
                },
            },
            {"id": "signatures", "type": "signatures"},
            {
                "id": "attestation",
                "type": "text",
                "text": (
                    "<div style=\"display:grid; gap:2mm; font-size:9pt; line-height:1.3;\">"
                    "<div>&nbsp;</div>"
                    "<div><strong>ATTESTATION DE DONATION</strong></div>"
                    "<div>Je soussign&eacute;, M. Edouard Gonnu, Responsable de la Messagerie M&eacute;dicale, de l'association Aviation Sans Fronti&egrave;res Atteste que le(s) colis faisant l'objet de la pr&eacute;sente exp&eacute;dition par l'interm&eacute;diaire d'Aviation Sans Fronti&egrave;res est (sont) un (des) don(s) de l'Exp&eacute;diteur au Destinataire mentionn&eacute;s ci-dessous. Le correspondant est le seul autoris&eacute; &agrave; r&eacute;cup&eacute;rer ces colis pour le compte du Destinataire.</div>"
                    "<div>Ces colis ne contiennent que du mat&eacute;riel m&eacute;dical et chirurgical envoy&eacute;s &agrave; titre humanitaire. Ces articles m&eacute;dicaux sont pour la sant&eacute; humaine et ne sont pas destin&eacute;s &agrave; &ecirc;tre revendus.</div>"
                    "<div><strong>Ils ne sont pas soumis aux biens &agrave; double usage - sans valeur commerciale. Valeur uniquement pour la douane : 1.00 &euro; -</strong></div>"
                    "<div>Fait &agrave; Roissy, France, le {{ document_date|date:\"d/m/y\" }} <img src=\"/static/scan/cachet.png\" style=\"height:18mm; vertical-align:middle;\" alt=\"Cachet\"></div>"
                    "</div>"
                ),
            },
        ]
    },
    "packing_list_shipment": {
        "blocks": [
            {
                "id": "heading",
                "type": "text",
                "tag": "h1",
                "text": (
                    "LISTE DE COLISAGE - EXPEDITION N&deg; {{ shipment_ref }} - DESTINATION "
                    "{% if destination_city %}{{ destination_city|upper }}{% if destination_iata %} / "
                    "{{ destination_iata|upper }}{% endif %}{% else %}{{ destination_label|upper }}{% endif %}"
                ),
            },
            {"id": "meta1", "type": "text", "text": "Shipment ref: {{ shipment_ref }}"},
            {"id": "meta2", "type": "text", "text": "Cartons: {{ carton_count }}"},
            {
                "id": "meta3",
                "type": "text",
                "text": "Poids total: {% if weight_total_kg %}{{ weight_total_kg|floatformat:2 }} kg{% else %}-{% endif %}",
            },
            {"id": "items", "type": "table_items", "mode": "carton"},
            {"id": "carton_title", "type": "text", "tag": "h2", "text": "Resume colis"},
            {"id": "cartons", "type": "table_cartons"},
        ]
    },
    "packing_list_carton": {
        "blocks": [
            {"id": "heading", "type": "text", "tag": "h1", "text": "Liste de colisage - carton"},
            {"id": "meta1", "type": "text", "text": "Shipment ref: {{ shipment_ref }}"},
            {
                "id": "meta2",
                "type": "text",
                "text": (
                    "Carton code: {{ carton_code }}<br>"
                    "Poids: {% if carton_weight_kg %}{{ carton_weight_kg|floatformat:2 }} kg{% else %}-{% endif %}"
                ),
            },
            {"id": "items", "type": "table_items", "mode": "carton"},
        ]
    },
    "donation_certificate": {
        "blocks": [
            {"id": "heading", "type": "text", "tag": "h1", "text": "Attestation de donation"},
            {"id": "meta1", "type": "text", "text": "Document ref: {{ document_ref }}"},
            {"id": "meta2", "type": "text", "text": "Date: {{ document_date|date:\"d/m/Y\" }}"},
            {"id": "org", "type": "text", "text": "Organisation: {{ org_name }}"},
            {"id": "org2", "type": "text", "text": "Adresse: {{ org_address }}"},
            {"id": "org3", "type": "text", "text": "Contact: {{ org_contact }}"},
            {"id": "donor", "type": "text", "text": "Donateur: {{ donor_name }}"},
            {"id": "recipient", "type": "text", "text": "Destinataire: {{ recipient_name }}"},
            {"id": "destination", "type": "text", "text": "Destination: {{ destination_address }}"},
            {"id": "desc", "type": "text", "text": "Description du don: {{ donation_description }}"},
            {"id": "sign", "type": "signatures", "labels": ["Signataire", "Signature"]},
        ]
    },
    "humanitarian_certificate": {
        "blocks": [
            {"id": "heading", "type": "text", "tag": "h1", "text": "Attestation d'aide humanitaire"},
            {"id": "meta1", "type": "text", "text": "Document ref: {{ document_ref }}"},
            {"id": "meta2", "type": "text", "text": "Date: {{ document_date|date:\"d/m/Y\" }}"},
            {"id": "org", "type": "text", "text": "Organisation: {{ org_name }}"},
            {"id": "purpose", "type": "text", "text": "Objet: {{ humanitarian_purpose }}"},
        ]
    },
    "customs": {
        "blocks": [
            {"id": "heading", "type": "text", "tag": "h1", "text": "Attestation de douane"},
            {"id": "meta1", "type": "text", "text": "Document ref: {{ document_ref }}"},
            {"id": "meta2", "type": "text", "text": "Date: {{ document_date|date:\"d/m/Y\" }}"},
            {"id": "org", "type": "text", "text": "Organisation: {{ org_name }}"},
            {"id": "desc", "type": "text", "text": "{{ shipment_description }}"},
        ]
    },
    "shipment_label": {
        "blocks": [
            {
                "id": "label_city",
                "type": "label_city",
                "style": {
                    "border_color": "#333",
                    "border_width": "5px",
                    "padding": "10mm 6mm",
                    "font_size": "36pt",
                    "font_weight": "800",
                    "letter_spacing": "2px",
                    "align": "center",
                    "text_transform": "uppercase",
                },
            },
            {
                "id": "label_iata",
                "type": "label_iata",
                "style": {
                    "border_color": "#d11",
                    "border_width": "8px",
                    "padding": "6mm 10mm",
                    "font_size": "54pt",
                    "font_weight": "900",
                    "letter_spacing": "4px",
                    "align": "center",
                    "text_transform": "uppercase",
                    "color": "#d11",
                },
            },
            {
                "id": "label_footer",
                "type": "label_footer",
                "style": {
                    "border_color": "#333",
                    "border_width": "5px",
                    "padding": "6mm 8mm",
                    "font_size": "26pt",
                    "font_weight": "800",
                    "letter_spacing": "2px",
                    "gap": "8mm",
                    "right_max_width": "45%",
                    "align": "center",
                    "text_transform": "uppercase",
                },
            },
        ]
    },
}

DOCUMENT_TEMPLATES = [
    ("shipment_note", "Bon d'expedition"),
    ("packing_list_shipment", "Liste colisage (lot)"),
    ("packing_list_carton", "Liste colisage (carton)"),
    ("donation_certificate", "Attestation donation"),
    ("humanitarian_certificate", "Attestation aide humanitaire"),
    ("customs", "Attestation douane"),
    ("shipment_label", "Etiquette expedition"),
]

BLOCK_LIBRARY = {
    "text": {
        "label": "Texte libre",
        "fields": [
            {"name": "text", "label": "Texte", "type": "textarea"},
            {"name": "tag", "label": "Tag", "type": "select", "options": ["div", "h1", "h2"]},
            {"name": "style.font_size", "label": "Taille", "type": "text"},
            {"name": "style.line_height", "label": "Interligne", "type": "text"},
            {"name": "style.align", "label": "Alignement", "type": "select", "options": ["left", "center", "right"]},
            {"name": "style.border", "label": "Bordure", "type": "checkbox"},
            {"name": "style.color", "label": "Couleur", "type": "text"},
            {"name": "style.padding", "label": "Padding", "type": "text"},
            {"name": "style.font_weight", "label": "Graisse", "type": "text"},
            {"name": "style.background", "label": "Fond", "type": "text"},
        ],
    },
    "summary_triplet": {"label": "Resume colis/poids/type", "fields": []},
    "contacts_row": {
        "label": "Contacts (expediteur/destinataire/correspondant)",
        "fields": [
            {"name": "title_shipper", "label": "Titre expediteur", "type": "text"},
            {"name": "title_recipient", "label": "Titre destinataire", "type": "text"},
            {"name": "title_correspondent", "label": "Titre correspondant", "type": "text"},
            {"name": "labels.company", "label": "Label societe", "type": "text"},
            {"name": "labels.person", "label": "Label nom", "type": "text"},
            {"name": "labels.address", "label": "Label adresse", "type": "text"},
            {"name": "labels.phone", "label": "Label telephone", "type": "text"},
            {"name": "labels.email", "label": "Label email", "type": "text"},
            {"name": "show_company", "label": "Afficher societe", "type": "checkbox"},
            {"name": "show_person", "label": "Afficher nom", "type": "checkbox"},
            {"name": "show_address", "label": "Afficher adresse", "type": "checkbox"},
            {"name": "show_phone", "label": "Afficher telephone", "type": "checkbox"},
            {"name": "show_email", "label": "Afficher email", "type": "checkbox"},
            {"name": "style.font_size", "label": "Taille texte", "type": "text"},
            {"name": "style.border_color", "label": "Couleur bordure", "type": "text"},
            {"name": "style.border_width", "label": "Epaisseur bordure", "type": "text"},
            {"name": "style.label_width", "label": "Largeur labels", "type": "text"},
            {"name": "style.column_gap", "label": "Ecart colonnes", "type": "text"},
            {"name": "style.inner_gap_row", "label": "Ecart lignes", "type": "text"},
            {"name": "style.inner_gap_col", "label": "Ecart colonnes internes", "type": "text"},
            {"name": "style.title_weight", "label": "Graisse titres", "type": "text"},
            {"name": "style.label_weight", "label": "Graisse labels", "type": "text"},
        ],
        "defaults": {
            "title_shipper": "EXPEDITEUR",
            "title_recipient": "DESTINATAIRE",
            "title_correspondent": "CORRESPONDANT",
            "show_company": True,
            "show_person": True,
            "show_address": True,
            "show_phone": True,
            "show_email": True,
            "labels": {
                "company": "Societe",
                "person": "Nom",
                "address": "Adresse",
                "phone": "Tel",
                "email": "Mail",
            },
            "style": {
                "border_color": "#000",
                "border_width": "1px",
                "font_size": "9pt",
                "label_width": "20mm",
                "column_gap": "4mm",
                "inner_gap_row": "1mm",
                "inner_gap_col": "2mm",
                "title_weight": "800",
                "label_weight": "700",
            },
        },
    },
    "signatures": {"label": "Signatures", "fields": []},
    "table_items": {
        "label": "Table produits",
        "fields": [
            {"name": "mode", "label": "Mode", "type": "select", "options": ["aggregate", "carton"]}
        ],
    },
    "table_cartons": {"label": "Table cartons", "fields": []},
    "label_city": {
        "label": "Etiquette: Ville",
        "fields": [
            {"name": "style.border_color", "label": "Couleur bordure", "type": "text"},
            {"name": "style.border_width", "label": "Epaisseur bordure", "type": "text"},
            {"name": "style.padding", "label": "Padding", "type": "text"},
            {"name": "style.font_size", "label": "Taille texte", "type": "text"},
            {"name": "style.font_weight", "label": "Graisse texte", "type": "text"},
            {"name": "style.letter_spacing", "label": "Espacement lettres", "type": "text"},
            {"name": "style.align", "label": "Alignement", "type": "select", "options": ["left", "center", "right"]},
            {"name": "style.text_transform", "label": "Casse", "type": "select", "options": ["uppercase", "none"]},
        ],
        "defaults": {
            "style": {
                "border_color": "#333",
                "border_width": "5px",
                "padding": "10mm 6mm",
                "font_size": "36pt",
                "font_weight": "800",
                "letter_spacing": "2px",
                "align": "center",
                "text_transform": "uppercase",
            }
        },
    },
    "label_iata": {
        "label": "Etiquette: IATA",
        "fields": [
            {"name": "style.color", "label": "Couleur texte", "type": "text"},
            {"name": "style.border_color", "label": "Couleur bordure", "type": "text"},
            {"name": "style.border_width", "label": "Epaisseur bordure", "type": "text"},
            {"name": "style.padding", "label": "Padding", "type": "text"},
            {"name": "style.font_size", "label": "Taille texte", "type": "text"},
            {"name": "style.font_weight", "label": "Graisse texte", "type": "text"},
            {"name": "style.letter_spacing", "label": "Espacement lettres", "type": "text"},
            {"name": "style.align", "label": "Alignement", "type": "select", "options": ["left", "center", "right"]},
            {"name": "style.text_transform", "label": "Casse", "type": "select", "options": ["uppercase", "none"]},
        ],
        "defaults": {
            "style": {
                "color": "#d11",
                "border_color": "#d11",
                "border_width": "8px",
                "padding": "6mm 10mm",
                "font_size": "54pt",
                "font_weight": "900",
                "letter_spacing": "4px",
                "align": "center",
                "text_transform": "uppercase",
            }
        },
    },
    "label_footer": {
        "label": "Etiquette: Footer",
        "fields": [
            {"name": "style.border_color", "label": "Couleur bordure", "type": "text"},
            {"name": "style.border_width", "label": "Epaisseur bordure", "type": "text"},
            {"name": "style.padding", "label": "Padding", "type": "text"},
            {"name": "style.font_size", "label": "Taille texte", "type": "text"},
            {"name": "style.font_weight", "label": "Graisse texte", "type": "text"},
            {"name": "style.letter_spacing", "label": "Espacement lettres", "type": "text"},
            {"name": "style.gap", "label": "Ecart blocs", "type": "text"},
            {"name": "style.right_max_width", "label": "Largeur bloc droit", "type": "text"},
            {"name": "style.align", "label": "Alignement", "type": "select", "options": ["flex-start", "center", "flex-end"]},
            {"name": "style.text_transform", "label": "Casse", "type": "select", "options": ["uppercase", "none"]},
        ],
        "defaults": {
            "style": {
                "border_color": "#333",
                "border_width": "5px",
                "padding": "6mm 8mm",
                "font_size": "26pt",
                "font_weight": "800",
                "letter_spacing": "2px",
                "gap": "8mm",
                "right_max_width": "45%",
                "align": "center",
                "text_transform": "uppercase",
            }
        },
    },
}
