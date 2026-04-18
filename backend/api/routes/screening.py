from fastapi import APIRouter, HTTPException
from backend.agents.screening_agent import screening_agent
from backend.models.schemas import ScreeningSubmission

router = APIRouter(prefix="/screening", tags=["screening"])


@router.get("/{candidate_id}/questions")
async def get_screening_questions(candidate_id: int):
    questions = await screening_agent.get_questions(candidate_id)
    if not questions:
        raise HTTPException(status_code=404, detail="Candidate not found or no questions generated")
    return {"candidate_id": candidate_id, "questions": questions}


@router.post("/submit")
async def submit_screening(body: ScreeningSubmission):
    answers = [a.model_dump() for a in body.answers]
    result = await screening_agent.save_answers(body.candidate_id, answers)
    return result
