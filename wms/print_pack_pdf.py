from io import BytesIO

try:
    from pypdf import PdfReader, PdfWriter
except ImportError:  # pragma: no cover - optional dependency at runtime
    PdfReader = None
    PdfWriter = None


class PrintPackPdfError(RuntimeError):
    """Raised when PDF merge operations cannot be completed."""


def merge_pdf_documents(pdf_list):
    if not pdf_list:
        raise PrintPackPdfError("No PDF documents were provided for merge.")
    if PdfReader is None or PdfWriter is None:
        raise PrintPackPdfError("pypdf is required to merge PDF documents.")

    writer = PdfWriter()
    for payload in pdf_list:
        reader = PdfReader(BytesIO(payload))
        for page in reader.pages:
            writer.add_page(page)

    output = BytesIO()
    writer.write(output)
    return output.getvalue()
