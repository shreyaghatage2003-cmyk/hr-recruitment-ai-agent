import json
from typing import Optional, List
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from backend.models.candidate import Candidate, EmailLog
from backend.models.job_role import JobRole


class CandidateService:
    async def create(self, db: AsyncSession, data: dict) -> Candidate:
        candidate = Candidate(**data)
        db.add(candidate)
        await db.commit()
        await db.refresh(candidate)
        return candidate

    async def get(self, db: AsyncSession, candidate_id: int) -> Optional[Candidate]:
        result = await db.execute(select(Candidate).where(Candidate.id == candidate_id))
        return result.scalar_one_or_none()

    async def get_by_email(self, db: AsyncSession, email: str) -> Optional[Candidate]:
        result = await db.execute(select(Candidate).where(Candidate.email == email))
        return result.scalar_one_or_none()

    async def list_all(self, db: AsyncSession, role_id: Optional[int] = None, stage: Optional[str] = None) -> List[Candidate]:
        query = select(Candidate)
        if role_id:
            query = query.where(Candidate.job_role_id == role_id)
        if stage:
            query = query.where(Candidate.pipeline_stage == stage)
        result = await db.execute(query)
        return result.scalars().all()

    async def update_stage(self, db: AsyncSession, candidate_id: int, stage: str) -> Optional[Candidate]:
        await db.execute(update(Candidate).where(Candidate.id == candidate_id).values(pipeline_stage=stage))
        await db.commit()
        return await self.get(db, candidate_id)

    async def update_fields(self, db: AsyncSession, candidate_id: int, fields: dict) -> Optional[Candidate]:
        await db.execute(update(Candidate).where(Candidate.id == candidate_id).values(**fields))
        await db.commit()
        return await self.get(db, candidate_id)

    async def email_already_sent(self, db: AsyncSession, candidate_id: int, email_type: str) -> bool:
        result = await db.execute(
            select(EmailLog).where(
                EmailLog.candidate_id == candidate_id,
                EmailLog.email_type == email_type,
                EmailLog.success == True,
            )
        )
        return result.scalar_one_or_none() is not None

    async def log_email(self, db: AsyncSession, candidate_id: int, email_type: str, recipient: str, success: bool):
        log = EmailLog(candidate_id=candidate_id, email_type=email_type, recipient=recipient, success=success)
        db.add(log)
        await db.commit()


class JobRoleService:
    async def create(self, db: AsyncSession, data: dict) -> JobRole:
        role = JobRole(**data)
        db.add(role)
        await db.commit()
        await db.refresh(role)
        return role

    async def get(self, db: AsyncSession, role_id: int) -> Optional[JobRole]:
        result = await db.execute(select(JobRole).where(JobRole.id == role_id))
        return result.scalar_one_or_none()

    async def list_all(self, db: AsyncSession) -> List[JobRole]:
        result = await db.execute(select(JobRole).where(JobRole.is_active == True))
        return result.scalars().all()


candidate_service = CandidateService()
job_role_service = JobRoleService()
