from io import BytesIO

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from app.dependencies import get_repository
from app.email_service import send_report_email_async
from app.models import DomainInterviewStart, InterviewAnswerRequest
from app.services.ai_evaluator import evaluator
from app.services.keyword_matcher import keyword_matcher
from app.services.question_extractor import question_extractor
from app.services.report_generator import report_generator
from app.services.resume_parser import resume_parser
from app.services.voice_handler import voice_handler


router = APIRouter(tags=["interviews"])


def maybe_email_report(session_id: str, repository) -> None:
    session = repository.get_session(session_id)
    if not session or repository.report_email_sent(session_id):
        return

    candidate_email = (session.get("candidate_email") or "").strip()
    if not candidate_email:
        return

    report = repository.build_report(session_id, evaluator.summarize_report)
    if not report:
        return

    send_report_email_async(
        report,
        on_success=lambda: repository.mark_report_email_sent(session_id, True),
    )


@router.post("/interviews/domain/start")
async def start_domain_interview(
    payload: DomainInterviewStart,
    repository=Depends(get_repository),
):
    questions = evaluator.generate_domain_questions(payload.domain, count=5)
    session = repository.create_session(
        candidate_name=payload.candidate_name,
        candidate_email=payload.candidate_email.strip(),
        mode="domain",
        metadata={"domain": payload.domain},
        questions=questions,
    )
    greeting = voice_handler.build_greeting(payload.candidate_name, payload.domain)
    repository.update_session_greeting(session["session_id"], greeting)
    return repository.build_session_view(session["session_id"])


@router.post("/interviews/resume/start")
async def start_resume_interview(
    candidate_name: str = Form(...),
    candidate_email: str = Form(""),
    resume_file: UploadFile = File(...),
    repository=Depends(get_repository),
):
    content = await resume_file.read()
    parsed_resume = resume_parser.parse_resume(content, resume_file.filename or "resume.pdf")
    questions = evaluator.generate_resume_questions(parsed_resume, count=5)
    session = repository.create_session(
        candidate_name=candidate_name,
        candidate_email=candidate_email.strip(),
        mode="resume",
        metadata=parsed_resume,
        questions=questions,
    )
    greeting = voice_handler.build_greeting(candidate_name, "your resume")
    repository.update_session_greeting(session["session_id"], greeting)
    return repository.build_session_view(session["session_id"])


@router.post("/interviews/company/start")
async def start_company_interview(
    candidate_name: str = Form(...),
    candidate_email: str = Form(""),
    evaluation_mode: str = Form(...),
    question_file: UploadFile = File(...),
    repository=Depends(get_repository),
):
    content = await question_file.read()
    if evaluation_mode not in {"ai", "keyword"}:
        raise HTTPException(status_code=400, detail="evaluation_mode must be 'ai' or 'keyword'")

    try:
        parsed = question_extractor.extract_company_questions(
            content=content,
            filename=question_file.filename or "questions.txt",
            evaluation_mode=evaluation_mode,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not parsed:
        if evaluation_mode == "ai":
            detail = "No valid questions were found in the uploaded company file."
        else:
            detail = "No valid Question + Keywords pairs were found in the uploaded company file."
        raise HTTPException(status_code=400, detail=detail)

    mode = "company-ai" if evaluation_mode == "ai" else "company-keyword"
    session = repository.create_session(
        candidate_name=candidate_name,
        candidate_email=candidate_email.strip(),
        mode=mode,
        metadata={
            "source_filename": question_file.filename,
            "question_count": len(parsed),
        },
        questions=parsed,
    )
    repository.store_company_questions(session["session_id"], parsed)
    greeting = voice_handler.build_greeting(candidate_name, "the company interview")
    repository.update_session_greeting(session["session_id"], greeting)
    return repository.build_session_view(session["session_id"])


@router.get("/interviews/{session_id}")
def get_session(session_id: str, repository=Depends(get_repository)):
    view = repository.build_session_view(session_id)
    if not view:
        raise HTTPException(status_code=404, detail="Session not found")
    return view


@router.post("/interviews/{session_id}/answer")
def submit_answer(
    session_id: str,
    payload: InterviewAnswerRequest,
    repository=Depends(get_repository),
):
    session = repository.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session["status"] == "completed":
        raise HTTPException(status_code=400, detail="Interview already completed")

    question = repository.get_current_question(session_id)
    if not question:
        raise HTTPException(status_code=400, detail="No active question")

    normalized_answer = voice_handler.normalize_transcript(payload.answer_text)
    if session["mode"] == "company-keyword":
        evaluation = keyword_matcher.evaluate_answer(
            normalized_answer,
            question.get("expected_keywords", []),
            question["question"],
        )
    else:
        evaluation = evaluator.evaluate_answer(
            question=question["question"],
            answer=normalized_answer,
            context={
                "mode": session["mode"],
                "metadata": session.get("metadata", {}),
            },
        )

    repository.record_answer(session_id, question, normalized_answer, evaluation)
    repository.advance_session(session_id)
    next_question = repository.get_current_question(session_id)
    if next_question is None:
        maybe_email_report(session_id, repository)

    return {
        "session_id": session_id,
        "completed": next_question is None,
        "next_question": next_question,
        "evaluation": evaluation,
        "answered_index": session["current_index"] + 1,
    }


@router.get("/interviews/{session_id}/report")
def get_report(session_id: str, repository=Depends(get_repository)):
    report = repository.build_report(session_id, evaluator.summarize_report)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    if not repository.report_email_sent(session_id):
        maybe_email_report(session_id, repository)
    return report


@router.get("/interviews/{session_id}/report/pdf")
def download_report_pdf(session_id: str, repository=Depends(get_repository)):
    report = repository.build_report(session_id, evaluator.summarize_report)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    pdf_bytes = report_generator.generate_pdf(report)
    filename = f"{session_id}-report.pdf"
    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
