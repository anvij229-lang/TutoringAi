from app.services.flashcards import generate_flashcards
from app.services.mindmap import generate_mindmap
from app.services.quiz_generator import generate_quiz
from app.services.rag import answer_question
from app.services.topics import get_topics_for

A = "895ef889-2936-47f1-a919-f7975bb9de8a"
B = "2e41b585-8ce7-418c-9c1f-ccbc5997c155"
QUESTION_ONLY_B_ANSWERS = "What is adaptive learning"

print("TOPICS (A + B)")
for topic in get_topics_for([A, B]):
    print(" -", topic["label"], "|", topic["material_title"])

print("\nONLY A selected, asking B's question (must be refused)")
result = answer_question([A], QUESTION_ONLY_B_ANSWERS)
print(" grounded:", result["grounded"])

print("\nA + B selected, same question (must answer from B)")
result = answer_question([A, B], QUESTION_ONLY_B_ANSWERS)
print(" grounded:", result["grounded"])
print(" citations:", [source["citation"] for source in result["sources"]])

print("\nMIXED QUIZ over A + B")
quiz = generate_quiz([A, B], None, "medium", 6)
for question in quiz["questions"]:
    print(" -", question["material_title"], "|", question["topic"], "|", question["question"][:60])

print("\nMIXED FLASHCARDS over A + B")
deck = generate_flashcards([A, B], None, 8)
for card in deck["cards"]:
    print(" -", card["source"], "|", card["front"][:60])

print("\nMIND MAP over A + B")
mind_map = generate_mindmap([A, B], None, True)
print(" scope:", mind_map["scope"], "| nodes:", mind_map["node_count"])
print(mind_map["markdown"])