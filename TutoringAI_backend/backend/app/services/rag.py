import os
import re
from app.database.db import get_connection
from app.services.embeddings import create_embedding
from app.services.llm import chat
from app.services.selection import resolve_selection, safe_title
from app.utils.citations import source_label
from app.utils.prompts import GROUNDING_PROMPT

NOT_COVERED_MSG = "This topic isn't covered in your uploaded material."
MAX_QUESTION_LENGTH = 500


def material_exists(material_id: str) -> bool:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM materials WHERE id = %s::uuid", (material_id,))
            return cur.fetchone() is not None

def clean_query(q: str) -> str:
    return re.sub(r"^which page (covers|describes|lists|says)\s+", "", q, flags=re.I)


def retrieve_chunks(material_ids, question: str, top_k: int = 5):
    ids = [material_ids] if isinstance(material_ids, str) else list(material_ids)
    embedding = create_embedding(question)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT content, page_number, start_seconds, file_type, similarity, "
                "material_id, material_title "
                "FROM match_chunks_multi(%s::vector, %s::uuid[], %s)",
                (str(embedding), ids, top_k),
            )
            rows = cur.fetchall()
    return [
        {
            "text": row[0],
            "page": row[1],
            "start_seconds": row[2],
            "file_type": row[3],
            "label": source_label(row[3], row[1], row[2]),
            "similarity": float(row[4]),
            "material_id": str(row[5]),
            "material_title": safe_title(row[6]),
        }
        for row in rows
    ]


def format_passage(chunk: dict, multi: bool) -> str:
    if multi:
        return f"[{chunk['material_title']} | {chunk['label']}]\n{chunk['text']}"
    return f"[{chunk['label']}]\n{chunk['text']}"


def answer_question(material_ids, question: str):
    if len(question) > MAX_QUESTION_LENGTH:
        raise ValueError(f"Question is too long (max {MAX_QUESTION_LENGTH} characters)")

    selection = resolve_selection(material_ids)
    ids = [item["id"] for item in selection]
    multi = len(ids) > 1
    materials = [{"id": item["id"], "title": item["title"]} for item in selection]

    threshold = float(os.getenv("SIMILARITY_THRESHOLD", "0.30"))
    chunks = retrieve_chunks(ids, question, top_k=8 if multi else 5)
    relevant = [chunk for chunk in chunks if chunk["similarity"] >= threshold]

    if not relevant:
        return {"answer": NOT_COVERED_MSG, "grounded": False, "sources": [], "materials": materials}

    for chunk in relevant:
        chunk["citation"] = (
            f"{chunk['material_title']}, {chunk['label']}" if multi else chunk["label"]
        )

    context = "\n\n".join(format_passage(chunk, multi) for chunk in relevant)
    answer = chat(GROUNDING_PROMPT, f"Context:\n{context}\n\nQuestion: {question}")

    if answer.upper().startswith("NOT_COVERED"):
        return {"answer": NOT_COVERED_MSG, "grounded": False, "sources": [], "materials": materials}

    return {"answer": answer, "grounded": True, "sources": relevant, "materials": materials}