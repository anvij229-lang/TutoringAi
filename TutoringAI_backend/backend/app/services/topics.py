import uuid

from app.database.db import get_connection
from app.services.llm import chat
from app.services.rag import material_exists
from app.utils.json_utils import parse_json
from app.utils.prompts import TOPIC_PROMPT

MAX_CONTEXT_CHARS = 12000


def get_topics(material_id: str):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, name, description FROM topics "
                "WHERE material_id = %s::uuid ORDER BY name",
                (material_id,),
            )
            rows = cur.fetchall()
    return [{"id": str(r[0]), "name": r[1], "description": r[2]} for r in rows]


def sample_material_text(material_id: str) -> str:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT content, page_number FROM chunks "
                "WHERE material_id = %s::uuid ORDER BY page_number, chunk_index",
                (material_id,),
            )
            rows = cur.fetchall()
    if not rows:
        return ""
    step = max(1, len(rows) // 25)
    sampled = rows[::step][:25]
    parts = [f"[Page {r[1]}] {r[0][:500]}" for r in sampled]
    return "\n\n".join(parts)[:MAX_CONTEXT_CHARS]


def detect_topics(material_id: str):
    text = sample_material_text(material_id)
    if not text:
        raise LookupError("No content found for this material")

    reply = chat(TOPIC_PROMPT, f"Study material:\n{text}")
    data = parse_json(reply)
    items = data.get("topics", []) if isinstance(data, dict) else []

    seen = set()
    cleaned = []
    for item in items:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        if not name or name.lower() in seen:
            continue
        seen.add(name.lower())
        description = str(item.get("description", "")).strip()
        cleaned.append((name[:80], description[:300]))

    if not cleaned:
        raise ValueError("No topics could be detected from this material")

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO topics (material_id, name, description) "
                "VALUES (%s::uuid, %s, %s) ON CONFLICT (material_id, name) DO NOTHING",
                [(material_id, name, description) for name, description in cleaned],
            )
        conn.commit()

    return get_topics(material_id)


def get_or_detect_topics(material_id: str):
    try:
        uuid.UUID(material_id)
    except ValueError:
        raise ValueError("Invalid material_id")
    if not material_exists(material_id):
        raise LookupError("Material not found")
    topics = get_topics(material_id)
    if topics:
        return topics
    return detect_topics(material_id)