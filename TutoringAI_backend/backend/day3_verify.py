from app.database.db import get_connection
from app.services.evaluator import submit_quiz
from app.services.quiz_generator import generate_quiz

MATERIAL_ID = "18475e52-416f-4d69-9448-2a71207d913c"

quiz = generate_quiz(MATERIAL_ID, None, "medium", 5)

with get_connection() as conn:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, correct_answer FROM questions WHERE quiz_id = %s::uuid",
            (quiz["quiz_id"],),
        )
        correct = {str(row[0]): row[1] for row in cur.fetchall()}

answers = [
    {"question_id": q["question_id"], "answer": correct[q["question_id"]]}
    for q in quiz["questions"]
]
result = submit_quiz(quiz["quiz_id"], answers, "demo")
print("SCORE:", result["score"], "| WEAK:", result["weak_topics"], "| STRONG:", result["strong_topics"])