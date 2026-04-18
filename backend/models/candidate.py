from sqlalchemy import Column, Integer, String, Float, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from backend.database.db import Base


class Candidate(Base):
    __tablename__ = "candidates"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)
    phone = Column(String, nullable=True)
    resume_text = Column(Text, nullable=False)
    resume_filename = Column(String, nullable=True)
    job_role_id = Column(Integer, ForeignKey("job_roles.id"), nullable=False)
    ats_score = Column(Float, nullable=True)
    ats_reasoning = Column(Text, nullable=True)
    pipeline_stage = Column(String, default="applied")  # applied, ats_passed, ats_rejected, interview, screening, scheduled, hired, rejected
    interview_score = Column(Float, nullable=True)
    screening_data = Column(Text, nullable=True)  # JSON string
    interview_qa = Column(Text, nullable=True)    # JSON string
    availability = Column(Text, nullable=True)    # JSON string
    meeting_link = Column(String, nullable=True)
    interview_datetime = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    job_role = relationship("JobRole", back_populates="candidates")
    email_logs = relationship("EmailLog", back_populates="candidate")


class EmailLog(Base):
    __tablename__ = "email_logs"

    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id"), nullable=False)
    email_type = Column(String, nullable=False)  # rejection, interview_invite, confirmation
    sent_at = Column(DateTime, default=datetime.utcnow)
    recipient = Column(String, nullable=False)
    success = Column(Boolean, default=True)

    candidate = relationship("Candidate", back_populates="email_logs")
