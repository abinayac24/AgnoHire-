from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


InterviewMode = Literal["domain", "resume", "company-ai", "company-keyword"]
SessionStatus = Literal["in_progress", "completed"]


class DomainInterviewStart(BaseModel):
    candidate_name: str = Field(min_length=2, max_length=100)
    candidate_email: str = Field(default="", max_length=320)
    domain: str = Field(min_length=2, max_length=100)


class InterviewAnswerRequest(BaseModel):
    answer_text: str = Field(default="", max_length=5000)


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
    total_questions: int
    overall_score: int
    strengths: list[str]
    weaknesses: list[str]
    improvement_suggestions: list[str]
    items: list[dict]
    generated_at: datetime
