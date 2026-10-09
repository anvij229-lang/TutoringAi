import uuid

from app.database.db import get_connection

WEAK_BELOW = 60
STRONG_FROM = 80


def topic_status(accuracy: int) -> str:
    if accuracy < WEAK_BELOW:
        return "weak"
    if accuracy >= STRONG_FROM:
        return "strong"
    return "developing"


def build_recommendation(weak_topics: list, developing_topics: list, missed_pages: set) -> str:
    if weak_topics:
        text = f"Review {', '.join(weak_topics)} before attempting a harder quiz."
        if missed_pages:
            pages = ", ".join(str(p) for p in sorted(missed_pages))
            text += f" Revisit page(s) {pages}."
        return text
    if developing_topics:
        return f"Good progress. Practice {', '.join(developing_topics)} to strengthen your understanding."
    return "Excellent work! Try a harder quiz or move on to the next topic."


def submit_quiz(quiz_id: str, answers: list, user_id: str = "demo"):
    try:
        uuid.UUID(quiz_id)
    except ValueError:
        raise ValueError("Invalid quiz_id")

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM quizzes WHERE id = %s::uuid", (quiz_id,))
            if cur.fetchone() is None:
                raise LookupError("Quiz not found")

            cur.execute(
                "SELECT q.id, q.question, q.options, q.correct_answer, q.explanation, "
                "q.source_page, q.topic_id, t.name "
                "FROM questions q LEFT JOIN topics t ON t.id = q.topic_id "
                "WHERE q.quiz_id = %s::uuid ORDER BY q.position",
                (quiz_id,),
            )
            rows = cur.fetchall()
            if not rows:
                raise LookupError("This quiz has no questions")

            valid_ids = {str(row[0]) for row in rows}
            submitted = {}
            for item in answers:
                question_id = str(item.get("question_id", "")).strip().lower()
                if question_id not in valid_ids:
                    raise ValueError("An answer refers to a question that is not in this quiz")
                submitted[question_id] = str(item.get("answer", "")).strip().upper()[:1]

            results = []
            topic_stats = {}
            missed_pages = set()
            correct_count = 0

            for row in rows:
                question_id = str(row[0])
                correct_answer = row[3]
                user_answer = submitted.get(question_id, "")
                is_correct = user_answer == correct_answer
                topic_name = row[7] or "General"

                stats = topic_stats.setdefault(
                    topic_name, {"topic_id": row[6], "correct": 0, "total": 0}
                )
                stats["total"] += 1
                if is_correct:
                    stats["correct"] += 1
                    correct_count += 1
                elif row[5]:
                    missed_pages.add(row[5])

                results.append(
                    {
                        "question_id": question_id,
                        "topic": topic_name,
                        "question": row[1],
                        "options": row[2],
                        "your_answer": user_answer or None,
                        "correct_answer": correct_answer,
                        "is_correct": is_correct,
                        "explanation": row[4],
                        "source_page": row[5],
                    }
                )

            total = len(rows)
            score = round(correct_count * 100 / total)

            breakdown = []
            weak_topics = []
            developing_topics = []
            strong_topics = []
            for name, stats in topic_stats.items():
                accuracy = round(stats["correct"] * 100 / stats["total"])
                status = topic_status(accuracy)
                if status == "weak":
                    weak_topics.append(name)
                elif status == "strong":
                    strong_topics.append(name)
                else:
                    developing_topics.append(name)
                breakdown.append(
                    {
                        "topic": name,
                        "topic_id": str(stats["topic_id"]) if stats["topic_id"] else None,
                        "correct": stats["correct"],
                        "total": stats["total"],
                        "accuracy": accuracy,
                        "status": status,
                    }
                )

            cur.execute(
                "INSERT INTO quiz_attempts "
                "(quiz_id, user_id, correct_count, total_questions, score_percent) "
                "VALUES (%s::uuid, %s, %s, %s, %s) RETURNING id",
                (quiz_id, user_id, correct_count, total, score),
            )
            attempt_id = str(cur.fetchone()[0])

            cur.executemany(
                "INSERT INTO attempt_answers "
                "(attempt_id, question_id, topic_id, user_answer, is_correct) "
                "VALUES (%s::uuid, %s::uuid, %s::uuid, %s, %s)",
                [
                    (
                        attempt_id,
                        row[0],
                        row[6],
                        submitted.get(str(row[0]), "") or None,
                        submitted.get(str(row[0]), "") == row[3],
                    )
                    for row in rows
                ],
            )
        conn.commit()

    return {
        "attempt_id": attempt_id,
        "quiz_id": quiz_id,
        "score": score,
        "correct": correct_count,
        "total": total,
        "topic_breakdown": breakdown,
        "strong_topics": strong_topics,
        "weak_topics": weak_topics,
        "recommendation": build_recommendation(weak_topics, developing_topics, missed_pages),
        "results": results,
    }