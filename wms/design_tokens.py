import re

HEX_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")

DENSITY_MODE_CHOICES = (
    ("dense", "Dense"),
    ("standard", "Standard"),
    ("airy", "Aere"),
)

BTN_STYLE_MODE_CHOICES = (
    ("flat", "Flat"),
    ("soft", "Soft"),
    ("elevated", "Elevated"),
    ("outlined", "Outlined"),
)

TEXT_TRANSFORM_CHOICES = (
    ("none", "Normal"),
    ("uppercase", "MAJUSCULE"),
)

FONT_WEIGHT_CHOICES = (
    ("400", "400"),
    ("500", "500"),
    ("600", "600"),
    ("700", "700"),
    ("800", "800"),
)

LINE_HEIGHT_HEADING_CHOICES = (
    ("1.1", "Compacte (1.1)"),
    ("1.2", "Standard (1.2)"),
    ("1.3", "Confort (1.3)"),
    ("1.4", "Aeree (1.4)"),
)

LINE_HEIGHT_BODY_CHOICES = (
    ("1.35", "Compacte (1.35)"),
    ("1.5", "Standard (1.5)"),
    ("1.6", "Confort (1.6)"),
    ("1.75", "Aeree (1.75)"),
)

LETTER_SPACING_HEADING_CHOICES = (
    ("0em", "0em"),
    ("0.01em", "0.01em"),
    ("0.02em", "0.02em"),
    ("0.04em", "0.04em"),
)

LETTER_SPACING_BODY_CHOICES = (
    ("0em", "0em"),
    ("0.005em", "0.005em"),
    ("0.01em", "0.01em"),
    ("0.02em", "0.02em"),
)

NAV_FONT_SIZE_CHOICES = (
    ("13px", "13 px"),
    ("14px", "14 px"),
    ("15px", "15 px"),
    ("16px", "16 px"),
)

NAV_LINE_HEIGHT_CHOICES = (
    ("1.1", "Compacte (1.1)"),
    ("1.2", "Standard (1.2)"),
    ("1.3", "Confort (1.3)"),
    ("1.4", "Aeree (1.4)"),
)

TABLE_HEADER_FONT_SIZE_CHOICES = (
    ("11px", "11 px"),
    ("12px", "12 px"),
    ("13px", "13 px"),
    ("14px", "14 px"),
)

TABLE_HEADER_LETTER_SPACING_CHOICES = (
    ("0.02em", "0.02em"),
    ("0.04em", "0.04em"),
    ("0.05em", "0.05em"),
    ("0.06em", "0.06em"),
)


DESIGN_TOKEN_FAMILY_DEFINITIONS = (
    ("foundations", "Fondations", "Densite, espacements et largeur de page.", True),
    ("typography", "Typographie", "Tailles, interlignes et poids des textes.", False),
    ("global_colors", "Couleurs globales", "Couleurs de base, liens, focus et etats desactives.", True),
    ("buttons", "Boutons", "Style, dimensions et couleurs des actions.", True),
    ("inputs", "Champs", "Apparence des champs de saisie.", False),
    ("cards", "Cards / Panneaux", "Contours, ombres et en-tetes des modules.", False),
    ("navigation", "Navigation", "Navbar, liens actifs et dropdown.", False),
    ("tables", "Tableaux", "En-tete, lignes, hover et bordures.", False),
    ("business_states", "Etats metier", "Pills, badges et codes couleur des etats.", False),
)


def _choice_spec(default, choices, family, label, help_text, preview_var=None):
    return {
        "kind": "choice",
        "default": str(default),
        "choices": tuple((str(value), text) for value, text in choices),
        "family": family,
        "label": label,
        "help_text": help_text,
        "preview_var": preview_var,
    }


def _int_spec(default, minimum, maximum, family, label, help_text, preview_var=None, preview_unit="px"):
    return {
        "kind": "int",
        "default": int(default),
        "min": int(minimum),
        "max": int(maximum),
        "family": family,
        "label": label,
        "help_text": help_text,
        "preview_var": preview_var,
        "preview_unit": preview_unit,
    }


def _color_spec(default, family, label, help_text, preview_var=None):
    return {
        "kind": "color",
        "default": str(default).lower(),
        "family": family,
        "label": label,
        "help_text": help_text,
        "preview_var": preview_var,
    }


def _text_spec(default, family, label, help_text, max_length=120, preview_var=None):
    return {
        "kind": "text",
        "default": str(default),
        "family": family,
        "label": label,
        "help_text": help_text,
        "max_length": int(max_length),
        "preview_var": preview_var,
    }


DESIGN_TOKEN_SPECS = {
    "density_mode": _choice_spec(
        "standard",
        DENSITY_MODE_CHOICES,
        "foundations",
        "Densite",
        "Rythme general: dense (compact), standard ou aere.",
        preview_var="--preview-density-mode",
    ),
    "space_unit": _int_spec(
        8,
        4,
        16,
        "foundations",
        "Unite d'espacement (px)",
        "Base des marges/paddings. 6 = compact, 8 = standard, 10 = aere.",
    ),
    "section_gap": _int_spec(
        16,
        8,
        64,
        "foundations",
        "Espace entre sections (px)",
        "Distance entre les blocs principaux.",
    ),
    "field_gap": _int_spec(
        12,
        4,
        40,
        "foundations",
        "Espace entre champs (px)",
        "Distance verticale entre les champs d'un formulaire.",
    ),
    "container_max_width": _int_spec(
        1520,
        960,
        2200,
        "foundations",
        "Largeur max conteneur (px)",
        "Largeur maximale de la zone principale.",
    ),
    "content_max_width": _int_spec(
        1200,
        720,
        1800,
        "foundations",
        "Largeur max contenu (px)",
        "Largeur des contenus textuels/denses.",
    ),
    "kpi_card_min_width": _int_spec(
        220,
        140,
        420,
        "foundations",
        "Largeur min carte KPI (px)",
        "Taille minimale des cartes indicateurs.",
    ),
    "table_min_width": _int_spec(
        720,
        480,
        2200,
        "foundations",
        "Largeur min tableau (px)",
        "Limite a partir de laquelle le tableau peut scroller horizontalement.",
    ),
    "font_size_h1": _int_spec(
        34,
        20,
        96,
        "typography",
        "Taille H1 (px)",
        "Taille des grands titres.",
        preview_var="--preview-font-size-h1",
    ),
    "font_size_h2": _int_spec(
        28,
        18,
        72,
        "typography",
        "Taille H2 (px)",
        "Taille des titres de section.",
        preview_var="--preview-font-size-h2",
    ),
    "font_size_h3": _int_spec(
        22,
        16,
        56,
        "typography",
        "Taille H3 (px)",
        "Taille des sous-titres.",
        preview_var="--preview-font-size-h3",
    ),
    "font_size_body": _int_spec(
        15,
        12,
        26,
        "typography",
        "Taille texte (px)",
        "Taille principale des paragraphes.",
        preview_var="--preview-font-size-body",
    ),
    "font_size_small": _int_spec(
        13,
        10,
        20,
        "typography",
        "Taille texte secondaire (px)",
        "Taille des aides/infos secondaires.",
        preview_var="--preview-font-size-small",
    ),
    "line_height_heading": _choice_spec(
        "1.2",
        LINE_HEIGHT_HEADING_CHOICES,
        "typography",
        "Interligne titres",
        "Hauteur de ligne pour H1/H2/H3.",
        preview_var="--preview-line-height-heading",
    ),
    "line_height_body": _choice_spec(
        "1.5",
        LINE_HEIGHT_BODY_CHOICES,
        "typography",
        "Interligne texte",
        "Hauteur de ligne des paragraphes et listes.",
        preview_var="--preview-line-height-body",
    ),
    "font_weight_heading": _choice_spec(
        "700",
        FONT_WEIGHT_CHOICES,
        "typography",
        "Graisse titres",
        "Epaisseur des titres (600/700/800).",
        preview_var="--preview-font-weight-heading",
    ),
    "font_weight_body": _choice_spec(
        "500",
        FONT_WEIGHT_CHOICES,
        "typography",
        "Graisse texte",
        "Epaisseur des paragraphes.",
        preview_var="--preview-font-weight-body",
    ),
    "font_weight_button": _choice_spec(
        "700",
        FONT_WEIGHT_CHOICES,
        "typography",
        "Graisse boutons",
        "Epaisseur des libelles de boutons.",
        preview_var="--preview-font-weight-button",
    ),
    "letter_spacing_heading": _choice_spec(
        "0.01em",
        LETTER_SPACING_HEADING_CHOICES,
        "typography",
        "Espacement lettres titres",
        "Ajuste l'espacement horizontal des caracteres des titres.",
        preview_var="--preview-letter-spacing-heading",
    ),
    "letter_spacing_body": _choice_spec(
        "0.005em",
        LETTER_SPACING_BODY_CHOICES,
        "typography",
        "Espacement lettres texte",
        "Ajuste l'espacement horizontal du texte courant.",
        preview_var="--preview-letter-spacing-body",
    ),
    "text_transform_heading": _choice_spec(
        "none",
        TEXT_TRANSFORM_CHOICES,
        "typography",
        "Transformation titres",
        "Normal ou MAJUSCULE pour les titres.",
        preview_var="--preview-text-transform-heading",
    ),
    "color_surface_alt": _color_spec(
        "#f1f6f3",
        "global_colors",
        "Surface secondaire",
        "Fond alternatif pour sections secondaires.",
    ),
    "color_panel": _color_spec(
        "#fffdf9",
        "global_colors",
        "Couleur panneau",
        "Fond des panneaux et outils.",
    ),
    "color_link": _color_spec(
        "#2f6d5f",
        "global_colors",
        "Couleur lien",
        "Couleur des liens cliquables.",
    ),
    "color_link_hover": _color_spec(
        "#245648",
        "global_colors",
        "Couleur lien (survol)",
        "Couleur des liens au survol.",
    ),
    "color_focus_ring": _color_spec(
        "#78a99b",
        "global_colors",
        "Anneau focus",
        "Couleur de contour clavier/focus.",
    ),
    "color_disabled_bg": _color_spec(
        "#edf2ef",
        "global_colors",
        "Fond desactive",
        "Fond des elements desactives.",
    ),
    "color_disabled_text": _color_spec(
        "#8a9791",
        "global_colors",
        "Texte desactive",
        "Texte des elements desactives.",
    ),
    "color_disabled_border": _color_spec(
        "#d2ddd8",
        "global_colors",
        "Bordure desactivee",
        "Bordure des elements desactives.",
    ),
    "btn_style_mode": _choice_spec(
        "flat",
        BTN_STYLE_MODE_CHOICES,
        "buttons",
        "Style boutons",
        "Flat, soft, elevated ou outlined.",
    ),
    "btn_radius": _int_spec(
        10,
        0,
        120,
        "buttons",
        "Rayon bouton (px)",
        "0 = angle droit, 12 = arrondi marque, 999 = pilule.",
        preview_var="--preview-btn-radius",
    ),
    "btn_height_md": _int_spec(
        42,
        24,
        120,
        "buttons",
        "Hauteur bouton md (px)",
        "Hauteur des boutons standards.",
        preview_var="--preview-btn-height",
    ),
    "btn_border_width": _int_spec(
        1,
        0,
        6,
        "buttons",
        "Epaisseur bordure bouton (px)",
        "Epaisseur du contour des boutons.",
        preview_var="--preview-btn-border-width",
    ),
    "btn_padding_x": _int_spec(
        14,
        6,
        40,
        "buttons",
        "Padding horizontal bouton (px)",
        "Largeur interne horizontale des boutons.",
        preview_var="--preview-btn-padding-x",
    ),
    "btn_font_size": _int_spec(
        14,
        11,
        24,
        "buttons",
        "Taille texte bouton (px)",
        "Taille du libelle des boutons.",
        preview_var="--preview-btn-font-size",
    ),
    "btn_shadow": _text_spec(
        "none",
        "buttons",
        "Ombre bouton",
        'Ex: "none" ou "0 2px 8px rgba(39,57,50,.12)".',
        preview_var="--preview-btn-shadow",
    ),
    "color_btn_primary_bg": _color_spec(
        "#6f9a8d",
        "buttons",
        "Btn primaire - fond",
        "Fond du bouton principal.",
        preview_var="--preview-btn-primary-bg",
    ),
    "color_btn_primary_text": _color_spec(
        "#f7faf8",
        "buttons",
        "Btn primaire - texte",
        "Texte du bouton principal.",
        preview_var="--preview-btn-primary-text",
    ),
    "color_btn_primary_border": _color_spec(
        "#5d8579",
        "buttons",
        "Btn primaire - bordure",
        "Bordure du bouton principal (independante du fond).",
        preview_var="--preview-btn-primary-border",
    ),
    "color_btn_secondary_bg": _color_spec(
        "#e7cdb3",
        "buttons",
        "Btn secondaire - fond",
        "Fond du bouton secondaire.",
        preview_var="--preview-btn-secondary-bg",
    ),
    "color_btn_secondary_text": _color_spec(
        "#2f3a36",
        "buttons",
        "Btn secondaire - texte",
        "Texte du bouton secondaire.",
        preview_var="--preview-btn-secondary-text",
    ),
    "color_btn_secondary_border": _color_spec(
        "#ceaf90",
        "buttons",
        "Btn secondaire - bordure",
        "Bordure du bouton secondaire.",
        preview_var="--preview-btn-secondary-border",
    ),
    "input_height": _int_spec(
        42,
        24,
        120,
        "inputs",
        "Hauteur champ (px)",
        "Hauteur minimale des champs.",
    ),
    "input_radius": _int_spec(
        10,
        0,
        120,
        "inputs",
        "Rayon champ (px)",
        "0 = angle droit, 10 = arrondi standard.",
    ),
    "input_padding_x": _int_spec(
        12,
        4,
        30,
        "inputs",
        "Padding horizontal champ (px)",
        "Espace interieur gauche/droite du champ.",
    ),
    "input_padding_y": _int_spec(
        8,
        2,
        24,
        "inputs",
        "Padding vertical champ (px)",
        "Espace interieur haut/bas du champ.",
    ),
    "input_border_width": _int_spec(
        1,
        1,
        4,
        "inputs",
        "Epaisseur bordure champ (px)",
        "Epaisseur du contour des champs.",
    ),
    "input_bg": _color_spec(
        "#fffdf9",
        "inputs",
        "Fond champ",
        "Fond des champs de saisie.",
    ),
    "input_border": _color_spec(
        "#d9e2dc",
        "inputs",
        "Bordure champ",
        "Couleur du contour des champs.",
    ),
    "input_text": _color_spec(
        "#2f3a36",
        "inputs",
        "Texte champ",
        "Couleur du texte saisi dans les champs.",
    ),
    "input_placeholder": _color_spec(
        "#7a8b84",
        "inputs",
        "Placeholder champ",
        "Couleur du texte indicatif des champs.",
    ),
    "input_focus_border": _color_spec(
        "#6f9a8d",
        "inputs",
        "Bordure focus champ",
        "Couleur de bordure quand le champ est actif.",
    ),
    "input_focus_shadow": _text_spec(
        "0 0 0 0.2rem rgba(111, 154, 141, 0.24)",
        "inputs",
        "Ombre focus champ",
        "Anneau de focus des champs.",
    ),
    "card_radius": _int_spec(
        16,
        0,
        120,
        "cards",
        "Rayon card (px)",
        "Rayon des cartes/panneaux.",
        preview_var="--preview-card-radius",
    ),
    "card_border_width": _int_spec(
        1,
        1,
        6,
        "cards",
        "Epaisseur bordure card (px)",
        "Epaisseur de contour des cartes.",
    ),
    "card_border_color": _color_spec(
        "#d9e2dc",
        "cards",
        "Bordure card",
        "Couleur de bordure des cartes.",
    ),
    "card_bg": _color_spec(
        "#fffdf9",
        "cards",
        "Fond card",
        "Fond principal des cartes.",
        preview_var="--preview-surface",
    ),
    "card_shadow": _text_spec(
        "none",
        "cards",
        "Ombre card",
        "Ombre de profondeur des cartes.",
        preview_var="--preview-card-shadow",
    ),
    "card_header_bg": _color_spec(
        "#f1f6f3",
        "cards",
        "Fond entete card",
        "Fond des en-tetes de modules.",
    ),
    "card_header_text": _color_spec(
        "#2f3a36",
        "cards",
        "Texte entete card",
        "Texte des en-tetes de modules.",
    ),
    "nav_item_active_bg": _color_spec(
        "#ddebe6",
        "navigation",
        "Nav actif - fond",
        "Fond de l'item actif dans la navigation.",
        preview_var="--preview-nav-active-bg",
    ),
    "nav_item_active_text": _color_spec(
        "#2f3a36",
        "navigation",
        "Nav actif - texte",
        "Texte de l'item actif dans la navigation.",
        preview_var="--preview-nav-active-text",
    ),
    "nav_item_bg": _color_spec(
        "#fffdf9",
        "navigation",
        "Nav standard - fond",
        "Fond des items de navigation non actifs.",
    ),
    "nav_item_text": _color_spec(
        "#2f3a36",
        "navigation",
        "Nav standard - texte",
        "Texte des items de navigation non actifs.",
    ),
    "nav_item_border": _color_spec(
        "#d9e2dc",
        "navigation",
        "Nav standard - bordure",
        "Bordure des items de navigation.",
        preview_var="--preview-nav-border",
    ),
    "nav_item_hover_bg": _color_spec(
        "#e9f2ee",
        "navigation",
        "Nav survol - fond",
        "Fond des items au survol.",
    ),
    "nav_item_hover_text": _color_spec(
        "#2b4f45",
        "navigation",
        "Nav survol - texte",
        "Texte des items au survol.",
    ),
    "nav_item_radius": _int_spec(
        10,
        0,
        32,
        "navigation",
        "Rayon item nav (px)",
        "Arrondi des items de navigation.",
    ),
    "nav_item_padding_x": _int_spec(
        10,
        4,
        24,
        "navigation",
        "Padding horizontal nav (px)",
        "Largeur interne gauche/droite des items nav.",
    ),
    "nav_item_padding_y": _int_spec(
        7,
        2,
        20,
        "navigation",
        "Padding vertical nav (px)",
        "Hauteur interne des items nav.",
    ),
    "nav_item_font_size": _choice_spec(
        "14px",
        NAV_FONT_SIZE_CHOICES,
        "navigation",
        "Taille texte nav",
        "Taille du texte des items de navigation.",
        preview_var="--preview-nav-font-size",
    ),
    "nav_item_font_weight": _choice_spec(
        "700",
        FONT_WEIGHT_CHOICES,
        "navigation",
        "Graisse texte nav",
        "Epaisseur du texte des items de navigation.",
        preview_var="--preview-nav-font-weight",
    ),
    "nav_item_line_height": _choice_spec(
        "1.2",
        NAV_LINE_HEIGHT_CHOICES,
        "navigation",
        "Interligne nav",
        "Hauteur de ligne des items de navigation.",
        preview_var="--preview-nav-line-height",
    ),
    "nav_item_letter_spacing": _choice_spec(
        "0.01em",
        LETTER_SPACING_HEADING_CHOICES,
        "navigation",
        "Espacement lettres nav",
        "Espacement horizontal du texte des items nav.",
        preview_var="--preview-nav-letter-spacing",
    ),
    "dropdown_shadow": _text_spec(
        "none",
        "navigation",
        "Ombre dropdown",
        "Ombre des menus deroulants.",
    ),
    "dropdown_bg": _color_spec(
        "#fffdf9",
        "navigation",
        "Fond dropdown",
        "Fond des menus deroulants.",
    ),
    "dropdown_border": _color_spec(
        "#d9e2dc",
        "navigation",
        "Bordure dropdown",
        "Bordure des menus deroulants.",
    ),
    "dropdown_item_font_size": _choice_spec(
        "14px",
        NAV_FONT_SIZE_CHOICES,
        "navigation",
        "Dropdown - taille texte",
        "Taille du texte des items du menu deroulant.",
    ),
    "dropdown_item_font_weight": _choice_spec(
        "600",
        FONT_WEIGHT_CHOICES,
        "navigation",
        "Dropdown - graisse texte",
        "Epaisseur du texte des items du menu deroulant.",
    ),
    "dropdown_item_padding_y": _int_spec(
        7,
        3,
        20,
        "navigation",
        "Dropdown - padding vertical (px)",
        "Espacement vertical interne des items du dropdown.",
    ),
    "dropdown_item_padding_x": _int_spec(
        9,
        4,
        30,
        "navigation",
        "Dropdown - padding horizontal (px)",
        "Espacement horizontal interne des items du dropdown.",
    ),
    "table_row_hover_bg": _color_spec(
        "#e7f1ec",
        "tables",
        "Table hover - fond",
        "Fond d'une ligne de tableau au survol.",
    ),
    "table_header_bg": _color_spec(
        "#edf4f0",
        "tables",
        "Table header - fond",
        "Fond de l'en-tete des tableaux.",
    ),
    "table_header_text": _color_spec(
        "#2f3a36",
        "tables",
        "Table header - texte",
        "Texte de l'en-tete des tableaux.",
    ),
    "table_header_font_size": _choice_spec(
        "12px",
        TABLE_HEADER_FONT_SIZE_CHOICES,
        "tables",
        "Table header - taille texte",
        "Taille du texte de l'en-tete du tableau.",
        preview_var="--preview-table-header-font-size",
    ),
    "table_header_letter_spacing": _choice_spec(
        "0.05em",
        TABLE_HEADER_LETTER_SPACING_CHOICES,
        "tables",
        "Table header - espacement lettres",
        "Espacement horizontal du texte de l'en-tete.",
        preview_var="--preview-table-header-letter-spacing",
    ),
    "table_header_padding_y": _int_spec(
        10,
        4,
        24,
        "tables",
        "Table header - padding vertical (px)",
        "Espacement vertical des cellules d'en-tete.",
        preview_var="--preview-table-header-padding-y",
    ),
    "table_header_padding_x": _int_spec(
        8,
        4,
        28,
        "tables",
        "Table header - padding horizontal (px)",
        "Espacement horizontal des cellules d'en-tete.",
        preview_var="--preview-table-header-padding-x",
    ),
    "table_cell_padding_y": _int_spec(
        6,
        2,
        28,
        "tables",
        "Table cellule - padding vertical (px)",
        "Espacement vertical des cellules de donnees.",
        preview_var="--preview-table-cell-padding-y",
    ),
    "table_cell_padding_x": _int_spec(
        8,
        2,
        32,
        "tables",
        "Table cellule - padding horizontal (px)",
        "Espacement horizontal des cellules de donnees.",
        preview_var="--preview-table-cell-padding-x",
    ),
    "table_row_bg": _color_spec(
        "#ffffff",
        "tables",
        "Table ligne - fond",
        "Fond des lignes standards.",
    ),
    "table_row_alt_bg": _color_spec(
        "#f8fbf9",
        "tables",
        "Table ligne alternee - fond",
        "Fond des lignes alternees.",
    ),
    "table_border_color": _color_spec(
        "#d9e2dc",
        "tables",
        "Table bordure",
        "Couleur des separateurs de tableau.",
    ),
    "table_radius": _int_spec(
        10,
        0,
        30,
        "tables",
        "Rayon tableau (px)",
        "Arrondi des conteneurs de tableaux.",
    ),
    "badge_radius": _int_spec(
        999,
        0,
        999,
        "business_states",
        "Rayon badge (px)",
        "Arrondi des badges/etiquettes.",
    ),
    "badge_font_size": _int_spec(
        12,
        10,
        18,
        "business_states",
        "Taille texte badge (px)",
        "Taille de texte pour badges et pills.",
    ),
    "color_btn_success_bg": _color_spec(
        "#e8f4ee",
        "business_states",
        "Btn success - fond",
        "Couleur des actions success.",
        preview_var="--preview-success-bg",
    ),
    "color_btn_success_text": _color_spec(
        "#2d5e46",
        "business_states",
        "Btn success - texte",
        "Couleur du texte des actions success.",
        preview_var="--preview-success-text",
    ),
    "color_btn_success_border": _color_spec(
        "#b8d6c8",
        "business_states",
        "Btn success - bordure",
        "Bordure des actions success.",
        preview_var="--preview-success-border",
    ),
    "color_btn_success_hover_bg": _color_spec(
        "#d8ebdf",
        "business_states",
        "Btn success - hover fond",
        "Couleur de fond au survol des actions success.",
    ),
    "color_btn_success_active_bg": _color_spec(
        "#cfe4d8",
        "business_states",
        "Btn success - actif fond",
        "Couleur de fond en etat actif des actions success.",
    ),
    "color_btn_warning_bg": _color_spec(
        "#fbf2e7",
        "business_states",
        "Btn warning - fond",
        "Couleur des actions warning.",
        preview_var="--preview-warning-bg",
    ),
    "color_btn_warning_text": _color_spec(
        "#715829",
        "business_states",
        "Btn warning - texte",
        "Couleur du texte des actions warning.",
        preview_var="--preview-warning-text",
    ),
    "color_btn_warning_border": _color_spec(
        "#e5d0a6",
        "business_states",
        "Btn warning - bordure",
        "Bordure des actions warning.",
        preview_var="--preview-warning-border",
    ),
    "color_btn_warning_hover_bg": _color_spec(
        "#f3e6d2",
        "business_states",
        "Btn warning - hover fond",
        "Couleur de fond au survol des actions warning.",
    ),
    "color_btn_warning_active_bg": _color_spec(
        "#ead8bb",
        "business_states",
        "Btn warning - actif fond",
        "Couleur de fond en etat actif des actions warning.",
    ),
    "color_btn_danger_bg": _color_spec(
        "#faece7",
        "business_states",
        "Btn danger - fond",
        "Couleur des actions danger.",
        preview_var="--preview-danger-bg",
    ),
    "color_btn_danger_text": _color_spec(
        "#7b3030",
        "business_states",
        "Btn danger - texte",
        "Couleur du texte des actions danger.",
        preview_var="--preview-danger-text",
    ),
    "color_btn_danger_border": _color_spec(
        "#dfb0b0",
        "business_states",
        "Btn danger - bordure",
        "Bordure des actions danger.",
        preview_var="--preview-danger-border",
    ),
    "color_btn_danger_hover_bg": _color_spec(
        "#f2d8d6",
        "business_states",
        "Btn danger - hover fond",
        "Couleur de fond au survol des actions danger.",
    ),
    "color_btn_danger_active_bg": _color_spec(
        "#e9c9c7",
        "business_states",
        "Btn danger - actif fond",
        "Couleur de fond en etat actif des actions danger.",
    ),
    "status_ready_bg": _color_spec(
        "#e8f4ee",
        "business_states",
        "Etat pret - fond",
        "Fond du statut Pret.",
    ),
    "status_ready_text": _color_spec(
        "#2d5e46",
        "business_states",
        "Etat pret - texte",
        "Texte du statut Pret.",
    ),
    "status_ready_border": _color_spec(
        "#b8d6c8",
        "business_states",
        "Etat pret - bordure",
        "Bordure du statut Pret.",
    ),
    "status_progress_bg": _color_spec(
        "#eef3fb",
        "business_states",
        "Etat en cours - fond",
        "Fond du statut En cours.",
    ),
    "status_progress_text": _color_spec(
        "#274d7f",
        "business_states",
        "Etat en cours - texte",
        "Texte du statut En cours.",
    ),
    "status_progress_border": _color_spec(
        "#b4cbe7",
        "business_states",
        "Etat en cours - bordure",
        "Bordure du statut En cours.",
    ),
    "status_warning_bg": _color_spec(
        "#fbf2e7",
        "business_states",
        "Etat alerte - fond",
        "Fond du statut Alerte.",
    ),
    "status_warning_text": _color_spec(
        "#715829",
        "business_states",
        "Etat alerte - texte",
        "Texte du statut Alerte.",
    ),
    "status_warning_border": _color_spec(
        "#e5d0a6",
        "business_states",
        "Etat alerte - bordure",
        "Bordure du statut Alerte.",
    ),
    "status_error_bg": _color_spec(
        "#faece7",
        "business_states",
        "Etat erreur - fond",
        "Fond du statut Erreur.",
    ),
    "status_error_text": _color_spec(
        "#7b3030",
        "business_states",
        "Etat erreur - texte",
        "Texte du statut Erreur.",
    ),
    "status_error_border": _color_spec(
        "#dfb0b0",
        "business_states",
        "Etat erreur - bordure",
        "Bordure du statut Erreur.",
    ),
    "status_info_bg": _color_spec(
        "#e7f1ec",
        "business_states",
        "Etat info - fond",
        "Fond du statut Information.",
    ),
    "status_info_text": _color_spec(
        "#355f53",
        "business_states",
        "Etat info - texte",
        "Texte du statut Information.",
    ),
    "status_info_border": _color_spec(
        "#b8d2c8",
        "business_states",
        "Etat info - bordure",
        "Bordure du statut Information.",
    ),
}

DESIGN_TOKEN_DEFAULTS = {
    token_key: spec["default"] for token_key, spec in DESIGN_TOKEN_SPECS.items()
}

DESIGN_TOKEN_FIELD_TO_KEY = {
    f"design_{token_key}": token_key for token_key in DESIGN_TOKEN_SPECS
}

DESIGN_TOKEN_COLOR_KEYS = tuple(
    token_key
    for token_key, spec in DESIGN_TOKEN_SPECS.items()
    if spec["kind"] == "color"
)
DESIGN_TOKEN_INT_KEYS = tuple(
    token_key for token_key, spec in DESIGN_TOKEN_SPECS.items() if spec["kind"] == "int"
)
DESIGN_TOKEN_TEXT_KEYS = tuple(
    token_key for token_key, spec in DESIGN_TOKEN_SPECS.items() if spec["kind"] == "text"
)

DESIGN_TOKEN_FAMILY_FIELDS = {
    family_key: tuple(
        f"design_{token_key}"
        for token_key, spec in DESIGN_TOKEN_SPECS.items()
        if spec["family"] == family_key
    )
    for family_key, _label, _description, _open in DESIGN_TOKEN_FAMILY_DEFINITIONS
}

PRIORITY_ONE_TOKEN_DEFAULTS = DESIGN_TOKEN_DEFAULTS
PRIORITY_ONE_TOKEN_FIELD_TO_KEY = DESIGN_TOKEN_FIELD_TO_KEY
PRIORITY_ONE_TOKEN_COLOR_KEYS = DESIGN_TOKEN_COLOR_KEYS
PRIORITY_ONE_TOKEN_INT_KEYS = DESIGN_TOKEN_INT_KEYS
PRIORITY_ONE_TOKEN_SHADOW_KEYS = DESIGN_TOKEN_TEXT_KEYS


def normalize_priority_one_tokens(raw_tokens):
    normalized = dict(DESIGN_TOKEN_DEFAULTS)
    if not isinstance(raw_tokens, dict):
        return normalized

    for token_key, spec in DESIGN_TOKEN_SPECS.items():
        kind = spec["kind"]
        raw_value = raw_tokens.get(token_key)

        if kind == "choice":
            value = str(raw_value or "").strip().lower()
            allowed = {choice_value for choice_value, _label in spec["choices"]}
            if value in allowed:
                normalized[token_key] = value
            continue

        if kind == "int":
            try:
                resolved = int(raw_value)
            except (TypeError, ValueError):
                continue
            normalized[token_key] = max(spec["min"], min(spec["max"], resolved))
            continue

        if kind == "color":
            value = str(raw_value or "").strip()
            if HEX_COLOR_RE.match(value):
                normalized[token_key] = value.lower()
            continue

        if kind == "text":
            value = str(raw_value or "").strip()
            if value:
                normalized[token_key] = value[: spec.get("max_length", 120)]
            continue

    return normalized


def density_factor_for_mode(mode):
    return {
        "dense": 0.9,
        "standard": 1.0,
        "airy": 1.12,
    }.get((mode or "").strip().lower(), 1.0)
