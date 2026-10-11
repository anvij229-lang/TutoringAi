from app.database.db import get_connection
from app.services.learner_model import START_MASTERY, difficulty_for, mastery_status


def recommend_next(topics: list) -> dict:
    started = [t for t in topics if t["mastery"] is not None]

    needs_work = sorted(
        [t for t in started if t["status"] in ("weak", "developing")],
        key=lambda t: t["mastery"],
    )
    if needs_work:
        topic = needs_work[0]
        difficulty = topic["recommended_difficulty"]
        return {
            "type": "review",
            "topic_id": topic["topic_id"],
            "topic": topic["name"],
            "difficulty": difficulty,
            "message": f"Review {topic['name']}, then take a {difficulty} quiz on it.",
        }

    not_started = [t for t in topics if t["mastery"] is None]
    if not_started:
        topic = not_started[0]
        return {
            "type": "start",
            "topic_id": topic["topic_id"],
            "topic": topic["name"],
            "difficulty": "medium",
            "message": f"Start learning {topic['name']} with a medium quiz.",
        }

    if started:
        topic = min(started, key=lambda t: t["mastery"])
        return {
            "type": "challenge",
            "topic_id": topic["topic_id"],
            "topic": topic["name"],
            "difficulty": "hard",
            "message": f"Great progress! Challenge yourself with a hard quiz on {topic['name']}.",
        }

    return {
        "type": "none",
        "topic_id": None,
        "topic": None,
        "difficulty": None,
        "message": "Upload study material and take your first quiz to see recommendations.",
    }


def get_progress(user_id: str, material_id: str | None = None) -> dict:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT t.id, t.name, t.material_id, m.mastery_score, "
                "m.questions_attempted, m.questions_correct, m.last_updated "
                "FROM topics t "
                "LEFT JOIN mastery m ON m.topic_id = t.id AND m.user_id = %s "
                "WHERE (%s::uuid IS NULL OR t.material_id = %s::uuid) "
                "ORDER BY t.name",
                (user_id, material_id, material_id),
            )
            topic_rows = cur.fetchall()

            cur.execute(
                "SELECT a.id, a.score_percent, a.correct_count, a.total_questions, "
                "a.created_at, qz.difficulty, mt.title, t.name "
                "FROM quiz_attempts a "
                "JOIN quizzes qz ON qz.id = a.quiz_id "
                "JOIN materials mt ON mt.id = qz.material_id "
                "LEFT JOIN topics t ON t.id = qz.topic_id "
                "WHERE a.user_id = %s AND (%s::uuid IS NULL OR qz.material_id = %s::uuid) "
                "ORDER BY a.created_at DESC LIMIT 10",
                (user_id, material_id, material_id),
            )
            attempt_rows = cur.fetchall()

            cur.execute(
                "SELECT h.topic_id, t.name, h.mastery_before, h.mastery_after, h.created_at "
                "FROM mastery_history h JOIN topics t ON t.id = h.topic_id "
                "WHERE h.user_id = %s AND (%s::uuid IS NULL OR t.material_id = %s::uuid) "
                "ORDER BY h.created_at DESC LIMIT 30",
                (user_id, material_id, material_id),
            )
            history_rows = cur.fetchall()

    topics = []
    for topic_id, name, topic_material, score, attempted, correct, updated in topic_rows:
        attempted = attempted or 0
        correct = correct or 0
        started = score is not None
        topics.append(
            {
                "topic_id": str(topic_id),
                "name": name,
                "material_id": str(topic_material),
                "mastery": score if started else None,
                "status": mastery_status(score) if started else "not_started",
                "questions_attempted": attempted,
                "questions_correct": correct,
                "accuracy": round(correct * 100 / attempted) if attempted else None,
                "recommended_difficulty": difficulty_for(score if started else START_MASTERY),
                "last_updated": updated.isoformat() if updated else None,
            }
        )

    started_topics = [t for t in topics if t["mastery"] is not None]
    overall = (
        round(sum(t["mastery"] for t in started_topics) / len(started_topics))
        if started_topics
        else 0
    )

    recent_attempts = [
        {
            "attempt_id": str(row[0]),
            "score": row[1],
            "correct": row[2],
            "total": row[3],
            "taken_at": row[4].isoformat(),
            "difficulty": row[5],
            "material": row[6],
            "topic": row[7] or "Mixed topics",
        }
        for row in attempt_rows
    ]

    mastery_trend = [
        {
            "topic_id": str(row[0]),
            "topic": row[1],
            "before": row[2],
            "after": row[3],
            "at": row[4].isoformat(),
        }
        for row in reversed(history_rows)
    ]

    return {
        "user_id": user_id,
        "overall_mastery": overall,
        "topics_started": len(started_topics),
        "topics": topics,
        "weak_topics": [t["name"] for t in started_topics if t["status"] == "weak"],
        "strong_topics": [t["name"] for t in started_topics if t["status"] == "strong"],
        "recommendation": recommend_next(topics),
        "recent_attempts": recent_attempts,
        "mastery_trend": mastery_trend,
    }