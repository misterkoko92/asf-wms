from .print_renderer import render_layout_from_layout


def chunked(items, size):
    return [items[i : i + size] for i in range(0, len(items), size)]


def extract_block_style(layout, block_type):
    if not isinstance(layout, dict):
        return {}
    blocks = layout.get("blocks") or []
    for block in blocks:
        if block.get("type") == block_type:
            return block.get("style") or {}
    return {}


def build_label_pages(
    layout, contexts, block_type="product_label", labels_per_page=4
):
    labels = []
    for context in contexts:
        blocks = render_layout_from_layout(layout, context)
        labels.append({"blocks": blocks})
    pages = chunked(labels, labels_per_page)
    page_style = extract_block_style(layout, block_type)
    return pages, page_style
