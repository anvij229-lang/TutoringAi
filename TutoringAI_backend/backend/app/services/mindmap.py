import json
import uuid

from app.database.db import get_connection
from app.services.learner_model import mastery_status
from app.services.llm import chat
from app.services.rag import material_exists, retrieve_chunks
from app.services.topics import get_or_detect_topics
from app.utils.json_utils import normalize_text, parse_json
from app.utils.prompts import MINDMAP_PROMPT
from app.utils.citations import clean_source_label

MAX_DEPTH = 3
MAX_CHILDREN = {1: 8, 2: 5, 3: 4}
MAX_NODES = 60


def chunk_label(chunk: dict) -> str:
    return chunk.get("label") or f"Page {chunk['page']}"


def material_title(material_id: str) -> str:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT title FROM materials WHERE id = %s::uuid", (material_id,))
            row = cur.fetchone()
    return row[0] if row else "Study material"


def build_context(material_id: str, topics: list, per_topic: int, max_chars: int) -> str:
    blocks = []
    for topic in topics:
        query = f"{topic['name']}. {topic['description'] or ''}"
        for chunk in retrieve_chunks(material_id, query, top_k=per_topic):
            blocks.append(
                f"[Topic: {topic['name']} | {chunk_label(chunk)}]\n{chunk['text'][:max_chars]}"
            )
    return "\n\n".join(blocks)


def clean_title(value) -> str:
    return normalize_text(value)[:60]


def clean_source(value):
    return clean_source_label(value)


def as_list(value) -> list:
    return value if isinstance(value, list) else []


def clean_node(item, depth: int, state: dict, topic_lookup: dict):
    if not isinstance(item, dict) or state["count"] >= MAX_NODES:
        return None
    title = clean_title(item.get("title"))
    if not title:
        return None

    key = title.lower()
    if key in state["seen"]:
        return None
    state["seen"].add(key)

    state["count"] += 1
    node = {
        "id": f"n{state['count']}",
        "title": title,
        "source": clean_source(item.get("source")),
        "children": [],
    }
    if depth == 1:
        node["topic_id"] = topic_lookup.get(key)

    if depth < MAX_DEPTH:
        for child in as_list(item.get("children")):
            if len(node["children"]) >= MAX_CHILDREN[depth + 1]:
                break
            cleaned = clean_node(child, depth + 1, state, topic_lookup)
            if cleaned is not None:
                node["children"].append(cleaned)
    return node


def clean_tree(raw, fallback_title: str, topic_lookup: dict, blocked=None):
    if not isinstance(raw, dict):
        return None
    blocked = blocked or set()

    if "children" not in raw:
        for value in raw.values():
            if isinstance(value, dict) and "children" in value:
                raw = value
                break

    root_title = clean_title(raw.get("title")) or fallback_title[:60]
    state = {"count": 0, "seen": set() if topic_lookup else {root_title.lower()}}
    root = {"id": "root", "title": root_title, "source": None, "children": []}

    for child in as_list(raw.get("children")):
        if len(root["children"]) >= MAX_CHILDREN[1]:
            break
        if isinstance(child, dict) and clean_title(child.get("title")).lower() in blocked:
            continue
        cleaned = clean_node(child, 1, state, topic_lookup)
        if cleaned is not None:
            root["children"].append(cleaned)

    return root if root["children"] else None


def count_nodes(node: dict) -> int:
    return 1 + sum(count_nodes(child) for child in node["children"])


def to_markdown(node: dict, depth: int = 0) -> str:
    if depth == 0:
        line = f"# {node['title']}"
    elif depth == 1:
        line = f"## {node['title']}"
    else:
        line = "  " * (depth - 2) + f"- {node['title']}"
    lines = [line]
    for child in node["children"]:
        lines.append(to_markdown(child, depth + 1))
    return "\n".join(lines)


def with_mastery(tree: dict, user_id: str) -> dict:
    ids = [n["topic_id"] for n in tree["children"] if n.get("topic_id")]
    scores = {}
    if ids:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT topic_id, mastery_score FROM mastery "
                    "WHERE user_id = %s AND topic_id = ANY(%s::uuid[])",
                    (user_id, ids),
                )
                scores = {str(row[0]): row[1] for row in cur.fetchall()}

    for node in tree["children"]:
        topic = node.get("topic_id")
        if topic in scores:
            node["mastery"] = scores[topic]
            node["status"] = mastery_status(scores[topic])
        elif topic:
            node["mastery"] = None
            node["status"] = "not_started"
        else:
            node["mastery"] = None
            node["status"] = None
    return tree


def load_tree(material_id: str, scope: str):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT tree FROM mindmaps WHERE material_id = %s::uuid AND scope_key = %s",
                (material_id, scope),
            )
            row = cur.fetchone()
    return row[0] if row else None


def save_tree(material_id: str, scope: str, tree: dict):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO mindmaps (material_id, scope_key, tree) "
                "VALUES (%s::uuid, %s, %s::jsonb) "
                "ON CONFLICT (material_id, scope_key) DO UPDATE SET "
                "tree = EXCLUDED.tree, created_at = now()",
                (material_id, scope, json.dumps(tree)),
            )
        conn.commit()


def build_response(material_id: str, scope: str, tree: dict, user_id: str, cached: bool):
    tree = with_mastery(tree, user_id)
    return {
        "material_id": material_id,
        "scope": scope,
        "cached": cached,
        "node_count": count_nodes(tree),
        "tree": tree,
        "markdown": to_markdown(tree),
    }


def generate_mindmap(material_id: str, topic_id=None, refresh: bool = False, user_id: str = "demo"):
    try:
        uuid.UUID(material_id)
        if topic_id:
            topic_id = str(uuid.UUID(topic_id))
    except ValueError:
        raise ValueError("Invalid material_id or topic_id")

    topics = get_or_detect_topics(material_id)
    scope = topic_id or "all"

    if not refresh:
        cached = load_tree(material_id, scope)
        if cached is not None:
            return build_response(material_id, scope, cached, user_id, True)

    blocked = set()
    if topic_id:
        focus = next((t for t in topics if t["id"] == topic_id), None)
        if focus is None:
            raise LookupError("Topic not found for this material")
        root_title = focus["name"]
        other_names = [t["name"] for t in topics if t["id"] != topic_id]
        blocked = {normalize_text(name).lower() for name in other_names}
        context = build_context(material_id, [focus], per_topic=8, max_chars=600)
        topic_lookup = {}
        user_prompt = (
            "Mode: focused\n"
            f"Central idea: {root_title}\n"
            "Create 4 to 6 first-level branches. Each branch must be a sub-idea or part of this one topic.\n"
            f"Never use any of these as a branch title, because they are other topics: {', '.join(other_names)}.\n"
            "Never use the central idea itself as a branch title.\n\n"
            f"Study material:\n{context}"
        )
    else:
        chosen = topics[: MAX_CHILDREN[1]]
        root_title = material_title(material_id)
        context = build_context(material_id, chosen, per_topic=3, max_chars=450)
        topic_lookup = {normalize_text(t["name"]).lower(): t["id"] for t in chosen}
        names = ", ".join(t["name"] for t in chosen)
        user_prompt = (
            "Mode: overview\n"
            f"The file name is: {root_title}\n"
            "Write a short central title of 2 to 5 words describing what the whole material is about and use it as the root title.\n"
            f"The first-level branches must be exactly these topics, in this order: {names}\n\n"
            f"Study material:\n{context}"
        )

    if not context.strip():
        raise ValueError("Not enough material to build a mind map")

    best = None
    for attempt in range(1, 4):
        reply = ""
        try:
            reply = chat(MINDMAP_PROMPT, user_prompt, temperature=0.3)
            data = parse_json(reply)
        except ValueError as error:
            print(f"[mindmap] attempt {attempt}: bad JSON ({error}). Reply began: {reply[:300]!r}")
            continue

        tree = clean_tree(data, root_title, topic_lookup, blocked)
        if tree is None:
            keys = list(data)[:6] if isinstance(data, dict) else type(data).__name__
            print(f"[mindmap] attempt {attempt}: JSON had no usable branches. Top-level: {keys}")
            print(f"[mindmap] reply began: {reply[:300]!r}")
            continue

        if best is None or count_nodes(tree) > count_nodes(best):
            best = tree
        if count_nodes(best) >= 10:
            break

    if best is None:
        raise RuntimeError("Could not generate a valid mind map. Please try again.")

    save_tree(material_id, scope, best)
    return build_response(material_id, scope, best, user_id, False)


def get_mindmap(material_id: str, topic_id=None, user_id: str = "demo"):
    try:
        uuid.UUID(material_id)
        if topic_id:
            topic_id = str(uuid.UUID(topic_id))
    except ValueError:
        raise ValueError("Invalid material_id or topic_id")

    if not material_exists(material_id):
        raise LookupError("Material not found")

    scope = topic_id or "all"
    tree = load_tree(material_id, scope)
    if tree is None:
        raise LookupError("No mind map yet. Generate one first.")
    return build_response(material_id, scope, tree, user_id, True)