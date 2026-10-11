import uuid

from fastapi import APIRouter, HTTPException

from app.services.progress import get_progress

router = APIRouter(prefix="/api/progress", tags=["progress"])


@router.get("/{user_id}")
def progress(user_id: str, material_id: str | None = None):
    user_id = user_id.strip() or "demo"
    if material_id:
        try:
            uuid.UUID(material_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid material_id")
    try:
        return get_progress(user_id, material_id)
    except RuntimeError as error:
        raise HTTPException(status_code=500, detail=str(error))
    except Exception:
        raise HTTPException(
            status_code=503,
            detail="The service is unavailable right now. Please try again.",
        )