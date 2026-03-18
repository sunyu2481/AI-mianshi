from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class AnswerCreate(BaseModel):
    mode: str  # "single" | "paper"
    question_id: int
    paper_id: Optional[int] = None
    paper_session_id: Optional[str] = None
    transcript: Optional[str] = None
    audio_url: Optional[str] = None
    duration_seconds: Optional[int] = None
    started_at: datetime
    finished_at: Optional[datetime] = None


class AnswerResponse(BaseModel):
    id: int
    mode: str
    question_id: int
    paper_id: Optional[int] = None
    paper_session_id: Optional[str] = None
    transcript: Optional[str] = None
    duration_seconds: Optional[int] = None
    started_at: datetime
    finished_at: Optional[datetime] = None
    practice_date: str
    created_at: datetime

    class Config:
        from_attributes = True


class AnalysisResultResponse(BaseModel):
    id: int
    answer_id: int
    analysis_type: str
    score: Optional[float] = None
    score_details: Optional[str] = None
    feedback: Optional[str] = None
    model_answer: Optional[str] = None
    model_name: str
    created_at: datetime

    class Config:
        from_attributes = True


class AnswerWithAnalysis(AnswerResponse):
    analysis: Optional[AnalysisResultResponse] = None
    question_content: Optional[str] = None


class HistoryAnalyzeRequest(BaseModel):
    answer_ids: list[int] = Field(default_factory=list)
    paper_session_ids: list[str] = Field(default_factory=list)
    analysis_type: str  # "history_single" | "history_paper"


class PaperAnalyzeRequest(BaseModel):
    paper_session_id: str


class PaperSessionCreate(BaseModel):
    paper_session_id: str
    paper_id: Optional[int] = None
    paper_title: str
    time_limit_seconds: Optional[int] = None
    total_duration_seconds: Optional[int] = None
    question_count: int
    started_at: datetime
    finished_at: Optional[datetime] = None


class PaperSessionResponse(BaseModel):
    id: int
    paper_session_id: str
    paper_id: Optional[int] = None
    paper_title: str
    time_limit_seconds: Optional[int] = None
    total_duration_seconds: Optional[int] = None
    question_count: int
    started_at: datetime
    finished_at: Optional[datetime] = None
    practice_date: str
    analysis_score: Optional[float] = None
    analysis_feedback: Optional[str] = None
    model_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
