import hashlib
import uuid

from app.database.db import get_connection

MAX_SELECTED = 10


def parse_ids(value) -> list:
    if value is None:
        return []
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    return [str(item).strip() for item in value if str(item).strip()]


def merge_ids(material_ids=None, material_id=None) -> list:
    return parse_ids(material_ids) + parse_ids(material_id)


def safe_title(title) -> str:
    text = " ".join(str(title or "").split())
    for character in "[]|":
        text = text.replace(character, " ")
    return " ".join(text.split())[:60] or "Untitled"


def selection_key(ids: list) -> str:
    return hashlib.sha1(",".join(sorted(ids)).encode()).hexdigest()[:16]


def resolve_selection(material_ids=None, material_id=None) -> list:
    ids = []
    for value in merge_ids(material_ids, material_id):
        try:
            ids.append(str(uuid.UUID(value)))
        except ValueError:
            raise ValueError("Invalid material id")

    ids = sorted(set(ids))
    if not ids:
        raise ValueError("Select at least one material")
    if len(ids) > MAX_SELECTED:
        raise ValueError(f"You can select up to {MAX_SELECTED} materials")

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, title, file_type FROM materials WHERE id = ANY(%s::uuid[])",
                (ids,),
            )
            rows = cur.fetchall()

    found = {
        str(row[0]): {"id": str(row[0]), "title": safe_title(row[1]), "file_type": row[2]}
        for row in rows
    }
    if any(item not in found for item in ids):
        raise LookupError("Material not found")
    return [found[item] for item in ids]