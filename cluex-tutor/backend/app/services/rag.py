import os
import uuid
import re
from app.database.db import get_connection
from app.services.embeddings import create_embedding
from app.services.llm import chat
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


def retrieve_chunks(material_id: str, question: str, top_k: int = 5):
    """Return the top_k most similar chunks for a question."""
    embedding = create_embedding(question)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT content, page_number, similarity "
                "FROM match_chunks(%s::vector, %s::uuid, %s)",
                (str(embedding), material_id, top_k),
            )
            rows = cur.fetchall()
    return [
        {"text": r[0], "page": r[1], "similarity": float(r[2])}
        for r in rows
    ]


def answer_question(material_id: str, question: str):
    try:
        uuid.UUID(material_id)
    except ValueError:
        raise ValueError("Invalid material_id")

    if len(question) > MAX_QUESTION_LENGTH:
        raise ValueError(f"Question is too long (max {MAX_QUESTION_LENGTH} characters)")

    if not material_exists(material_id):
        raise LookupError("Material not found")

    threshold = float(os.getenv("SIMILARITY_THRESHOLD", "0.30"))
    chunks = retrieve_chunks(material_id, clean_query(question))
    print("similarities:", [round(c["similarity"], 3) for c in chunks])  # remove after tuning

    # Layer 1: similarity threshold
    relevant = [c for c in chunks if c["similarity"] >= threshold]
    if not relevant:
        return {"answer": NOT_COVERED_MSG, "grounded": False, "sources": [],
                "reason": "below_threshold"}

    # Build context with page labels
    context = "\n\n".join(f"[Page {c['page']}]\n{c['text']}" for c in relevant)
    answer = chat(GROUNDING_PROMPT, f"Context:\n{context}\n\nQuestion: {question}")

    # Layer 2: the LLM says the context doesn't answer it
    if answer.strip().lstrip("*_\"' `").upper().startswith("NOT_COVERED"):
        return {"answer": NOT_COVERED_MSG, "grounded": False, "sources": [],
                "reason": "llm_not_covered"}

    return {"answer": answer, "grounded": True, "sources": relevant, "reason": "answered"}


    return {"answer": answer, "grounded": True, "sources": relevant, "reason": "answered"}