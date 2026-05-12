from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


InterviewMode = Literal["domain", "resume", "company-ai", "company-keyword"]
SessionStatus = Literal["in_progress", "completed", "terminated"]


class DomainInterviewStart(BaseModel):
    candidate_name: str = Field(min_length=2, max_length=100)
    candidate_email: str = Field(default="", max_length=320)
    domain: str = Field(min_length=2, max_length=100)


class InterviewAnswerRequest(BaseModel):
    answer_text: str = Field(default="", max_length=5000)
    question_id: str | None = Field(default=None)
    question_number: int | None = Field(default=None)


class InterviewTerminateRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=300)
    ended_by: str = Field(default="system", max_length=50)


class SessionEventRequest(BaseModel):
    event_type: str = Field(min_length=2, max_length=80)
    message: str = Field(min_length=1, max_length=600)
    level: str = Field(default="info", max_length=20)
    payload: dict = Field(default_factory=dict)


class EvaluationResult(BaseModel):
    score: int
    feedback: str
    improvement_suggestion: str


class QuestionItem(BaseModel):
    id: str
    question: str
    expected_keywords: list[str] = Field(default_factory=list)
    source: str = "generated"


class InterviewReportView(BaseModel):
    session_id: str
    candidate_name: str
    candidate_email: str = ""
    mode: InterviewMode
    status: SessionStatus | str = "completed"
    termination_reason: str = ""
    terminated_at: datetime | None = None
    ended_by: str = ""
    total_questions: int
    total_score: int = 0
    overall_score: int
    performance_label: str = ""
    question_scores: list[dict] = Field(default_factory=list)
    strengths: list[str]
    weaknesses: list[str]
    improvement_suggestions: list[str]
    scores: dict = Field(default_factory=dict)
    alerts: list[str] = Field(default_factory=list)
    final_feedback: str = ""
    items: list[dict]
    generated_at: datetime


class LegacyQuestionItem(BaseModel):
    id: str | None = None
    question: str = Field(min_length=1, max_length=2000)
    expected_keywords: list[str] = Field(default_factory=list)
    source: str = "legacy-flask"


class LegacyInterviewStart(BaseModel):
    candidate_name: str = Field(min_length=2, max_length=100)
    candidate_email: str = Field(default="", max_length=320)
    mode: InterviewMode
    metadata: dict = Field(default_factory=dict)
    questions: list[LegacyQuestionItem] = Field(min_length=1, max_length=20)
    greeting: str = ""
