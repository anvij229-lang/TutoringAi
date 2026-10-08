from app.database.db import get_connection
from app.services.embeddings import create_embeddings
from app.services.pdf_processor import extract_pdf_pages


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 100):
    text = text.replace("\u200b", "").replace("\u25cf", "-")
    text = " ".join(text.split())
    if not text:
        return []
    chunks, start = [], 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(text):
            break
        start = end - overlap
    return chunks


def ingest_pdf(file_path: str, title: str, file_name: str):
    pages = extract_pdf_pages(file_path)
    if not pages:
        raise ValueError("No readable text found in PDF")

    records = []
    for page in pages:
        for idx, content in enumerate(chunk_text(page["text"])):
            records.append({
                "content": content,
                "page_number": page["page_number"],
                "chunk_index": idx,
            })
    if not records:
        raise ValueError("No chunks were generated")

    embeddings = create_embeddings([r["content"] for r in records])
    if len(embeddings) != len(records):
        raise RuntimeError("Embedding count does not match chunk count")

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO materials (title, file_name, file_type) "
                "VALUES (%s, %s, %s) RETURNING id",
                (title, file_name, "pdf"),
            )
            material_id = cur.fetchone()[0]

            rows = [
                (material_id, r["content"], r["page_number"],
                 r["chunk_index"], str(emb))   # ⚠️ Fix: string + ::vector cast
                for r, emb in zip(records, embeddings)
            ]
            cur.executemany(
                "INSERT INTO chunks "
                "(material_id, content, page_number, chunk_index, embedding) "
                "VALUES (%s, %s, %s, %s, %s::vector)",
                rows,
            )
        conn.commit()

    return {
        "material_id": str(material_id),
        "pages_processed": len(pages),
        "chunks_created": len(records),
    }