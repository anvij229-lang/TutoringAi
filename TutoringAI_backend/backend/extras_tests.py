from app.services.flashcards import generate_flashcards, record_review
from app.services.topics import get_or_detect_topics

MATERIAL_ID = "2e41b585-8ce7-418c-9c1f-ccbc5997c155"
USER_ID = "demo"

topics = get_or_detect_topics(MATERIAL_ID)
topic = topics[0]
print("Topic under test:", topic["name"])

deck = generate_flashcards(MATERIAL_ID, topic["id"], 6, USER_ID)
for number, card in enumerate(deck["cards"], start=1):
    print(f"\nCard {number} [{card['topic']}] source={card['source']}")
    print("  FRONT:", card["front"])
    print("  BACK: ", card["back"])

print("\nREVIEW:", record_review(deck["cards"][0]["card_id"], True, USER_ID))

from app.services.mindmap import generate_mindmap

print("\nMIND MAP (overview)")
result = generate_mindmap(MATERIAL_ID, None, True, USER_ID)
print("nodes:", result["node_count"])
print(result["markdown"])

print("\nMIND MAP (focused on", topic["name"] + ")")
focused = generate_mindmap(MATERIAL_ID, topic["id"], True, USER_ID)
print("nodes:", focused["node_count"])
print(focused["markdown"])

from collections import Counter


def titles(node):
    found = [node["title"].lower()]
    for child in node["children"]:
        found += titles(child)
    return found


repeats = [t for t, n in Counter(titles(result["tree"])).items() if n > 1]
print("\nrepeated titles in overview:", repeats)