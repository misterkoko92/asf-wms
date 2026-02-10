import json

from django.template import Context, Template
from django.template.loader import render_to_string
from django.utils.safestring import mark_safe

from .models import PrintTemplate
from .print_layouts import DEFAULT_LAYOUTS

EMPTY_LAYOUT = {"blocks": []}
TEXT_DEFAULT_TAG = "div"

CONTACT_LABEL_DEFAULTS = {
    "company": "Societe",
    "person": "Nom",
    "address": "Adresse",
    "phone": "Tel",
    "email": "Mail",
}

CONTACT_BLOCK_DEFAULTS = {
    "title_shipper": "EXPEDITEUR",
    "title_recipient": "DESTINATAIRE",
    "title_correspondent": "CORRESPONDANT",
    "show_company": True,
    "show_person": True,
    "show_address": True,
    "show_phone": True,
    "show_email": True,
}

SIMPLE_CONTEXT_BLOCK_TEMPLATES = {
    "summary_triplet": "print/blocks/summary_triplet.html",
    "table_cartons": "print/blocks/table_cartons.html",
}

BLOCK_CONTEXT_TEMPLATES = {
    "signatures": "print/blocks/signatures.html",
}

BLOCK_STYLE_TEMPLATES = {
    "label_city": "print/blocks/label_city.html",
    "label_iata": "print/blocks/label_iata.html",
    "label_footer": "print/blocks/label_footer.html",
    "product_label": "print/blocks/product_label.html",
    "product_qr_label": "print/blocks/product_qr_label.html",
}


def _render_template_string(value, context):
    template = Template(value or "")
    return template.render(Context(context))


def _build_style(style):
    if not style:
        return ""
    rules = []
    if style.get("border"):
        rules.append("border:1px solid #000;")
    padding = style.get("padding")
    if padding:
        rules.append(f"padding:{padding};")
    align = style.get("align")
    if align:
        rules.append(f"text-align:{align};")
    font_size = style.get("font_size")
    if font_size:
        rules.append(f"font-size:{font_size};")
    line_height = style.get("line_height")
    if line_height:
        rules.append(f"line-height:{line_height};")
    color = style.get("color")
    if color:
        rules.append(f"color:{color};")
    background = style.get("background")
    if background:
        rules.append(f"background:{background};")
    font_weight = style.get("font_weight")
    if font_weight:
        rules.append(f"font-weight:{font_weight};")
    return " ".join(rules)


def _render_text_block(block, context):
    tag = block.get("tag") or TEXT_DEFAULT_TAG
    text = _render_template_string(block.get("text", ""), context)
    style = _build_style(block.get("style", {}))
    return mark_safe(f"<{tag} style=\"{style}\">{text}</{tag}>")


def _render_simple_template_block(block_type, context):
    template_name = SIMPLE_CONTEXT_BLOCK_TEMPLATES[block_type]
    return render_to_string(template_name, context)


def _render_block_context_template(block_type, block, context):
    template_name = BLOCK_CONTEXT_TEMPLATES[block_type]
    return render_to_string(template_name, {"block": block, **context})


def _render_block_style_template(block_type, block, context):
    template_name = BLOCK_STYLE_TEMPLATES[block_type]
    return render_to_string(
        template_name,
        {"block": block, "style": block.get("style", {}), **context},
    )


def _build_contacts_row_payload(block, context):
    block_data = dict(block)
    for key, value in CONTACT_BLOCK_DEFAULTS.items():
        block_data.setdefault(key, value)
    labels = dict(CONTACT_LABEL_DEFAULTS)
    labels.update(block.get("labels") or {})
    return {
        "block": block_data,
        "style": block.get("style", {}),
        "labels": labels,
        **context,
    }


def _render_contacts_row_block(block, context):
    return render_to_string(
        "print/blocks/contacts_row.html",
        _build_contacts_row_payload(block, context),
    )


def _render_table_items_block(block, context):
    context_for_block = dict(context)
    if block.get("mode") == "aggregate":
        aggregate_rows = context.get("aggregate_rows")
        if aggregate_rows is not None:
            context_for_block["item_rows"] = aggregate_rows
    return render_to_string(
        "print/blocks/table_items.html",
        {"block": block, **context_for_block},
    )


def _render_block(block, context):
    block_type = block.get("type")
    if block_type == "text":
        return _render_text_block(block, context)
    if block_type in SIMPLE_CONTEXT_BLOCK_TEMPLATES:
        return _render_simple_template_block(block_type, context)
    if block_type == "contacts_row":
        return _render_contacts_row_block(block, context)
    if block_type in BLOCK_CONTEXT_TEMPLATES:
        return _render_block_context_template(block_type, block, context)
    if block_type == "table_items":
        return _render_table_items_block(block, context)
    if block_type in BLOCK_STYLE_TEMPLATES:
        return _render_block_style_template(block_type, block, context)
    return ""


def _normalize_layout(layout):
    if not isinstance(layout, dict):
        return dict(EMPTY_LAYOUT)
    blocks = layout.get("blocks") or []
    if not isinstance(blocks, list):
        blocks = []
    return {"blocks": blocks}


def get_default_layout(doc_type):
    return DEFAULT_LAYOUTS.get(doc_type, dict(EMPTY_LAYOUT))


def get_template_layout(doc_type):
    template = PrintTemplate.objects.filter(doc_type=doc_type).first()
    if template and template.layout:
        return template.layout
    return None


def resolve_layout(doc_type):
    layout = get_template_layout(doc_type)
    if layout is None:
        layout = get_default_layout(doc_type)
    return _normalize_layout(layout)


def render_layout_from_layout(layout, context):
    layout = _normalize_layout(layout)
    rendered = []
    for block in layout["blocks"]:
        rendered_block = _render_block(block, context)
        if rendered_block:
            rendered.append(rendered_block)
    return rendered


def render_layout(doc_type, context):
    layout = resolve_layout(doc_type)
    return render_layout_from_layout(layout, context)


def layout_changed(previous, updated):
    if previous is None:
        return True
    return json.dumps(previous, sort_keys=True) != json.dumps(updated, sort_keys=True)
