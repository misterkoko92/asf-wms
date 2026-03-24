from io import BytesIO

try:
    from pypdf import PdfReader, PdfWriter, Transformation
except ImportError:  # pragma: no cover - optional dependency at runtime
    PdfReader = None
    PdfWriter = None
    Transformation = None


class PrintPackPdfError(RuntimeError):
    """Raised when PDF merge operations cannot be completed."""


POINTS_PER_MM = 72 / 25.4
A4_WIDTH_POINTS = 210 * POINTS_PER_MM
A4_HEIGHT_POINTS = 297 * POINTS_PER_MM


def _require_pypdf():
    if PdfReader is None or PdfWriter is None or Transformation is None:
        raise PrintPackPdfError("pypdf is required to merge PDF documents.")


def merge_pdf_documents(pdf_list):
    if not pdf_list:
        raise PrintPackPdfError("No PDF documents were provided for merge.")
    _require_pypdf()

    writer = PdfWriter()
    for payload in pdf_list:
        reader = PdfReader(BytesIO(payload))
        for page in reader.pages:
            writer.add_page(page)

    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def impose_two_up_pdf_on_a4(pdf_list):
    if not pdf_list:
        raise PrintPackPdfError("No PDF documents were provided for merge.")
    _require_pypdf()

    writer = PdfWriter()
    source_pages = []
    for payload in pdf_list:
        reader = PdfReader(BytesIO(payload))
        source_pages.extend(reader.pages)

    slot_width = A4_WIDTH_POINTS
    slot_height = A4_HEIGHT_POINTS / 2
    for index in range(0, len(source_pages), 2):
        sheet = writer.add_blank_page(width=A4_WIDTH_POINTS, height=A4_HEIGHT_POINTS)
        for slot_index, page in enumerate(source_pages[index : index + 2]):
            page_width = float(page.mediabox.width)
            page_height = float(page.mediabox.height)
            if page_width <= 0 or page_height <= 0:
                raise PrintPackPdfError("PDF page dimensions must be positive.")
            scale = min(slot_width / page_width, slot_height / page_height)
            rendered_width = page_width * scale
            rendered_height = page_height * scale
            x_offset = (slot_width - rendered_width) / 2
            base_y_offset = slot_height if slot_index == 0 else 0
            y_offset = base_y_offset + ((slot_height - rendered_height) / 2)
            transformation = Transformation().scale(scale).translate(x_offset, y_offset)
            sheet.merge_transformed_page(page, transformation)

    output = BytesIO()
    writer.write(output)
    return output.getvalue()
