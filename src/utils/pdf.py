import tempfile
from pathlib import Path


def pdf_page_batches(file_path, pages_per_batch):
    try:
        from pypdf import PdfReader, PdfWriter
    except ImportError as error:
        raise RuntimeError("Install pypdf to batch PDF bank statements by page.") from error

    reader = PdfReader(str(file_path))
    batches = []
    for start in range(0, len(reader.pages), pages_per_batch):
        writer = PdfWriter()
        end = min(start + pages_per_batch, len(reader.pages))
        for page in reader.pages[start:end]:
            writer.add_page(page)
        batch_file = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
        with batch_file:
            writer.write(batch_file)
        batches.append((f"pages {start + 1}-{end}", Path(batch_file.name)))
    return batches
