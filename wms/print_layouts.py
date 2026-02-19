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
            {"id": "meta2", "type": "text", "text": "Cartons: {{ carton_count }}"},
            {
                "id": "meta3",
                "type": "text",
                "text": (
                    "Poids total: {% if weight_total_kg %}{{ weight_total_kg|floatformat:2 }} kg{% else %}-{% endif %}"
                    " | Volume total: {% if volume_total_m3 %}{{ volume_total_m3|floatformat:2 }} m3{% else %}-{% endif %}"
                ),
            },
            {"id": "items", "type": "table_items", "mode": "carton"},
        ]
    },
    "packing_list_carton": {
        "blocks": [
            {"id": "heading", "type": "text", "tag": "h1", "text": "Liste de colisage - carton"},
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
    "product_label": {
        "blocks": [
            {
                "id": "product_label",
                "type": "product_label",
                "title_product": "PRODUIT",
                "title_brand": "MARQUE",
                "title_color": "COULEUR",
                "title_rack": "RACK",
                "title_aisle": "ETAGERE",
                "title_shelf": "BAC",
                "style": {
                    "label_width": "18.8cm",
                    "label_height": "6.9cm",
                    "label_padding": "3mm",
                    "label_gap": "2mm",
                    "grid_gap": "2mm",
                    "label_border_width": "2px",
                    "label_border_color": "#1C8BC0",
                    "title_bg_color": "#1C8BC0",
                    "title_text_color": "#ffffff",
                    "title_font_size": "14pt",
                    "title_font_weight": "700",
                    "title_text_transform": "uppercase",
                    "value_font_size": "14pt",
                    "value_font_weight": "700",
                    "value_text_color": "#000000",
                    "value_text_transform": "capitalize",
                    "grid_value_font_size": "12pt",
                    "grid_value_line_height": "1.15",
                    "code_text_transform": "uppercase",
                    "font_family": "Aptos, Arial, sans-serif",
                    "title_col_width": "24%",
                    "value_col_width": "46%",
                    "photo_col_width": "30%",
                    "photo_border": "1px solid #d0d0d0",
                    "photo_padding": "2mm",
                    "pill_radius": "12mm",
                    "pill_padding": "1mm 3mm",
                    "pill_gap": "1mm",
                    "footer_gap": "4mm",
                    "page_margin": "8mm",
                    "page_gap": "1.5mm",
                },
            }
        ]
    },
    "product_qr": {
        "blocks": [
            {
                "id": "product_qr_label",
                "type": "product_qr_label",
                "style": {
                    "label_padding": "2mm",
                    "label_border_width": "0",
                    "label_border_color": "#000000",
                    "qr_size": "38mm",
                    "text_gap": "2mm",
                    "text_font_size": "12pt",
                    "text_font_weight": "600",
                    "font_family": "Aptos, Arial, sans-serif",
                    "page_margin": "5mm",
                    "page_gap": "2mm",
                    "page_rows": 5,
                    "page_columns": 3,
                },
            }
        ]
    },
}

DOCUMENT_TEMPLATES = [
    ("shipment_note", "Bon d'expédition"),
    ("packing_list_shipment", "Liste colisage (lot)"),
    ("packing_list_carton", "Liste colisage (carton)"),
    ("donation_certificate", "Attestation donation"),
    ("humanitarian_certificate", "Attestation aide humanitaire"),
    ("customs", "Attestation douane"),
    ("shipment_label", "Étiquette expédition"),
    ("product_label", "Étiquettes produit"),
    ("product_qr", "QR produits"),
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
    "summary_triplet": {"label": "Résumé colis/poids/type", "fields": []},
    "contacts_row": {
        "label": "Contacts (expéditeur/destinataire/correspondant)",
        "fields": [
            {"name": "title_shipper", "label": "Titre expéditeur", "type": "text"},
            {"name": "title_recipient", "label": "Titre destinataire", "type": "text"},
            {"name": "title_correspondent", "label": "Titre correspondant", "type": "text"},
            {"name": "labels.company", "label": "Label société", "type": "text"},
            {"name": "labels.person", "label": "Label nom", "type": "text"},
            {"name": "labels.address", "label": "Label adresse", "type": "text"},
            {"name": "labels.phone", "label": "Label téléphone", "type": "text"},
            {"name": "labels.email", "label": "Label email", "type": "text"},
            {"name": "show_company", "label": "Afficher société", "type": "checkbox"},
            {"name": "show_person", "label": "Afficher nom", "type": "checkbox"},
            {"name": "show_address", "label": "Afficher adresse", "type": "checkbox"},
            {"name": "show_phone", "label": "Afficher téléphone", "type": "checkbox"},
            {"name": "show_email", "label": "Afficher email", "type": "checkbox"},
            {"name": "style.font_size", "label": "Taille texte", "type": "text"},
            {"name": "style.border_color", "label": "Couleur bordure", "type": "text"},
            {"name": "style.border_width", "label": "Épaisseur bordure", "type": "text"},
            {"name": "style.label_width", "label": "Largeur labels", "type": "text"},
            {"name": "style.column_gap", "label": "Écart colonnes", "type": "text"},
            {"name": "style.inner_gap_row", "label": "Écart lignes", "type": "text"},
            {"name": "style.inner_gap_col", "label": "Écart colonnes internes", "type": "text"},
            {"name": "style.title_weight", "label": "Graisse titres", "type": "text"},
            {"name": "style.label_weight", "label": "Graisse labels", "type": "text"},
        ],
        "defaults": {
            "title_shipper": "EXPÉDITEUR",
            "title_recipient": "DESTINATAIRE",
            "title_correspondent": "CORRESPONDANT",
            "show_company": True,
            "show_person": True,
            "show_address": True,
            "show_phone": True,
            "show_email": True,
            "labels": {
                "company": "Société",
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
            {"name": "style.border_width", "label": "Épaisseur bordure", "type": "text"},
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
            {"name": "style.border_width", "label": "Épaisseur bordure", "type": "text"},
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
            {"name": "style.border_width", "label": "Épaisseur bordure", "type": "text"},
            {"name": "style.padding", "label": "Padding", "type": "text"},
            {"name": "style.font_size", "label": "Taille texte", "type": "text"},
            {"name": "style.font_weight", "label": "Graisse texte", "type": "text"},
            {"name": "style.letter_spacing", "label": "Espacement lettres", "type": "text"},
            {"name": "style.gap", "label": "Écart blocs", "type": "text"},
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
    "product_label": {
        "label": "Étiquette produit",
        "fields": [
            {"name": "title_product", "label": "Titre produit", "type": "text"},
            {"name": "title_brand", "label": "Titre marque", "type": "text"},
            {"name": "title_color", "label": "Titre couleur", "type": "text"},
            {"name": "title_rack", "label": "Titre rack", "type": "text"},
            {"name": "title_aisle", "label": "Titre étagère", "type": "text"},
            {"name": "title_shelf", "label": "Titre bac", "type": "text"},
            {"name": "style.label_width", "label": "Largeur étiquette", "type": "text"},
            {"name": "style.label_height", "label": "Hauteur étiquette", "type": "text"},
            {"name": "style.label_padding", "label": "Padding étiquette", "type": "text"},
            {"name": "style.label_gap", "label": "Écart interne", "type": "text"},
            {"name": "style.grid_gap", "label": "Écart grille", "type": "text"},
            {"name": "style.label_border_width", "label": "Bordure largeur", "type": "text"},
            {"name": "style.label_border_color", "label": "Bordure couleur", "type": "text"},
            {"name": "style.title_bg_color", "label": "Titre fond", "type": "text"},
            {"name": "style.title_text_color", "label": "Titre texte", "type": "text"},
            {"name": "style.title_font_size", "label": "Titre taille", "type": "text"},
            {"name": "style.title_font_weight", "label": "Titre graisse", "type": "text"},
            {"name": "style.title_text_transform", "label": "Titre casse", "type": "text"},
            {"name": "style.value_font_size", "label": "Valeur taille", "type": "text"},
            {"name": "style.value_font_weight", "label": "Valeur graisse", "type": "text"},
            {"name": "style.value_text_color", "label": "Valeur couleur", "type": "text"},
            {"name": "style.value_text_transform", "label": "Valeur casse", "type": "text"},
            {"name": "style.grid_value_font_size", "label": "Valeur grille taille", "type": "text"},
            {"name": "style.grid_value_line_height", "label": "Valeur grille interligne", "type": "text"},
            {"name": "style.code_text_transform", "label": "Code casse", "type": "text"},
            {"name": "style.font_family", "label": "Police", "type": "text"},
            {"name": "style.title_col_width", "label": "Colonne titre", "type": "text"},
            {"name": "style.value_col_width", "label": "Colonne valeur", "type": "text"},
            {"name": "style.photo_col_width", "label": "Colonne photo", "type": "text"},
            {"name": "style.photo_border", "label": "Photo bordure", "type": "text"},
            {"name": "style.photo_padding", "label": "Photo padding", "type": "text"},
            {"name": "style.pill_radius", "label": "Pill radius", "type": "text"},
            {"name": "style.pill_padding", "label": "Pill padding", "type": "text"},
            {"name": "style.pill_gap", "label": "Pill ecart", "type": "text"},
            {"name": "style.footer_gap", "label": "Écart bas", "type": "text"},
            {"name": "style.page_margin", "label": "Marge page", "type": "text"},
            {"name": "style.page_gap", "label": "Écart page", "type": "text"},
        ],
        "defaults": {
            "title_product": "PRODUIT",
            "title_brand": "MARQUE",
            "title_color": "COULEUR",
            "title_rack": "RACK",
            "title_aisle": "ETAGERE",
            "title_shelf": "BAC",
            "style": {
                "label_width": "18.8cm",
                "label_height": "6.9cm",
                "label_padding": "3mm",
                "label_gap": "2mm",
                "grid_gap": "2mm",
                "label_border_width": "2px",
                "label_border_color": "#1C8BC0",
                "title_bg_color": "#1C8BC0",
                "title_text_color": "#ffffff",
                "title_font_size": "14pt",
                "title_font_weight": "700",
                "title_text_transform": "uppercase",
                "value_font_size": "14pt",
                "value_font_weight": "700",
                "value_text_color": "#000000",
                "value_text_transform": "capitalize",
                "grid_value_font_size": "12pt",
                "grid_value_line_height": "1.15",
                "code_text_transform": "uppercase",
                "font_family": "Aptos, Arial, sans-serif",
                "title_col_width": "24%",
                "value_col_width": "46%",
                "photo_col_width": "30%",
                "photo_border": "1px solid #d0d0d0",
                "photo_padding": "2mm",
                "pill_radius": "12mm",
                "pill_padding": "1mm 3mm",
                "pill_gap": "1mm",
                "footer_gap": "4mm",
                "page_margin": "8mm",
                "page_gap": "1.5mm",
            },
        },
    },
    "product_qr_label": {
        "label": "QR produit",
        "fields": [
            {"name": "style.label_padding", "label": "Padding étiquette", "type": "text"},
            {"name": "style.label_border_width", "label": "Bordure largeur", "type": "text"},
            {"name": "style.label_border_color", "label": "Bordure couleur", "type": "text"},
            {"name": "style.qr_size", "label": "Taille QR", "type": "text"},
            {"name": "style.text_gap", "label": "Écart texte", "type": "text"},
            {"name": "style.text_font_size", "label": "Taille texte", "type": "text"},
            {"name": "style.text_font_weight", "label": "Graisse texte", "type": "text"},
            {"name": "style.font_family", "label": "Police", "type": "text"},
            {"name": "style.page_margin", "label": "Marge page", "type": "text"},
            {"name": "style.page_gap", "label": "Écart page", "type": "text"},
            {"name": "style.page_rows", "label": "Lignes/page", "type": "text"},
            {"name": "style.page_columns", "label": "Colonnes/page", "type": "text"},
        ],
        "defaults": {
            "style": {
                "label_padding": "2mm",
                "label_border_width": "0",
                "label_border_color": "#000000",
                "qr_size": "38mm",
                "text_gap": "2mm",
                "text_font_size": "12pt",
                "text_font_weight": "600",
                "font_family": "Aptos, Arial, sans-serif",
                "page_margin": "5mm",
                "page_gap": "2mm",
                "page_rows": 5,
                "page_columns": 3,
            },
        },
    },
}
