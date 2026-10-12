from app.database.db import get_connection
from app.services.embeddings import create_embeddings
from app.services.pdf_processor import extract_pdf_pages
from app.services.pptx_processor import extract_pptx_slides
from app.services.transcription import transcribe_video


def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 150):
    text = " ".join(text.split())
    if not text:
        return []
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(text):
            break
        start = end - overlap
    return chunks


def group_transcript(segments: list, max_chars: int = 900, max_seconds: int = 75):
    groups = []
    current = None
    for segment in segments:
        if current is None:
            current = {"start": segment["start"], "text": segment["text"]}
            continue
        too_long = len(current["text"]) + len(segment["text"]) + 1 > max_chars
        too_far = segment["start"] - current["start"] > max_seconds
        if too_long or too_far:
            groups.append(current)
            current = {"start": segment["start"], "text": segment["text"]}
        else:
            current["text"] += " " + segment["text"]
    if current is not None:
        groups.append(current)
    return groups


def records_from_pages(pages: list):
    records = []
    for page in pages:
        for index, content in enumerate(chunk_text(page["text"])):
            records.append(
                {
                    "content": content,
                    "page_number": page["page_number"],
                    "start_seconds": None,
                    "chunk_index": index,
                }
            )
    return records


def records_from_transcript(segments: list):
    records = []
    for index, group in enumerate(group_transcript(segments)):
        records.append(
            {
                "content": group["text"],
                "page_number": None,
                "start_seconds": group["start"],
                "chunk_index": index,
            }
        )
    return records


def save_material(title: str, file_name: str, file_type: str, records: list) -> str:
    embeddings = create_embeddings([r["content"] for r in records])
    if len(embeddings) != len(records):
        raise RuntimeError("Embedding count does not match chunk count")

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO materials (title, file_name, file_type) "
                "VALUES (%s, %s, %s) RETURNING id",
                (title, file_name, file_type),
            )
            material_id = cur.fetchone()[0]

            rows = [
                (
                    material_id,
                    record["content"],
                    record["page_number"],
                    record["start_seconds"],
                    record["chunk_index"],
                    str(embedding),
                )
                for record, embedding in zip(records, embeddings)
            ]
            cur.executemany(
                "INSERT INTO chunks "
                "(material_id, content, page_number, start_seconds, chunk_index, embedding) "
                "VALUES (%s, %s, %s, %s, %s, %s::vector)",
                rows,
            )
        conn.commit()
    return str(material_id)


def ingest_file(file_path: str, title: str, file_name: str, file_type: str):
    if file_type == "pdf":
        units = extract_pdf_pages(file_path)
        if not units:
            raise ValueError("No readable text found in this PDF")
        records = records_from_pages(units)
        unit_name = "pages"
    elif file_type == "pptx":
        units = extract_pptx_slides(file_path)
        if not units:
            raise ValueError("No readable text found in this presentation")
        records = records_from_pages(units)
        unit_name = "slides"
    elif file_type == "video":
        units = transcribe_video(file_path)
        records = records_from_transcript(units)
        unit_name = "transcript segments"
    else:
        raise ValueError("Unsupported file type")

    if not records:
        raise ValueError("No chunks were generated")

    material_id = save_material(title, file_name, file_type, records)
    return {
        "material_id": material_id,
        "file_type": file_type,
        "units_processed": len(units),
        "unit": unit_name,
        "pages_processed": len(units),
        "chunks_created": len(records),
    }