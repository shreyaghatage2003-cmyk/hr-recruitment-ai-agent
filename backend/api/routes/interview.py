from fastapi import APIRouter, HTTPException
from backend.agents.interview_agent import interview_agent
from backend.models.schemas import InterviewSubmission

router = APIRouter(prefix="/interview", tags=["interview"])


@router.get("/{candidate_id}/questions")
async def get_questions(candidate_id: int):
    """Generate and return interview questions for a candidate."""
    questions = await interview_agent.get_questions(candidate_id)
    if not questions:
        raise HTTPException(status_code=404, detail="Candidate not found or could not generate questions")
    return {"candidate_id": candidate_id, "questions": questions}


@router.post("/submit")
async def submit_answers(body: InterviewSubmission):
    """Evaluate submitted answers and persist results."""
    questions = await interview_agent.get_questions(body.candidate_id)
    if not questions:
        raise HTTPException(status_code=404, detail="Candidate not found")
    raw_answers = [a.model_dump() for a in body.answers]
    result = await interview_agent.run(body.candidate_id, questions, raw_answers)
    return result
