import re
from app.services.rag import answer_question
from collections import Counter

MATERIAL_ID = "18475e52-416f-4d69-9448-2a71207d913c"

TESTS = [
    # ---------- Direct, covered ----------
    ("What are the three types of source material the study companion must unify into a knowledge base", True),
    ("Which three metrics must be reported on the team-built test set", True),
    ("How long should the demonstration video be, and where should it be hosted", True),
    ("What percentage of the evaluation score is for Personalization Effectiveness", True),
    ("What three question formats should generated quizzes and mock exams support", True),
    ("Which learner-model approaches does the brief give as examples", True),
    ("What percentage of the evaluation score is for Knowledge Base & Grounding", True),
    ("Which evaluation frameworks does the brief name for the retrieval and generation pipeline", True),
    ("What must each generated question be tagged with", True),
    ("How should the system handle new students with no history", True),
    ("Which course materials may teams use for their prototype", True),
    ("What does the post-assessment report need to identify", True),

    # ---------- Paraphrased ----------
    ("What kinds of content does the tool need to bring together in one cited collection", True),
    ("How should the retrieval and generation pipeline be scored, and on what measures", True),
    ("How heavily is the personalization criterion weighted in judging", True),
    ("How are learners with zero prior data supposed to be onboarded", True),
    ("Which kinds of problems should the exam generator be able to produce", True),
    ("What metadata should be attached to every question the system generates", True),

    # ---------- Which page covers X ----------
    ("Which page describes how question answer keys should be verified, for example by cross-model validation", True),
    ("Which page lists the optional enhancements, such as a course flow map or Hindi support", True),
    ("Which page lists the evaluation criteria and their weights", True),
    ("Which page covers the expected deliverables", True),
    ("Which page says unsupported queries should be declined or flagged in source grounding", True),

    # ---------- Out of scope (easy) ----------
    ("Explain Newton's laws of motion", False),
    ("Who won the 2018 football world cup?", False),
    ("What is quantum entanglement?", False),
    ("What is the capital of France?", False),

    # ---------- Out of scope (hard: overlaps PDF vocabulary) ----------
    ("What is the prize money for the winning team", False),
    ("What is the deadline for submitting the project", False),
    ("Explain how the Bayesian knowledge tracing update equation works, step by step", False),
    ("How many members are allowed in a team", False),
    ("Explain how RAGAS calculates the faithfulness score", False),
]

EXPECTED_PAGE = {
    "Which page describes how question answer keys should be verified, for example by cross-model validation": {1},
    "Which page lists the optional enhancements, such as a course flow map or Hindi support": {2},
    "Which page lists the evaluation criteria and their weights": {3},
    "Which page covers the expected deliverables": {2},
    "Which page says unsupported queries should be declined or flagged in source grounding": {1, 3},
}

def page_matches(answer, pages):
    found = {int(n) for n in re.findall(r"page\s*(\d+)", answer, re.I)}
    return bool(found & pages)

passed = 0
reasons = Counter()
for question, should_be_grounded in TESTS:
    result = answer_question(MATERIAL_ID, question)
    reasons[result["reason"]] += 1
    ok = result["grounded"] == should_be_grounded

    if ok and question in EXPECTED_PAGE:
        ok = page_matches(result["answer"], EXPECTED_PAGE[question])

    passed += int(ok)
    status = "PASS" if ok else "FAIL"
    print(f"[{status}] grounded={result['grounded']} ({result['reason']}) | {question}")
    print(f"        {result['answer'][:150]}")
    if not ok and question in EXPECTED_PAGE:
        print(f"        FULL ANSWER: {result['answer']}")

print(f"\n{passed}/...")
print(dict(reasons))

print(f"\n{passed}/{len(TESTS)} passed")