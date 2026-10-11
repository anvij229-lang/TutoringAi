from app.database.db import get_connection

START_MASTERY = 50
STEP = 10
WEAK_MAX = 40
DEVELOPING_MAX = 70


def clamp(value: int) -> int:
    return max(0, min(100, value))


def mastery_status(score: int) -> str:
    if score <= WEAK_MAX:
        return "weak"
    if score <= DEVELOPING_MAX:
        return "developing"
    return "strong"


def difficulty_for(score: float) -> str:
    if score <= WEAK_MAX:
        return "easy"
    if score <= DEVELOPING_MAX:
        return "medium"
    return "hard"


def auto_difficulty(user_id: str, topic_ids: list) -> str:
    if not topic_ids:
        return "medium"
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT topic_id, mastery_score FROM mastery "
                "WHERE user_id = %s AND topic_id = ANY(%s::uuid[])",
                (user_id, topic_ids),
            )
            known = {str(row[0]): row[1] for row in cur.fetchall()}
    scores = [known.get(str(topic_id), START_MASTERY) for topic_id in topic_ids]
    return difficulty_for(sum(scores) / len(scores))


def answers_for_mastery(rows, submitted: dict) -> list:
    answered = []
    for row in rows:
        user_answer = submitted.get(str(row[0]), "")
        if not user_answer:
            continue
        answered.append((row[6], row[7] or "General", user_answer == row[3]))
    return answered


def update_mastery(cur, user_id: str, attempt_id: str, answered: list) -> list:
    stats = {}
    for topic_id, topic_name, is_correct in answered:
        if topic_id is None:
            continue
        entry = stats.setdefault(
            str(topic_id), {"name": topic_name, "correct": 0, "total": 0}
        )
        entry["total"] += 1
        if is_correct:
            entry["correct"] += 1

    changes = []
    for topic_id, entry in stats.items():
        cur.execute(
            "SELECT mastery_score, questions_attempted, questions_correct "
            "FROM mastery WHERE user_id = %s AND topic_id = %s::uuid",
            (user_id, topic_id),
        )
        row = cur.fetchone()
        before, attempted, correct_total = row if row else (START_MASTERY, 0, 0)

        wrong = entry["total"] - entry["correct"]
        after = clamp(before + STEP * (entry["correct"] - wrong))

        cur.execute(
            "INSERT INTO mastery "
            "(user_id, topic_id, mastery_score, questions_attempted, questions_correct, last_updated) "
            "VALUES (%s, %s::uuid, %s, %s, %s, now()) "
            "ON CONFLICT (user_id, topic_id) DO UPDATE SET "
            "mastery_score = EXCLUDED.mastery_score, "
            "questions_attempted = EXCLUDED.questions_attempted, "
            "questions_correct = EXCLUDED.questions_correct, "
            "last_updated = now()",
            (
                user_id,
                topic_id,
                after,
                attempted + entry["total"],
                correct_total + entry["correct"],
            ),
        )
        cur.execute(
            "INSERT INTO mastery_history "
            "(user_id, topic_id, attempt_id, mastery_before, mastery_after) "
            "VALUES (%s, %s::uuid, %s::uuid, %s, %s)",
            (user_id, topic_id, attempt_id, before, after),
        )

        changes.append(
            {
                "topic": entry["name"],
                "topic_id": topic_id,
                "before": before,
                "after": after,
                "change": after - before,
                "status": mastery_status(after),
                "next_difficulty": difficulty_for(after),
            }
        )
    return changes