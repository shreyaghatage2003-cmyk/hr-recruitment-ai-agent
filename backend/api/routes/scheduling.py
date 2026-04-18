from fastapi import APIRouter, HTTPException
from backend.agents.scheduling_agent import scheduling_agent
from backend.models.schemas import ScheduleRequest

router = APIRouter(prefix="/scheduling", tags=["scheduling"])


@router.post("/schedule")
async def schedule_interview(body: ScheduleRequest):
    availability = [a.model_dump() for a in body.availability]
    result = await scheduling_agent.run(body.candidate_id, availability)
    if result.get("error"):
        raise HTTPException(status_code=404, detail=result["error"])
    if not result.get("meeting_link"):
        raise HTTPException(status_code=500, detail="Failed to create meeting")
    return result
