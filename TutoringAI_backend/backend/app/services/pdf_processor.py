import fitz  # PyMuPDF

def extract_pdf_pages(file_path: str):
    """Returns [{"page_number": 1, "text": "..."}, ...]"""
    doc = fitz.open(file_path)
    pages = []
    for i, page in enumerate(doc):
        text = page.get_text("text").strip()
        if text:
            pages.append({"page_number": i + 1, "text": text})
    doc.close()
    return pages