from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.rag import answer_question
from app.services.teach import teach_topic
from app.services.selection import merge_ids

router = APIRouter(prefix="/api/tutor", tags=["tutor"])


class AskRequest(BaseModel):
    material_id: str | None = None
    material_ids: list[str] | None = None
    question: str


@router.post("/ask")
def ask(request: AskRequest):
    question = request.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    try:
        return answer_question(merge_ids(request.material_ids, request.material_id), question)
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

class TeachRequest(BaseModel):
    topic_id: str
    user_id: str = "demo"


@router.post("/teach")
def teach(request: TeachRequest):
    try:
        return teach_topic(request.topic_id, request.user_id.strip() or "demo")
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error))
    except Exception:
        raise HTTPException(
            status_code=503,
            detail="The AI service is unavailable right now. Please try again.",
        )