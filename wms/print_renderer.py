import json

from django.template import Context, Template
from django.template.loader import render_to_string
from django.utils.safestring import mark_safe

from .models import PrintTemplate
from .print_layouts import DEFAULT_LAYOUTS


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
    tag = block.get("tag") or "div"
    text = _render_template_string(block.get("text", ""), context)
    style = _build_style(block.get("style", {}))
    return mark_safe(f"<{tag} style=\"{style}\">{text}</{tag}>")


def _render_block(block, context):
    block_type = block.get("type")
    if block_type == "text":
        return _render_text_block(block, context)
    if block_type == "summary_triplet":
        return render_to_string("print/blocks/summary_triplet.html", context)
    if block_type == "contacts_row":
        return render_to_string("print/blocks/contacts_row.html", context)
    if block_type == "signatures":
        return render_to_string(
            "print/blocks/signatures.html", {"block": block, **context}
        )
    if block_type == "table_items":
        context_for_block = dict(context)
        if block.get("mode") == "aggregate":
            aggregate_rows = context.get("aggregate_rows")
            if aggregate_rows is not None:
                context_for_block["item_rows"] = aggregate_rows
        return render_to_string(
            "print/blocks/table_items.html", {"block": block, **context_for_block}
        )
    if block_type == "table_cartons":
        return render_to_string("print/blocks/table_cartons.html", context)
    if block_type == "label_city":
        return render_to_string("print/blocks/label_city.html", context)
    if block_type == "label_iata":
        return render_to_string("print/blocks/label_iata.html", context)
    if block_type == "label_footer":
        return render_to_string("print/blocks/label_footer.html", context)
    return ""


def _normalize_layout(layout):
    if not isinstance(layout, dict):
        return {"blocks": []}
    blocks = layout.get("blocks") or []
    if not isinstance(blocks, list):
        blocks = []
    return {"blocks": blocks}


def get_default_layout(doc_type):
    return DEFAULT_LAYOUTS.get(doc_type, {"blocks": []})


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
