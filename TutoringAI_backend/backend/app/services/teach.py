import uuid

from app.database.db import get_connection
from app.services.learner_model import START_MASTERY, WEAK_MAX, DEVELOPING_MAX
from app.services.llm import chat
from app.services.rag import NOT_COVERED_MSG, retrieve_chunks
from app.utils.prompts import TEACH_PROMPT


def level_for(score: int) -> str:
    if score <= WEAK_MAX:
        return "beginner"
    if score <= DEVELOPING_MAX:
        return "intermediate"
    return "advanced"


def teach_topic(topic_id: str, user_id: str = "demo"):
    try:
        uuid.UUID(topic_id)
    except ValueError:
        raise ValueError("Invalid topic_id")

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT t.name, t.description, t.material_id, m.mastery_score "
                "FROM topics t "
                "LEFT JOIN mastery m ON m.topic_id = t.id AND m.user_id = %s "
                "WHERE t.id = %s::uuid",
                (user_id, topic_id),
            )
            row = cur.fetchone()
    if row is None:
        raise LookupError("Topic not found")

    name, description, material_id, score = row
    level = level_for(START_MASTERY if score is None else score)

    chunks = retrieve_chunks(str(material_id), f"{name}. {description or ''}", top_k=6)
    if not chunks:
        return {
            "topic": name,
            "topic_id": topic_id,
            "level": level,
            "lesson": NOT_COVERED_MSG,
            "grounded": False,
            "sources": [],
        }

    context = "\n\n".join(f"[{c['label']}]\n{c['text']}" for c in chunks)
    prompt = f"Topic: {name}\nStudent level: {level}\n\nStudy material:\n{context}"
    reply = chat(TEACH_PROMPT, prompt, temperature=0.3)

    if reply.upper().startswith("NOT_COVERED"):
        return {
            "topic": name,
            "topic_id": topic_id,
            "level": level,
            "lesson": NOT_COVERED_MSG,
            "grounded": False,
            "sources": [],
        }

    return {
        "topic": name,
        "topic_id": topic_id,
        "level": level,
        "lesson": reply,
        "grounded": True,
        "sources": chunks,
    }