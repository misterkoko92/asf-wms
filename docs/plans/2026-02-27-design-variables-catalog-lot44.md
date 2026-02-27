# Design Variables Catalog - Lot 44

## Objectif
Lister toutes les variables visuelles qui peuvent être exposées dans l'onglet `Admin > Design` pour permettre un maximum d'ajustements directement depuis le site, sans toucher au code.

## Etat actuel (deja dispo)
- Typo: `H1`, `H2`, `H3`, `texte`
- Couleurs: `primaire`, `secondaire`, `fond`, `surface`, `bordure`, `texte`, `texte secondaire`

## Variables recommandees a ajouter (catalogue complet)

### 1) Densite / Espacements
- `density_mode` (`dense|standard|airy`)
- `space_unit` (px de base, ex: `4`, `6`, `8`)
- `space_xs`, `space_sm`, `space_md`, `space_lg`, `space_xl`
- `page_padding_x`, `page_padding_y`
- `card_padding`
- `section_gap`
- `field_gap`
- `table_cell_padding_y`, `table_cell_padding_x`
- `toolbar_gap`
- `inline_actions_gap`

### 2) Typographie
- `font_h4`, `font_h5`, `font_h6`
- `font_button`
- `font_mono`
- `font_size_h1`, `font_size_h2`, `font_size_h3`, `font_size_h4`, `font_size_body`, `font_size_small`
- `line_height_heading`, `line_height_body`, `line_height_small`
- `font_weight_heading`, `font_weight_body`, `font_weight_button`
- `letter_spacing_heading`, `letter_spacing_body`
- `text_transform_heading` (`none|uppercase`)

### 3) Couleurs globales
- `color_surface_alt` (surface secondaire)
- `color_panel`
- `color_overlay`
- `color_link`, `color_link_hover`
- `color_focus_ring`
- `color_disabled_bg`, `color_disabled_text`, `color_disabled_border`

### 4) Couleurs par action (boutons)
- `color_btn_primary_bg`, `color_btn_primary_text`, `color_btn_primary_border`
- `color_btn_primary_hover_bg`, `color_btn_primary_active_bg`
- `color_btn_secondary_bg`, `color_btn_secondary_text`, `color_btn_secondary_border`
- `color_btn_secondary_hover_bg`, `color_btn_secondary_active_bg`
- `color_btn_success_bg`, `color_btn_success_text`, `color_btn_success_border`
- `color_btn_warning_bg`, `color_btn_warning_text`, `color_btn_warning_border`
- `color_btn_danger_bg`, `color_btn_danger_text`, `color_btn_danger_border`
- `color_btn_info_bg`, `color_btn_info_text`, `color_btn_info_border`
- `color_btn_neutral_bg`, `color_btn_neutral_text`, `color_btn_neutral_border`

### 5) Boutons (taille / forme / relief)
- `btn_height_sm`, `btn_height_md`, `btn_height_lg`
- `btn_padding_x_sm`, `btn_padding_x_md`, `btn_padding_x_lg`
- `btn_radius`
- `btn_border_width`
- `btn_font_size`
- `btn_icon_gap`
- `btn_shadow`
- `btn_shadow_hover`
- `btn_press_translate_y`
- `btn_style_mode` (`flat|soft|elevated|outlined`)

### 6) Champs de formulaire
- `input_height`
- `input_padding_x`, `input_padding_y`
- `input_radius`
- `input_border_width`
- `input_bg`
- `input_border`
- `input_text`
- `input_placeholder`
- `input_focus_border`
- `input_focus_shadow`
- `select_chevron_color`
- `help_text_color`
- `error_text_color`
- `error_bg`
- `success_bg`

### 7) Cards / Panneaux / Modules
- `card_radius`
- `card_border_width`
- `card_border_color`
- `card_bg`
- `card_shadow`
- `card_shadow_hover`
- `card_header_bg`
- `card_header_text`
- `panel_bg`
- `panel_border`

### 8) Tableaux
- `table_header_bg`
- `table_header_text`
- `table_row_bg`
- `table_row_alt_bg`
- `table_row_hover_bg`
- `table_border_color`
- `table_radius`
- `table_filter_input_bg`
- `table_filter_input_border`
- `table_sort_icon_color`

### 9) Navigation (onglets / navbar / dropdown)
- `nav_bg`
- `nav_border`
- `nav_item_text`
- `nav_item_bg`
- `nav_item_hover_bg`
- `nav_item_hover_text`
- `nav_item_active_bg`
- `nav_item_active_text`
- `nav_item_radius`
- `nav_item_padding_x`, `nav_item_padding_y`
- `dropdown_bg`
- `dropdown_border`
- `dropdown_shadow`
- `dropdown_item_hover_bg`
- `dropdown_item_active_bg`

### 10) Modales / Overlays
- `modal_bg`
- `modal_text`
- `modal_border`
- `modal_radius`
- `modal_shadow`
- `modal_overlay_color`
- `modal_overlay_opacity`

### 11) Badges / Pills / Etats metier
- `badge_radius`
- `badge_padding_x`, `badge_padding_y`
- `badge_font_size`
- `status_ready_bg`, `status_ready_text`, `status_ready_border`
- `status_progress_bg`, `status_progress_text`, `status_progress_border`
- `status_warning_bg`, `status_warning_text`, `status_warning_border`
- `status_error_bg`, `status_error_text`, `status_error_border`
- `status_info_bg`, `status_info_text`, `status_info_border`

### 12) Ombres / Relief / Effets
- `shadow_sm`, `shadow_md`, `shadow_lg`
- `shadow_color`
- `elevation_level_default` (`0..5`)
- `surface_relief_mode` (`flat|soft|raised|glass`)
- `border_contrast`
- `backdrop_blur`
- `outline_width`
- `outline_offset`

### 13) Motion / Animations
- `motion_enabled` (`true|false`)
- `motion_duration_fast`, `motion_duration_base`, `motion_duration_slow`
- `motion_easing_standard`
- `hover_lift_px`
- `transition_property_set` (`minimal|standard|rich`)

### 14) Layout global
- `container_max_width`
- `content_max_width`
- `grid_gap`
- `kpi_card_min_width`
- `table_min_width`
- `header_height`
- `footer_height`
- `sticky_header_enabled`

### 15) Impression (si rebranche plus tard)
- `print_font_body`
- `print_font_heading`
- `print_font_size`
- `print_line_height`
- `print_border_color`
- `print_highlight_color`

## Variables prio 1 (a ajouter en premier)
1. `density_mode`
2. `btn_style_mode`
3. `btn_radius`
4. `btn_height_md`
5. `btn_shadow`
6. `card_radius`
7. `card_shadow`
8. `input_height`
9. `input_radius`
10. `nav_item_active_bg`
11. `nav_item_active_text`
12. `dropdown_shadow`
13. `table_row_hover_bg`
14. `color_btn_success_*`
15. `color_btn_warning_*`
16. `color_btn_danger_*`

## Types de controles UI recommandes dans l'onglet Design
- Couleurs: `input color` + valeur hex
- Tailles / espacements: `slider` + champ numerique
- Rayons / bordures / ombres: `slider`
- Modes: `select` (`dense|standard|airy`, `flat|soft|elevated|outlined`)
- Typographies: `select` (liste) + option custom
- Animations: `toggle` + durees

## Recommendation technique (pour evolutivite)
Pour eviter d'ajouter des dizaines de colonnes SQL a chaque lot, introduire ensuite un `design_tokens` (`JSONField`) dans `WmsRuntimeSettings`.
- Les variables critiques restent en colonnes (retro-compatibilite).
- Les nouvelles variables vont dans `design_tokens`.
- Le context processor merge: `defaults` -> `colonnes` -> `design_tokens`.
- Le template `design_vars_style.html` expose toutes les variables CSS en un seul endroit.

## Definition de fait
- Toutes les variables ci-dessus peuvent etre configurees depuis l'onglet Design.
- Aucun ajustement visuel standard ne necessite une modif CSS/HTML manuelle.
- Presets disponibles: `Calme`, `Standard`, `Contraste`, `Dense`, `Aere`.
