from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from backend.database.db import get_db
from backend.agents.ats_agent import ats_agent
from backend.services.db_service import candidate_service
from backend.models.schemas import CandidateOut, StageUpdate
from typing import List, Optional

router = APIRouter(prefix="/candidates", tags=["candidates"])


@router.post("/upload")
async def upload_resume(
    file: UploadFile = File(...),
    job_role_id: int = Form(...),
):
    """Ingest resume and run ATS scoring."""
    file_bytes = await file.read()
    result = await ats_agent.run(file_bytes, file.filename, job_role_id)
    return result


@router.get("/", response_model=List[CandidateOut])
async def list_candidates(
    role_id: Optional[int] = None,
    stage: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    return await candidate_service.list_all(db, role_id=role_id, stage=stage)


@router.get("/{candidate_id}", response_model=CandidateOut)
async def get_candidate(candidate_id: int, db: AsyncSession = Depends(get_db)):
    c = await candidate_service.get(db, candidate_id)
    if not c:
        raise HTTPException(404, "Candidate not found")
    return c


@router.patch("/{candidate_id}/stage")
async def update_stage(candidate_id: int, body: StageUpdate, db: AsyncSession = Depends(get_db)):
    c = await candidate_service.update_stage(db, candidate_id, body.stage)
    if not c:
        raise HTTPException(404, "Candidate not found")
    return {"candidate_id": candidate_id, "stage": body.stage}
