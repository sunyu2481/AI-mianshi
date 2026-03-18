from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from ..core.database import Base


class PaperSession(Base):
    __tablename__ = "paper_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    paper_session_id = Column(String(50), unique=True, nullable=False)
    paper_id = Column(Integer, ForeignKey("papers.id", ondelete="SET NULL"), nullable=True)
    paper_title = Column(String(200), nullable=False)
    time_limit_seconds = Column(Integer, nullable=True)
    total_duration_seconds = Column(Integer, nullable=True)
    question_count = Column(Integer, nullable=False, default=0)
    started_at = Column(DateTime, nullable=False)
    finished_at = Column(DateTime, nullable=True)
    practice_date = Column(String(10), nullable=False)
    analysis_score = Column(Float, nullable=True)
    analysis_feedback = Column(Text, nullable=True)
    model_name = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    paper = relationship("Paper")
