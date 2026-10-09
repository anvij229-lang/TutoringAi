from app.services.evaluator import submit_quiz
from app.services.quiz_generator import generate_quiz
from app.services.topics import get_or_detect_topics

MATERIAL_ID = "18475e52-416f-4d69-9448-2a71207d913c"

topics = get_or_detect_topics(MATERIAL_ID)
print("TOPICS:")
for topic in topics:
    print("-", topic["name"], "|", topic["id"])

quiz = generate_quiz(MATERIAL_ID, None, "medium", 5)
print("\nQUIZ ID:", quiz["quiz_id"])
for number, question in enumerate(quiz["questions"], start=1):
    print(f"\nQ{number} [{question['topic']}] {question['question']}")
    for letter, option in zip("ABCD", question["options"]):
        print(f"   {letter}) {option}")

answers = [{"question_id": q["question_id"], "answer": "A"} for q in quiz["questions"]]
result = submit_quiz(quiz["quiz_id"], answers, "demo")

print("\nSCORE:", result["score"], "%")
print("WEAK:", result["weak_topics"])
print("STRONG:", result["strong_topics"])
print("RECOMMENDATION:", result["recommendation"])
for item in result["results"]:
    mark = "OK " if item["is_correct"] else "BAD"
    print(f"[{mark}] correct={item['correct_answer']} page={item['source_page']} | {item['question'][:70]}")