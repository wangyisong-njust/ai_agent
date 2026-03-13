from sqlalchemy import Column, Integer, String, DateTime, Text, Float
from sqlalchemy.sql import func
from app.database import Base


class JobApplication(Base):
    __tablename__ = "job_applications"

    id = Column(Integer, primary_key=True, index=True)
    platform = Column(String(50))          # linkedin / talentconnect
    company = Column(String(200))
    role = Column(String(200))
    job_url = Column(String(500))
    status = Column(String(50), default="pending")  # pending/applied/failed/skipped
    match_score = Column(Float, default=0.0)
    cover_letter = Column(Text, default="")
    notes = Column(Text, default="")
    applied_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())
