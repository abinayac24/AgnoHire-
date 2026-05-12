from io import BytesIO

from fastapi import APIRouter
from fastapi.responses import RedirectResponse, StreamingResponse
from pydantic import BaseModel, Field

from app.config import settings
from app.services.interviewer_renderer import interviewer_renderer


router = APIRouter(tags=["interviewer"])


class InterviewerRenderRequest(BaseModel):
    text: str = Field(min_length=1, max_length=5000)
    session_id: str = Field(default="", max_length=128)
    question_id: str = Field(default="", max_length=128)
    preload: bool = False


@router.post("/interviewer/render")
def render_interviewer(payload: InterviewerRenderRequest):
    result = interviewer_renderer.render_question(payload.text)
    video_url = result.video_url
    if result.video_token:
        video_url = f"{settings.api_prefix}/interviewer/video/{result.video_token}"
    audio_url = f"{settings.api_prefix}/interviewer/audio/{result.audio_token}" if result.audio_token else ""
    return {
        "mode": result.mode,
        "provider": result.provider,
        "video_url": video_url,
        "audio_url": audio_url,
        "subtitle": result.subtitle,
        "ready": result.ready,
    }

@router.get("/interviewer-video")
def interviewer_video_by_text(text: str):
    result = interviewer_renderer.render_question(text)
    if result.video_token:
        stream_item = interviewer_renderer.get_video_stream(result.video_token)
        if not stream_item:
            return StreamingResponse(BytesIO(b""), media_type="video/mp4", status_code=404)
        stream, mime_type = stream_item
        return StreamingResponse(stream, media_type=mime_type)
    if result.video_url:
        return RedirectResponse(result.video_url)
    if result.audio_token:
        stream_item = interviewer_renderer.get_audio_stream(result.audio_token)
        if not stream_item:
            return StreamingResponse(BytesIO(b""), media_type="audio/mpeg", status_code=404)
        stream, mime_type = stream_item
        return StreamingResponse(stream, media_type=mime_type)
    return StreamingResponse(BytesIO(b""), media_type="video/mp4", status_code=503)


@router.get("/interviewer/audio/{token}")
def interviewer_audio(token: str):
    stream_item = interviewer_renderer.get_audio_stream(token)
    if not stream_item:
        return StreamingResponse(BytesIO(b""), media_type="audio/mpeg", status_code=404)
    stream, mime_type = stream_item
    return StreamingResponse(stream, media_type=mime_type)


@router.get("/interviewer/video/{token}")
def interviewer_video(token: str):
    stream_item = interviewer_renderer.get_video_stream(token)
    if not stream_item:
        return StreamingResponse(BytesIO(b""), media_type="video/mp4", status_code=404)
    stream, mime_type = stream_item
    return StreamingResponse(stream, media_type=mime_type)
