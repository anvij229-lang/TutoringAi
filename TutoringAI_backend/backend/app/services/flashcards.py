import random
import uuid

from app.database.db import get_connection
from app.services.learner_model import WEAK_MAX
from app.services.llm import chat
from app.services.rag import retrieve_chunks
from app.services.selection import resolve_selection
from app.services.topics import balanced_sample, get_topics_for
from app.utils.citations import with_file_name
from app.utils.json_utils import normalize_text, parse_json
from app.utils.prompts import FLASHCARD_PROMPT
from app.utils.citations import clean_source_label

MIN_CARDS = 4
MAX_CARDS = 15
MAX_TOPICS = 4


def chunk_label(chunk: dict) -> str:
    return chunk.get("label") or f"Page {chunk['page']}"


def weak_topic_ids(user_id: str, material_ids: list) -> list:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT m.topic_id FROM mastery m JOIN topics t ON t.id = m.topic_id "
                "WHERE m.user_id = %s AND t.material_id = ANY(%s::uuid[]) "
                "AND m.mastery_score <= %s ORDER BY m.mastery_score",
                (user_id, material_ids, WEAK_MAX),
            )
            return [str(row[0]) for row in cur.fetchall()]


def select_topics(ids: list, topic_id, user_id: str, weak_only: bool, count: int):
    topics = get_topics_for(ids)
    by_id = {t["id"]: t for t in topics}

    if topic_id:
        if topic_id not in by_id:
            raise LookupError("Topic not found in the selected materials")
        return [by_id[topic_id]]

    if weak_only:
        weak = [by_id[i] for i in weak_topic_ids(user_id, ids) if i in by_id]
        if not weak:
            raise ValueError(
                "No weak topics yet in the selected materials. Take a quiz first, or choose a topic."
            )
        return weak[:MAX_TOPICS]

    return balanced_sample(topics, min(len(topics), MAX_TOPICS, count), True)


def build_context(topics: list) -> str:
    per_topic = 6 if len(topics) == 1 else 4
    blocks = []
    for topic in topics:
        query = f"{topic['name']}. {topic['description'] or ''}"
        for chunk in retrieve_chunks(topic["material_id"], query, top_k=per_topic):
            blocks.append(
                f"[Topic: {topic['label']} | {chunk_label(chunk)}]\n{chunk['text'][:700]}"
            )
    return "\n\n".join(blocks)


def validate_card(item, topic_names: list):
    if not isinstance(item, dict):
        return None

    front = normalize_text(item.get("front"))
    back = normalize_text(item.get("back"))
    if not front or not back or len(front) > 200 or len(back) > 600:
        return None

    topic = normalize_text(item.get("topic"))
    lowered = {normalize_text(name).lower(): name for name in topic_names}
    topic = lowered.get(topic.lower(), topic_names[0])

    source = clean_source_label(item.get("source"))
    return {"topic": topic, "front": front, "back": back, "source": source}

def generate_flashcards(
    material_ids,
    topic_id,
    number_of_cards: int,
    user_id: str = "demo",
    weak_only: bool = False,
):
    if not MIN_CARDS <= number_of_cards <= MAX_CARDS:
        raise ValueError(f"number_of_cards must be between {MIN_CARDS} and {MAX_CARDS}")

    try:
        if topic_id:
            topic_id = str(uuid.UUID(topic_id))
    except ValueError:
        raise ValueError("Invalid topic_id")

    selection = resolve_selection(material_ids)
    ids = [item["id"] for item in selection]
    multi = len(ids) > 1

    topics = select_topics(ids, topic_id, user_id, weak_only, number_of_cards)
    context = build_context(topics)
    if not context.strip():
        raise ValueError("Not enough material to build flashcards")

    topic_names = [t["label"] for t in topics]
    by_label = {t["label"]: t for t in topics}

    user_prompt = (
        f"Number of cards: {number_of_cards}\n"
        f"Allowed topics: {', '.join(topic_names)}\n\n"
        f"Study material:\n{context}"
    )

    best = []
    for _ in range(2):
        try:
            data = parse_json(chat(FLASHCARD_PROMPT, user_prompt, temperature=0.3))
        except ValueError:
            continue

        raw = data.get("cards", []) if isinstance(data, dict) else []
        seen = set()
        valid = []
        for item in raw:
            card = validate_card(item, topic_names)
            if card is None or card["front"].lower() in seen:
                continue
            seen.add(card["front"].lower())
            valid.append(card)

        if len(valid) > len(best):
            best = valid
        if len(best) >= number_of_cards:
            break

    if not best:
        raise RuntimeError("Could not generate valid flashcards. Please try again.")
    cards = best[:number_of_cards]

    if topic_id:
        mode = "topic"
    elif weak_only:
        mode = "weak"
    else:
        mode = "mixed"

    output = []
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO flashcard_sets (material_id, material_ids, topic_id, user_id, mode) "
                "VALUES (%s::uuid, %s::uuid[], %s::uuid, %s, %s) RETURNING id",
                (ids[0], ids, topic_id, user_id, mode),
            )
            set_id = str(cur.fetchone()[0])

            for position, card in enumerate(cards):
                topic = by_label[card["topic"]]
                source = with_file_name(card["source"], topic["material_title"], multi)
                cur.execute(
                    "INSERT INTO flashcards "
                    "(set_id, topic_id, position, front, back, source_label) "
                    "VALUES (%s::uuid, %s::uuid, %s, %s, %s, %s) RETURNING id",
                    (set_id, topic["id"], position, card["front"], card["back"], source),
                )
                output.append(
                    {
                        "card_id": str(cur.fetchone()[0]),
                        "topic": topic["name"],
                        "topic_id": topic["id"],
                        "material_title": topic["material_title"],
                        "front": card["front"],
                        "back": card["back"],
                        "source": source,
                    }
                )
        conn.commit()

    return {
        "set_id": set_id,
        "material_id": ids[0],
        "material_ids": ids,
        "mode": mode,
        "topics": topic_names,
        "cards": output,
    }

def get_flashcards(material_ids, topic_id=None, user_id: str = "demo"):
    try:
        if topic_id:
            topic_id = str(uuid.UUID(topic_id))
    except ValueError:
        raise ValueError("Invalid topic_id")

    ids = [item["id"] for item in resolve_selection(material_ids)]

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, mode, created_at FROM flashcard_sets "
                "WHERE material_ids = %s::uuid[] AND user_id = %s "
                "AND (%s::uuid IS NULL OR topic_id = %s::uuid) "
                "ORDER BY created_at DESC LIMIT 1",
                (ids, user_id, topic_id, topic_id),
            )
            row = cur.fetchone()
            if row is None:
                raise LookupError("No flashcards yet for this selection. Generate a set first.")
            set_id, mode, created_at = row

            cur.execute(
                "SELECT c.id, c.front, c.back, c.source_label, t.id, t.name, mt.title, r.known "
                "FROM flashcards c "
                "LEFT JOIN topics t ON t.id = c.topic_id "
                "LEFT JOIN materials mt ON mt.id = t.material_id "
                "LEFT JOIN flashcard_reviews r ON r.card_id = c.id AND r.user_id = %s "
                "WHERE c.set_id = %s ORDER BY c.position",
                (user_id, set_id),
            )
            rows = cur.fetchall()

    return {
        "set_id": str(set_id),
        "material_id": ids[0],
        "material_ids": ids,
        "mode": mode,
        "created_at": created_at.isoformat(),
        "cards": [
            {
                "card_id": str(r[0]),
                "front": r[1],
                "back": r[2],
                "source": r[3],
                "topic_id": str(r[4]) if r[4] else None,
                "topic": r[5],
                "material_title": r[6],
                "known": r[7],
            }
            for r in rows
        ],
    }


def record_review(card_id: str, known: bool, user_id: str = "demo"):
    try:
        uuid.UUID(card_id)
    except ValueError:
        raise ValueError("Invalid card_id")

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT set_id FROM flashcards WHERE id = %s::uuid", (card_id,))
            row = cur.fetchone()
            if row is None:
                raise LookupError("Card not found")
            set_id = row[0]

            cur.execute(
                "INSERT INTO flashcard_reviews (user_id, card_id, known, reviewed_at) "
                "VALUES (%s, %s::uuid, %s, now()) "
                "ON CONFLICT (user_id, card_id) DO UPDATE SET "
                "known = EXCLUDED.known, reviewed_at = now()",
                (user_id, card_id, known),
            )

            cur.execute(
                "SELECT count(*), count(*) FILTER (WHERE r.known) "
                "FROM flashcards c "
                "LEFT JOIN flashcard_reviews r ON r.card_id = c.id AND r.user_id = %s "
                "WHERE c.set_id = %s",
                (user_id, set_id),
            )
            total, known_count = cur.fetchone()
        conn.commit()

    return {
        "card_id": card_id,
        "known": known,
        "set_progress": {"known": known_count, "total": total},
    }