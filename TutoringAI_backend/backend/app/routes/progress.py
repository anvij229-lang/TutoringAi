import uuid

from fastapi import APIRouter, HTTPException

from app.services.progress import get_progress
from app.services.selection import merge_ids

router = APIRouter(prefix="/api/progress", tags=["progress"])


@router.get("/{user_id}")
def progress(user_id: str, material_ids: str | None = None, material_id: str | None = None):
    user_id = user_id.strip() or "demo"
    ids = merge_ids(material_ids, material_id)
    for value in ids:
        try:
            uuid.UUID(value)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid material id")
    try:
        return get_progress(user_id, ids)
    except RuntimeError as error:
        raise HTTPException(status_code=500, detail=str(error))
    except Exception:
        raise HTTPException(
            status_code=503,
            detail="The service is unavailable right now. Please try again.",
        )