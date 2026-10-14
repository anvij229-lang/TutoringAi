import json
import random
import re
import uuid

from app.database.db import get_connection
from app.services.llm import chat
from app.services.rag import retrieve_chunks
from app.services.selection import resolve_selection
from app.services.topics import balanced_sample, get_topics_for
from app.utils.citations import with_file_name
from app.utils.json_utils import parse_json
from app.utils.prompts import QUIZ_PROMPT
from app.services.learner_model import auto_difficulty
from app.utils.citations import clean_source_label

VALID_DIFFICULTIES = ("easy", "medium", "hard")
MIN_QUESTIONS = 3
MAX_QUESTIONS = 10
MAX_TOPICS_PER_QUIZ = 4
LETTERS = ["A", "B", "C", "D"]


def select_topics(ids: list, topic_id, number_of_questions: int):
    topics = get_topics_for(ids)
    if topic_id:
        chosen = [t for t in topics if t["id"] == topic_id]
        if not chosen:
            raise LookupError("Topic not found in the selected materials")
        return chosen
    limit = min(len(topics), MAX_TOPICS_PER_QUIZ, number_of_questions)
    return balanced_sample(topics, limit, True)


def build_context(topics: list) -> str:
    per_topic = 6 if len(topics) == 1 else 3
    blocks = []
    for topic in topics:
        query = f"{topic['name']}. {topic['description'] or ''}"
        for chunk in retrieve_chunks(topic["material_id"], query, top_k=per_topic):
            blocks.append(f"[Topic: {topic['label']} | {chunk['label']}]\n{chunk['text']}")
    return "\n\n".join(blocks)


def clean_option(text) -> str:
    return re.sub(r"^[A-Da-d][\).:]\s+", "", str(text).strip())


def validate_question(item, topic_names: list):
    if not isinstance(item, dict):
        return None

    question = str(item.get("question", "")).strip()
    options = item.get("options")
    answer = str(item.get("answer", "")).strip().upper()[:1]

    if not question or not isinstance(options, list) or len(options) != 4:
        return None
    if answer not in LETTERS:
        return None

    options = [clean_option(o) for o in options]
    if any(not o for o in options):
        return None
    if len({o.lower() for o in options}) != 4:
        return None

    topic = str(item.get("topic", "")).strip()
    if topic not in topic_names:
        lowered = {n.lower(): n for n in topic_names}
        topic = lowered.get(topic.lower(), topic_names[0])

    source = clean_source_label(item.get("source"))
    digits = re.search(r"\d+", source) if source and not source.startswith("Video") else None
    page = int(digits.group()) if digits else None

    return {
        "topic": topic,
        "question": question,
        "options": options,
        "answer": answer,
        "explanation": str(item.get("explanation", "")).strip(),
        "source": source or None,
        "page": page,
    }


def generate_quiz(material_ids, topic_id, difficulty: str, number_of_questions: int, user_id: str = "demo"):
    difficulty = difficulty.strip().lower()
    if difficulty != "auto" and difficulty not in VALID_DIFFICULTIES:
        raise ValueError("difficulty must be auto, easy, medium or hard")
    if not MIN_QUESTIONS <= number_of_questions <= MAX_QUESTIONS:
        raise ValueError(
            f"number_of_questions must be between {MIN_QUESTIONS} and {MAX_QUESTIONS}"
        )

    try:
        if topic_id:
            topic_id = str(uuid.UUID(topic_id))
    except ValueError:
        raise ValueError("Invalid topic_id")

    selection = resolve_selection(material_ids)
    ids = [item["id"] for item in selection]
    multi = len(ids) > 1
    materials = [{"id": item["id"], "title": item["title"]} for item in selection]

    topics = select_topics(ids, topic_id, number_of_questions)
    adaptive = difficulty == "auto"
    if adaptive:
        difficulty = auto_difficulty(user_id, [t["id"] for t in topics])

    context = build_context(topics)
    if not context.strip():
        raise ValueError("Not enough material to build a quiz")

    topic_names = [t["label"] for t in topics]
    by_label = {t["label"]: t for t in topics}

    user_prompt = (
        f"Difficulty: {difficulty}\n"
        f"Number of questions: {number_of_questions}\n"
        f"Allowed topics: {', '.join(topic_names)}\n\n"
        f"Study material:\n{context}"
    )

    best = []
    for _ in range(2):
        try:
            reply = chat(QUIZ_PROMPT, user_prompt, temperature=0.4)
            data = parse_json(reply)
        except ValueError:
            continue
        raw = data.get("questions", []) if isinstance(data, dict) else []
        valid = [q for q in (validate_question(i, topic_names) for i in raw) if q]
        if len(valid) > len(best):
            best = valid
        if len(best) >= number_of_questions:
            break

    if not best:
        raise RuntimeError("Could not generate a valid quiz. Please try again.")
    questions = best[:number_of_questions]

    output = []
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO quizzes (material_id, material_ids, topic_id, difficulty) "
                "VALUES (%s::uuid, %s::uuid[], %s::uuid, %s) RETURNING id",
                (ids[0], ids, topic_id, difficulty),
            )
            quiz_id = str(cur.fetchone()[0])

            for position, q in enumerate(questions):
                topic = by_label[q["topic"]]
                source = with_file_name(q.get("source"), topic["material_title"], multi)
                cur.execute(
                    "INSERT INTO questions "
                    "(quiz_id, topic_id, position, question, question_type, difficulty, "
                    "options, correct_answer, explanation, source_page, source_label) "
                    "VALUES (%s::uuid, %s::uuid, %s, %s, 'mcq', %s, %s::jsonb, %s, %s, %s, %s) "
                    "RETURNING id",
                    (
                        quiz_id,
                        topic["id"],
                        position,
                        q["question"],
                        difficulty,
                        json.dumps(q["options"]),
                        q["answer"],
                        q["explanation"],
                        q["page"],
                        source,
                    ),
                )
                output.append(
                    {
                        "question_id": str(cur.fetchone()[0]),
                        "topic": q["topic"],
                        "material_title": topic["material_title"],
                        "question": q["question"],
                        "options": q["options"],
                    }
                )
        conn.commit()

    return {
        "quiz_id": quiz_id,
        "material_id": ids[0],
        "material_ids": ids,
        "materials": materials,
        "adaptive": adaptive,
        "difficulty": difficulty,
        "topics": topic_names,
        "questions": output,
    }