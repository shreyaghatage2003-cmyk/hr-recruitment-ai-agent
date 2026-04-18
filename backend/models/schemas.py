from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime


# --- Job Role ---
class JobRoleCreate(BaseModel):
    title: str
    description: str
    required_skills: str
    experience_level: str = Field(..., pattern="^(junior|mid|senior)$")
    headcount_target: int = 1


class JobRoleOut(JobRoleCreate):
    id: int
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


# --- Candidate ---
class CandidateOut(BaseModel):
    id: int
    name: str
    email: str
    phone: Optional[str]
    job_role_id: int
    ats_score: Optional[float]
    pipeline_stage: str
    interview_score: Optional[float]
    meeting_link: Optional[str]
    interview_datetime: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


class StageUpdate(BaseModel):
    stage: str


# --- ATS ---
class ATSRequest(BaseModel):
    job_role_id: int


class ATSResult(BaseModel):
    candidate_id: int
    ats_score: float
    reasoning: str
    passed: bool


# --- Interview ---
class InterviewAnswer(BaseModel):
    question_index: int
    answer: str
    time_taken: int  # seconds


class InterviewSubmission(BaseModel):
    candidate_id: int
    answers: List[InterviewAnswer]


# --- Screening ---
class ScreeningAnswer(BaseModel):
    question: str
    answer: str


class ScreeningSubmission(BaseModel):
    candidate_id: int
    answers: List[ScreeningAnswer]


# --- Scheduling ---
class AvailabilitySlot(BaseModel):
    date: str
    time: str
    timezone: str = "UTC"


class ScheduleRequest(BaseModel):
    candidate_id: int
    availability: List[AvailabilitySlot]


# --- Chatbot ---
class ChatMessage(BaseModel):
    message: str
    session_id: str
