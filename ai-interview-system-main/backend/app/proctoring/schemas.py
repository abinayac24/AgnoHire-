from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field


class FrameAnalyzeRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=128)
    image_base64: str = Field(min_length=10)
    include_annotated_image: bool = True


class DetectionBox(BaseModel):
    label: str
    confidence: float
    x1: int
    y1: int
    x2: int
    y2: int
    partial: bool = False
    area: int | None = None


class ViolationEvent(BaseModel):
    timestamp: datetime
    session_id: str
    rule: str
    message: str
    severity: str = "high"
    details: dict = Field(default_factory=dict)


class FrameAnalyzeResponse(BaseModel):
    session_id: str
    timestamp: datetime
    fps_estimate: float
    detections: list[DetectionBox]
    alerts: list[ViolationEvent]
    metrics: dict
    annotated_image_base64: str | None = None
