from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from backend.database.db import Base


class JobRole(Base):
    __tablename__ = "job_roles"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    required_skills = Column(Text, nullable=False)   # comma-separated
    experience_level = Column(String, nullable=False)  # junior / mid / senior
    headcount_target = Column(Integer, default=1)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    candidates = relationship("Candidate", back_populates="job_role")
