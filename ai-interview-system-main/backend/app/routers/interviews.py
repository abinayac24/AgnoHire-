import logging
import time
from io import BytesIO
import secrets

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel, Field
from werkzeug.security import check_password_hash

from app.config import settings
from app.dependencies import get_repository
from app.email_service import schedule_report_email_async
from app.models import InterviewAnswerRequest, InterviewTerminateRequest, LegacyInterviewStart, SessionEventRequest
from app.proctoring.identity_verifier import identity_verifier
from app.services.ai_evaluator import evaluator
from app.services.final_feedback import enrich_report_with_final_feedback
from app.services.keyword_matcher import keyword_matcher
from app.services.report_generator import report_generator
from app.services.voice_handler import voice_handler


router = APIRouter(tags=["interviews"])
security = HTTPBasic()
logger = logging.getLogger(__name__)


class SubmitInterviewRequest(BaseModel):
    session_id: str = Field(min_length=8, max_length=128)


class IdentityRegistrationRequest(BaseModel):
    session_id: str = Field(min_length=8, max_length=128)
    username: str = Field(min_length=1, max_length=128)
    face_embedding: list[float] | None = None
    voice_embedding: list[float] | None = None


def require_admin(credentials: HTTPBasicCredentials = Depends(security)):
    candidate_identity = credentials.username or ""
    username_ok = secrets.compare_digest(candidate_identity, settings.admin_username)
    email_ok = secrets.compare_digest(candidate_identity, settings.admin_email)
    supplied_password = credentials.password or ""
    if settings.admin_password_hash:
        password_ok = check_password_hash(settings.admin_password_hash, supplied_password)
    else:
        password_ok = secrets.compare_digest(supplied_password, settings.admin_password)
    if not ((username_ok or email_ok) and password_ok):
        raise HTTPException(status_code=403, detail="Unauthorized")
    return candidate_identity


def _queue_report_email(session_id: str, report: dict, repository) -> None:
    repository.mark_report_email_scheduled(session_id, True)
    repository.update_report_email_status(session_id, "scheduled", "")

    schedule_report_email_async(
        report=report,
        delay_seconds=settings.result_email_delay_seconds,
        on_success=lambda: (
            repository.mark_report_email_sent(session_id, True),
            repository.update_report_email_status(session_id, "sent", ""),
        ),
        on_failure=lambda reason: (
            repository.mark_report_email_scheduled(session_id, False),
            repository.update_report_email_status(session_id, "failed", reason),
        ),
    )


def finalize_interview_result(session_id: str, repository, background_tasks: BackgroundTasks | None = None) -> dict:
    session = repository.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    report = repository.build_report(session_id, evaluator.summarize_report)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    events = repository.list_session_events(session_id, limit=500)
    report = enrich_report_with_final_feedback(report, events=events)
    if (session.get("status") or "") == "in_progress":
        repository.set_completion_reason(session_id, "Interview completed successfully")
    repository.save_final_report(session_id, report)

    candidate_email = (session.get("candidate_email") or "").strip()
    if not candidate_email:
        repository.mark_report_email_scheduled(session_id, False)
        repository.update_report_email_status(session_id, "skipped", "candidate_email_missing")
    elif not repository.report_email_sent(session_id) and not repository.report_email_scheduled(session_id):
        if background_tasks is not None:
            background_tasks.add_task(_queue_report_email, session_id, report, repository)
        else:
            _queue_report_email(session_id, report, repository)

    status = repository.get_report_email_status(session_id) or {}
    return {
        "report": report,
        "email_status": status.get("status", "pending"),
        "email_scheduled": status.get("scheduled", False),
        "delay_seconds": settings.result_email_delay_seconds,
    }


@router.post("/interviews/legacy/start")
def start_legacy_interview(
    payload: LegacyInterviewStart,
    repository=Depends(get_repository),
):
    session = repository.create_session(
        candidate_name=payload.candidate_name,
        candidate_email=payload.candidate_email.strip(),
        mode=payload.mode,
        metadata=payload.metadata or {},
        questions=[question.model_dump() for question in payload.questions[:5]],
    )
    if payload.greeting:
        repository.update_session_greeting(session["session_id"], payload.greeting)
    return repository.build_session_view(session["session_id"])


@router.post("/interviews/{session_id}/register-identity")
def register_interview_identity(
    session_id: str,
    payload: IdentityRegistrationRequest,
    repository=Depends(get_repository),
):
    """
    Register the authenticated user's identity for continuous verification during the interview.
    This should be called after successful username + face + voice login.
    """
    session = repository.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Convert list embeddings to numpy arrays if provided
    face_emb = None
    voice_emb = None

    if payload.face_embedding:
        try:
            import numpy as np
            face_emb = np.array(payload.face_embedding, dtype=np.float32)
        except Exception as e:
            logger.warning("Failed to convert face embedding: %s", e)

    if payload.voice_embedding:
        try:
            import numpy as np
            voice_emb = np.array(payload.voice_embedding, dtype=np.float32)
        except Exception as e:
            logger.warning("Failed to convert voice embedding: %s", e)

    # Register with identity verifier
    identity_verifier.register_user(
        session_id=session_id,
        username=payload.username,
        face_embedding=face_emb,
        voice_embedding=voice_emb,
    )

    logger.info(
        "Identity registered for interview session=%s, username=%s, has_face=%s, has_voice=%s",
        session_id, payload.username, face_emb is not None, voice_emb is not None
    )

    return {
        "session_id": session_id,
        "username": payload.username,
        "identity_registered": True,
        "face_registered": face_emb is not None,
        "voice_registered": voice_emb is not None,
    }


@router.get("/interviews/{session_id}/identity-status")
def get_identity_status(session_id: str, repository=Depends(get_repository)):
    """Get the current identity verification status for the interview session."""
    session = repository.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    is_verified = identity_verifier.is_identity_verified(session_id)
    face_box = identity_verifier.get_face_box(session_id)

    return {
        "session_id": session_id,
        "identity_verified": is_verified,
        "face_box": face_box,
        "status": "verified" if is_verified else "unverified",
    }


@router.get("/interviews/{session_id}")
def get_interview_session(
    session_id: str,
    repository=Depends(get_repository),
):
    view = repository.build_session_view(session_id)
    if not view:
        raise HTTPException(status_code=404, detail="Session not found")
    return view


@router.get("/interviews/{session_id}/upcoming")
def get_upcoming_question(session_id: str, repository=Depends(get_repository)):
    session = repository.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    upcoming = repository.get_next_question_preview(session_id)
    return {
        "session_id": session_id,
        "upcoming_question": upcoming,
    }


def background_evaluate_answer(
    session_id: str,
    question: dict,
    answer_text: str,
    mode: str,
    metadata: dict,
    repository,
):
    start_time = time.time()
    try:
        if mode == "company-keyword":
            evaluation = keyword_matcher.evaluate_answer(
                answer=answer_text,
                expected_keywords=question.get("expected_keywords", []),
                question=question["question"],
            )
        else:
            evaluation = evaluator.evaluate_answer(
                question=question["question"],
                answer=answer_text,
                context={
                    "mode": mode,
                    "metadata": metadata,
                },
            )
        repository.update_evaluation(session_id, question.get("id"), evaluation)
        duration = time.time() - start_time
        logger.info(
            "Background evaluation completed",
            extra={
                "session_id": session_id,
                "question_id": question.get("id"),
                "duration": round(duration, 3),
            },
        )
    except Exception as e:
        logger.error(
            "Background evaluation failed",
            extra={"session_id": session_id, "error": str(e)},
        )


@router.post("/interviews/{session_id}/answer")
def submit_answer(
    session_id: str,
    payload: InterviewAnswerRequest,
    background_tasks: BackgroundTasks,
    repository=Depends(get_repository),
):
    start_ts = time.time()
    session = repository.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.get("status") == "terminated":
        raise HTTPException(status_code=400, detail="Interview already terminated")

    question = repository.get_current_question(session_id)
    if not question:
        raise HTTPException(status_code=400, detail="No active question")

    expected_question_id = question.get("id")
    if not payload.question_id:
        logger.error(
            "Missing question_id in submission",
            extra={"session_id": session_id, "expected_question_id": expected_question_id},
        )
        raise HTTPException(status_code=400, detail="Missing question_id in submission")

    if payload.question_id != expected_question_id:
        logger.error(
            "Question ID mismatch on submission",
            extra={
                "session_id": session_id,
                "expected_question_id": expected_question_id,
                "received_question_id": payload.question_id,
            },
        )
        raise HTTPException(
            status_code=400, 
            detail=f"Question ID mismatch. Expected {expected_question_id}, got {payload.question_id}"
        )

    normalized_answer = voice_handler.normalize_transcript(payload.answer_text)
    
    # 1. Record answer immediately with placeholder evaluation
    t0 = time.time()
    repository.record_answer(session_id, question, normalized_answer, None)
    t_record = time.time() - t0

    # 2. Add evaluation to background tasks
    background_tasks.add_task(
        background_evaluate_answer,
        session_id=session_id,
        question=question,
        answer_text=normalized_answer,
        mode=session["mode"],
        metadata=session.get("metadata", {}),
        repository=repository,
    )

    # 3. Advance session immediately
    t1 = time.time()
    repository.append_session_event(
        session_id,
        "answer_submitted",
        f"Answer submitted for question {question.get('id', '')}",
        payload={"answer_length": len(normalized_answer or "")},
    )
    repository.advance_session(session_id)
    t_advance = time.time() - t1

    refreshed_session = repository.get_session(session_id) or session
    answered_index = min(int(refreshed_session.get("current_index", 0)), 5)
    
    t2 = time.time()
    next_question = repository.get_current_question(session_id)
    if answered_index >= 5:
        next_question = None
    t_next = time.time() - t2

    total_duration = time.time() - start_ts
    logger.info(
        "Next question triggered (optimized)",
        extra={
            "session_id": session_id,
            "answered_index": answered_index,
            "next_question_id": (next_question or {}).get("id"),
            "completed": next_question is None,
            "durations": {
                "record": round(t_record, 4),
                "advance": round(t_advance, 4),
                "next_fetch": round(t_next, 4),
                "total": round(total_duration, 4),
            }
        },
    )

    if next_question is None:
        finalize_interview_result(session_id, repository, background_tasks)

    return {
        "session_id": session_id,
        "completed": next_question is None,
        "next_question": next_question,
        "answered_index": answered_index,
        "timing": {
            "processing_time": round(total_duration, 4),
            "record_time": round(t_record, 4),
            "advance_time": round(t_advance, 4),
            "next_fetch_time": round(t_next, 4)
        }
    }


@router.post("/submit-interview")
def submit_interview(
    payload: SubmitInterviewRequest,
    background_tasks: BackgroundTasks,
    repository=Depends(get_repository),
):
    finalized = finalize_interview_result(payload.session_id, repository, background_tasks)
    return {
        "session_id": payload.session_id,
        "status": "accepted",
        "result_stored": True,
        "email_status": finalized["email_status"],
        "email_scheduled": finalized["email_scheduled"],
        "email_delay_seconds": finalized["delay_seconds"],
    }


@router.get("/interviews/{session_id}/completion")
def get_completion_view(session_id: str, repository=Depends(get_repository)):
    session = repository.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    termination_reason = session.get("termination_reason", "") or "Interview completed successfully"
    title = "Interview Completed" if session.get("status") == "completed" else "Interview Ended"
    subtext = (
        "Your results and feedback will be sent to your email within 5 minutes."
        if session.get("status") == "completed"
        else "Your session has ended and the reason is shown below."
    )
    return {
        "title": title,
        "candidate_name": session.get("candidate_name", "Candidate"),
        "message": f"Thank you for attending the interview, {session.get('candidate_name', 'Candidate')}.",
        "subtext": subtext,
        "termination_reason": termination_reason,
        "status": session.get("status", "completed"),
        "delay_seconds": settings.result_email_delay_seconds,
    }


@router.post("/interviews/{session_id}/terminate")
def terminate_interview(
    session_id: str,
    payload: InterviewTerminateRequest,
    background_tasks: BackgroundTasks,
    repository=Depends(get_repository),
):
    session = repository.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    repository.terminate_session(session_id, payload.reason, payload.ended_by)
    repository.append_session_event(
        session_id,
        "interview_terminated",
        payload.reason,
        level="warning",
        payload={"ended_by": payload.ended_by},
    )

    # Clean up identity verifier for this session
    identity_verifier.unregister_session(session_id)

    finalized = None
    try:
        finalized = finalize_interview_result(session_id, repository, background_tasks)
    except HTTPException:
        finalized = None

    return {
        "session_id": session_id,
        "status": "terminated",
        "termination_reason": payload.reason,
        "finalized": bool(finalized),
    }


@router.post("/interviews/{session_id}/events")
def add_session_event(
    session_id: str,
    payload: SessionEventRequest,
    repository=Depends(get_repository),
):
    session = repository.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    repository.append_session_event(
        session_id=session_id,
        event_type=payload.event_type,
        message=payload.message,
        level=payload.level,
        payload=payload.payload,
    )
    return {"session_id": session_id, "status": "recorded"}


@router.get("/interviews/{session_id}/events")
def get_session_events(
    session_id: str,
    _: str = Depends(require_admin),
    limit: int = Query(default=200, ge=1, le=1000),
    repository=Depends(get_repository),
):
    session = repository.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"session_id": session_id, "events": repository.list_session_events(session_id, limit=limit)}


@router.get("/interviews/{session_id}/report")
def get_report(session_id: str, _: str = Depends(require_admin), repository=Depends(get_repository)):
    report = repository.build_report(session_id, evaluator.summarize_report)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    events = repository.list_session_events(session_id, limit=500)
    report = enrich_report_with_final_feedback(report, events=events)
    repository.save_final_report(session_id, report)
    return report


@router.get("/interviews/{session_id}/report/pdf")
def download_report_pdf(session_id: str, _: str = Depends(require_admin), repository=Depends(get_repository)):
    report = repository.build_report(session_id, evaluator.summarize_report)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    events = repository.list_session_events(session_id, limit=500)
    report = enrich_report_with_final_feedback(report, events=events)

    pdf_bytes = report_generator.generate_pdf(report)
    filename = f"{session_id}-report.pdf"
    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/interviews/{session_id}/result-email-status")
def get_result_email_status(session_id: str, _: str = Depends(require_admin), repository=Depends(get_repository)):
    status = repository.get_report_email_status(session_id)
    if not status:
        raise HTTPException(status_code=404, detail="Session not found")
    return {
        "session_id": session_id,
        "email_status": status["status"],
        "email_scheduled": status["scheduled"],
        "email_sent": status["sent"],
        "email_error": status["error"],
        "email_updated_at": status["updated_at"],
        "candidate_email": status["candidate_email"],
    }


@router.get("/admin/results")
def admin_list_results(
    search: str = Query(default="", max_length=200),
    status: str = Query(default="", max_length=10),
    limit: int = Query(default=100, ge=1, le=500),
    _: str = Depends(require_admin),
    repository=Depends(get_repository),
):
    results = repository.list_final_reports(search=search, limit=limit, status=status)
    return {
        "count": len(results),
        "results": results,
    }


@router.get("/admin/results/{session_id}")
def admin_get_result(
    session_id: str,
    _: str = Depends(require_admin),
    repository=Depends(get_repository),
):
    record = repository.get_final_report(session_id)
    if not record:
        raise HTTPException(status_code=404, detail="Result not found")
    return record


@router.get("/admin/sessions")
def admin_list_sessions(
    search: str = Query(default="", max_length=200),
    limit: int = Query(default=200, ge=1, le=1000),
    _: str = Depends(require_admin),
    repository=Depends(get_repository),
):
    sessions = repository.list_sessions(search=search, limit=limit)
    return {"count": len(sessions), "sessions": sessions}


@router.get("/admin/users")
def admin_list_users(
    search: str = Query(default="", max_length=200),
    limit: int = Query(default=200, ge=1, le=1000),
    _: str = Depends(require_admin),
    repository=Depends(get_repository),
):
    users = repository.list_users(search=search, limit=limit)
    sessions = repository.list_sessions(search=search, limit=limit)
    return {"count": len(users), "users": users, "sessions": sessions}


@router.get("/admin/sessions/{session_id}")
def admin_get_session_detail(
    session_id: str,
    _: str = Depends(require_admin),
    repository=Depends(get_repository),
):
    detail = repository.admin_session_detail(session_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Session not found")
    return detail


@router.delete("/admin/sessions/{session_id}")
def admin_delete_session(
    session_id: str,
    _: str = Depends(require_admin),
    repository=Depends(get_repository),
):
    result = repository.delete_session_data(session_id)
    if not result.get("deleted"):
        raise HTTPException(status_code=404, detail="Session not found")
    return result


@router.post("/admin/reset-data")
def admin_reset_data(
    _: str = Depends(require_admin),
    repository=Depends(get_repository),
):
    return repository.reset_interview_data()


@router.get("/admin/diagnostics")
def admin_diagnostics(_: str = Depends(require_admin), repository=Depends(get_repository)):
    return repository.event_diagnostics()


@router.get("/admin/reports")
def admin_reports(_: str = Depends(require_admin), repository=Depends(get_repository)):
    return repository.admin_reports()


# Enrollment endpoint for biometric registration
class EnrollmentRequest(BaseModel):
    session_id: str
    username: str
    face_samples: list[str] = []  # base64 encoded images
    voice_samples: list[str] = []  # base64 encoded audio
    timestamp: str = ""


@router.post("/enrollment")
def create_enrollment(
    payload: EnrollmentRequest,
    repository=Depends(get_repository),
):
    """
    Create a new enrollment with biometric samples.
    Processes face and voice samples to create identity embeddings.
    """
    try:
        logger.info("[Enrollment] Starting enrollment for session %s, user %s", 
                   payload.session_id, payload.username)
        
        # Store enrollment data
        enrollment_data = {
            "session_id": payload.session_id,
            "username": payload.username,
            "face_samples_count": len(payload.face_samples),
            "voice_samples_count": len(payload.voice_samples),
            "timestamp": payload.timestamp,
            "status": "enrolled"
        }
        
        # Register with identity verifier if face samples exist
        face_embedding = None
        if payload.face_samples:
            try:
                # Process first face sample for registration
                from app.proctoring.detectors import decode_base64_image
                import numpy as np
                
                frame = decode_base64_image(payload.face_samples[0].split(",")[-1])
                face_embedding, face_box = identity_verifier._extract_face_embedding(frame)
                
                if face_embedding is not None:
                    identity_verifier.register_user(
                        session_id=payload.session_id,
                        username=payload.username,
                        face_embedding=face_embedding.tolist() if isinstance(face_embedding, np.ndarray) else face_embedding,
                        voice_embedding=None
                    )
                    logger.info("[Enrollment] Face embedding registered for %s", payload.session_id)
                else:
                    logger.warning("[Enrollment] No face detected in enrollment sample")
                    
            except Exception as e:
                logger.error("[Enrollment] Face processing error: %s", e)
        
        # Store in repository
        repository.create_enrollment(enrollment_data)
        
        logger.info("[Enrollment] Completed successfully for %s", payload.session_id)
        
        return {
            "status": "success",
            "session_id": payload.session_id,
            "username": payload.username,
            "face_registered": face_embedding is not None,
            "message": "Enrollment completed successfully"
        }
        
    except Exception as e:
        logger.error("[Enrollment] Failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Enrollment failed: {str(e)}")
