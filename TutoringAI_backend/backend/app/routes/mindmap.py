from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.mindmap import generate_mindmap, get_mindmap

router = APIRouter(prefix="/api/mindmap", tags=["mindmap"])


class GenerateRequest(BaseModel):
    material_id: str
    topic_id: str | None = None
    refresh: bool = False
    user_id: str = "demo"


def run(function, *args):
    try:
        return function(*args)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error))
    except RuntimeError as error:
        raise HTTPException(status_code=500, detail=str(error))
    except Exception:
        raise HTTPException(
            status_code=503,
            detail="The service is unavailable right now. Please try again.",
        )


@router.post("/generate")
def generate(request: GenerateRequest):
    return run(
        generate_mindmap,
        request.material_id,
        request.topic_id,
        request.refresh,
        request.user_id.strip() or "demo",
    )


@router.get("/{material_id}")
def saved(material_id: str, topic_id: str | None = None, user_id: str = "demo"):
    return run(get_mindmap, material_id, topic_id, user_id.strip() or "demo")