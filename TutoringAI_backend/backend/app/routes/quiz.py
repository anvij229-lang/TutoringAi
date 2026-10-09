from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.evaluator import submit_quiz
from app.services.quiz_generator import generate_quiz
from app.services.topics import get_or_detect_topics

router = APIRouter(prefix="/api/quiz", tags=["quiz"])


class GenerateRequest(BaseModel):
    material_id: str
    topic_id: str | None = None
    difficulty: str = "medium"
    number_of_questions: int = 5


class AnswerItem(BaseModel):
    question_id: str
    answer: str


class SubmitRequest(BaseModel):
    quiz_id: str
    answers: list[AnswerItem]
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


@router.get("/topics/{material_id}")
def list_topics(material_id: str):
    return {"material_id": material_id, "topics": run(get_or_detect_topics, material_id)}


@router.post("/generate")
def generate(request: GenerateRequest):
    return run(
        generate_quiz,
        request.material_id,
        request.topic_id,
        request.difficulty,
        request.number_of_questions,
    )


@router.post("/submit")
def submit(request: SubmitRequest):
    answers = [item.model_dump() for item in request.answers]
    user_id = request.user_id.strip() or "demo"
    return run(submit_quiz, request.quiz_id, answers, user_id)