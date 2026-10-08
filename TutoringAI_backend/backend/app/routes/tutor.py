from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.rag import answer_question

router = APIRouter(prefix="/api/tutor", tags=["tutor"])


class AskRequest(BaseModel):
    material_id: str
    question: str


@router.post("/ask")
def ask(request: AskRequest):
    question = request.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    try:
        return answer_question(request.material_id, question)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error))
    except RuntimeError as error:
        raise HTTPException(status_code=500, detail=str(error))
    except Exception:
        raise HTTPException(
            status_code=503,
            detail="The AI service is unavailable right now. Please try again.",
        )