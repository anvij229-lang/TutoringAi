from app.database.db import get_connection
from app.services.evaluator import submit_quiz
from app.services.progress import get_progress
from app.services.quiz_generator import generate_quiz
from app.services.topics import get_or_detect_topics

MATERIAL_ID = "2e41b585-8ce7-418c-9c1f-ccbc5997c155"
USER_ID = "demo"


def correct_letters(quiz_id):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, correct_answer FROM questions WHERE quiz_id = %s::uuid",
                (quiz_id,),
            )
            return {str(row[0]): row[1] for row in cur.fetchall()}


def take_quiz(topic_id, answer_correctly):
    quiz = generate_quiz(MATERIAL_ID, topic_id, "auto", 5, USER_ID)
    correct = correct_letters(quiz["quiz_id"])
    answers = []
    for question in quiz["questions"]:
        right = correct[question["question_id"]]
        if answer_correctly:
            letter = right
        else:
            letter = next(l for l in "ABCD" if l != right)
        answers.append({"question_id": question["question_id"], "answer": letter})
    result = submit_quiz(quiz["quiz_id"], answers, USER_ID)
    print(
        f"   difficulty={quiz['difficulty']} adaptive={quiz['adaptive']} "
        f"questions={len(quiz['questions'])} score={result['score']}%"
    )
    for change in result["mastery_changes"]:
        print(
            f"   {change['topic']}: {change['before']} -> {change['after']} "
            f"({change['status']}), next quiz = {change['next_difficulty']}"
        )
    return result


topics = get_or_detect_topics(MATERIAL_ID)
topic = topics[0]
print("Topic under test:", topic["name"])

print("\n1) First quiz, answering everything WRONG")
take_quiz(topic["id"], False)

print("\n2) Second quiz, should be EASY now, answering everything RIGHT")
take_quiz(topic["id"], True)

print("\n3) Progress snapshot")
progress = get_progress(USER_ID, MATERIAL_ID)
print("   overall mastery:", progress["overall_mastery"])
for item in progress["topics"]:
    print(f"   {item['name']}: mastery={item['mastery']} status={item['status']}")
print("   recommendation:", progress["recommendation"]["message"])
print("   trend entries:", len(progress["mastery_trend"]))