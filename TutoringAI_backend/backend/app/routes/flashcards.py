from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.flashcards import generate_flashcards, get_flashcards, record_review
from app.services.selection import merge_ids

router = APIRouter(prefix="/api/flashcards", tags=["flashcards"])


class GenerateRequest(BaseModel):
    material_id: str | None = None
    material_ids: list[str] | None = None
    topic_id: str | None = None
    number_of_cards: int = 10
    weak_only: bool = False
    user_id: str = "demo"


class ReviewRequest(BaseModel):
    card_id: str
    known: bool
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
        merge_ids(request.material_ids, request.material_id),
        request.material_id,
        request.topic_id,
        request.number_of_cards,
        request.user_id.strip() or "demo",
        request.weak_only,
    )


@router.get("/{material_id}")
def latest(material_id: str, topic_id: str | None = None, user_id: str = "demo"):
    return run(get_flashcards, material_id, topic_id, user_id.strip() or "demo")


@router.post("/review")
def review(request: ReviewRequest):
    return run(record_review, request.card_id, request.known, request.user_id.strip() or "demo")