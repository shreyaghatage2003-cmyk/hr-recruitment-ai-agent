from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from backend.database.db import get_db
from backend.models.candidate import Candidate
from backend.models.job_role import JobRole
from backend.services.db_service import candidate_service, job_role_service
from backend.models.schemas import JobRoleCreate, JobRoleOut
from typing import List, Optional

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary")
async def get_summary(db: AsyncSession = Depends(get_db)):
    """Pipeline summary: counts per stage, per role."""
    candidates = await candidate_service.list_all(db)
    roles = await job_role_service.list_all(db)

    stage_counts: dict = {}
    role_stats: dict = {}

    for c in candidates:
        stage_counts[c.pipeline_stage] = stage_counts.get(c.pipeline_stage, 0) + 1
        if c.job_role_id not in role_stats:
            role_stats[c.job_role_id] = {"stages": {}, "total": 0}
        role_stats[c.job_role_id]["stages"][c.pipeline_stage] = role_stats[c.job_role_id]["stages"].get(c.pipeline_stage, 0) + 1
        role_stats[c.job_role_id]["total"] += 1

    roles_out = []
    for r in roles:
        stats = role_stats.get(r.id, {"stages": {}, "total": 0})
        roles_out.append({
            "id": r.id,
            "title": r.title,
            "experience_level": r.experience_level,
            "headcount_target": r.headcount_target,
            "candidate_count": stats["total"],
            "stages": stats["stages"],
        })

    return {
        "total_candidates": len(candidates),
        "stage_counts": stage_counts,
        "roles": roles_out,
    }


@router.get("/roles", response_model=List[JobRoleOut])
async def list_roles(db: AsyncSession = Depends(get_db)):
    return await job_role_service.list_all(db)


@router.post("/roles", response_model=JobRoleOut)
async def create_role(body: JobRoleCreate, db: AsyncSession = Depends(get_db)):
    return await job_role_service.create(db, body.model_dump())
