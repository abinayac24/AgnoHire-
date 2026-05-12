import requests
import time
import random
import secrets
import datetime
import os
import re
import csv
import PyPDF2
import io
import logging
import threading
import smtplib
import html
import numpy as np
from datetime import timedelta
from email.message import EmailMessage
from email.utils import formataddr
from functools import wraps

from bson import ObjectId
from flask import (
    Flask,
    abort,
    jsonify,
    render_template,
    request,
    redirect,
    url_for,
    session,
    send_file,
)
from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import PyMongoError
from reportlab.pdfgen import canvas
from database.mongo import db_manager
from werkzeug.security import check_password_hash
from voice_password import (
    analyze_interview_voice,
    authenticate_voice_profile,
    average_embeddings,
    cleanup_file,
    delete_voice_profile,
    extract_voice_embedding,
    get_voice_profile,
    get_voice_profile_stats,
    get_voice_profile_with_auth_logs,
    init_voice_password_store,
    list_all_voice_profiles,
    log_voice_verification,
    reset_voice_profile_for_reregistration,
    save_uploaded_voice_sample,
    save_voice_profile,
    update_voice_profile_metadata,
    voice_user_exists,
)
from backend.app.proctoring.config import settings as proctoring_settings
SentenceTransformer = None
util = None
_sentence_transformers_import_attempted = False

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-pro")

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret-key-change-me")
app.logger.setLevel(logging.INFO)
app.permanent_session_lifetime = timedelta(minutes=max(15, int(os.getenv("ADMIN_SESSION_MINUTES", "120"))))

MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
MONGODB_DB_NAME = os.getenv("MONGODB_DB_NAME", "ai_interview_system")
MAX_WARNINGS = 3
REQUEST_TIMEOUT = 10
SENTENCE_TRANSFORMER_MODEL = os.getenv(
    "SENTENCE_TRANSFORMER_MODEL",
    "sentence-transformers/all-MiniLM-L6-v2",
)
RESULT_EMAIL_DELAY_SECONDS = int(os.getenv("RESULT_EMAIL_DELAY_SECONDS", "300"))
SMTP_HOST = os.getenv("SMTP_HOST", os.getenv("SMTP_SERVER", ""))
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME", os.getenv("SMTP_EMAIL", ""))
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "true").lower() == "true"
EMAIL_SENDER = os.getenv("EMAIL_SENDER", SMTP_USERNAME)
FASTAPI_BASE_URL = os.getenv("FASTAPI_BASE_URL", "http://127.0.0.1:8000/api")
SPEECH_SERVICE_URL = os.getenv("SPEECH_SERVICE_URL", "http://127.0.0.1:9000")
INTERVIEWER_IMAGE_URL = os.getenv("INTERVIEWER_IMAGE_URL", "")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", ADMIN_USERNAME)
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")
ADMIN_PASSWORD_HASH = os.getenv("ADMIN_PASSWORD_HASH", "")
REQUIRE_VOICE_PASSWORD = os.getenv("REQUIRE_VOICE_PASSWORD", "true").lower() == "true"
VOICE_INTERVIEW_MAX_VIOLATIONS = int(os.getenv("VOICE_INTERVIEW_MAX_VIOLATIONS", "3"))
SECURITY_MAX_WARNINGS = int(os.getenv("SECURITY_MAX_WARNINGS", str(MAX_WARNINGS)))
VOICE_LOGIN_RECORD_SECONDS = int(os.getenv("VOICE_LOGIN_RECORD_SECONDS", "7"))
VOICE_REGISTER_RECORD_SECONDS = int(os.getenv("VOICE_REGISTER_RECORD_SECONDS", "5"))
VOICE_AUTH_TRANSCRIBE_TIMEOUT = int(os.getenv("VOICE_AUTH_TRANSCRIBE_TIMEOUT", "90"))
VOICE_CHALLENGE_PASSAGE_THRESHOLD = float(os.getenv("VOICE_CHALLENGE_PASSAGE_THRESHOLD", "0.55"))
STT_CONFIDENCE_THRESHOLD = float(os.getenv("STT_CONFIDENCE_THRESHOLD", "-0.95"))
SILENCE_TIMEOUT_MS = int(os.getenv("SILENCE_TIMEOUT_MS", "1400"))
VAD_SPEECH_THRESHOLD = float(os.getenv("VAD_SPEECH_THRESHOLD", "0.018"))
AUDIO_BUFFER_MS = int(os.getenv("AUDIO_BUFFER_MS", "1000"))

VOICE_REGISTRATION_PASSAGES = [
    "Today I am registering my secure interview voice profile with a calm and natural tone.",
    "My voice confirms my identity while I answer questions in a quiet interview setting.",
    "I will speak clearly, steadily, and honestly during every AI interview session.",
    "This enrollment sample helps the system learn my normal speaking rhythm and sound.",
    "I understand that my registered voice protects interview access and candidate integrity.",
]

VOICE_LOGIN_CHALLENGE_SENTENCES = [
    # Technology & Computing
    "The quick brown fox jumps over the lazy dog while the programmer debugs code.",
    "Machine learning algorithms improve with more data and careful parameter tuning.",
    "Cloud computing enables scalable applications without managing physical hardware.",
    "Cybersecurity requires constant vigilance against evolving digital threats daily.",
    "Artificial intelligence transforms how we solve complex real world problems.",
    "Database optimization ensures fast queries even with millions of records stored.",
    "Version control systems help teams collaborate on software projects effectively.",
    "API integration connects different services into seamless user experiences.",
    "Responsive design makes websites work beautifully across all device sizes.",
    "Continuous deployment automates the delivery of tested software to production.",
    # General Knowledge
    "The scientific method relies on observation hypothesis testing and conclusion.",
    "Renewable energy sources reduce our dependence on fossil fuel consumption.",
    "Critical thinking skills help distinguish facts from misleading information.",
    "Effective communication bridges gaps between diverse teams and cultures.",
    "Time management prioritizes important tasks over merely urgent demands.",
    "Active listening demonstrates respect and builds stronger relationships.",
    "Adaptability allows professionals to thrive in rapidly changing industries.",
    "Data driven decisions outperform gut feelings in most business scenarios.",
    "Collaboration multiplies individual strengths into collective achievements.",
    "Attention to detail separates good work from truly excellent results.",
    # Interview Context
    "Preparation before an interview increases confidence and response quality.",
    "Clear articulation helps interviewers understand your actual capabilities.",
    "Professional integrity matters more than short term success or gains.",
    "Technical depth combined with soft skills creates the best candidates.",
    "Problem solving approach reveals more than memorized facts or answers.",
    "Growth mindset embraces challenges as opportunities to learn and improve.",
    "Work ethic determines long term success more than raw talent alone.",
    "Teamwork skills enable complex projects that no individual could complete.",
    "Curiosity drives the continuous learning that technology careers require.",
    "Accountability means owning both successes and failures with equal grace.",
]

mongo_client = None
mongo_db = None
sentence_model = None
TECHNICAL_TERM_CORRECTIONS = {
    "encapsulation": [
        "in capsule ation",
        "encapsulasion",
        "encapsolation",
        "encapsulations",
        "incapsulation",
        "encapsuation",
        "encapsulaton",
    ],
    "inheritance": [
        "in heritance",
        "inheritence",
        "inneritance",
        "inheritanc",
        "ineritance",
        "inheretance",
    ],
    "polymorphism": [
        "poly morphism",
        "polly morphism",
        "polymorfism",
        "polimorphism",
        "polymorphysm",
        "polymorphim",
    ],
    "REST API": [
        "rest ap i",
        "rest a p i",
        "restapi",
        "rest a p eye",
    ],
    "microservices": [
        "micro services",
        "microservice",
        "micro service",
        "microservice is",
        "microservis",
    ],
    "API": [
        "a p i",
        "ap i",
        "a p eye",
    ],
    "database": [
        "data base",
        "data bases",
        "databace",
    ],
    "algorithm": [
        "algo rhythm",
        "algo rithm",
        "algoritm",
        "algorythm",
    ],
    "framework": [
        "frame work",
        "frame werk",
        "framwork",
    ],
}


# =========================
# DATABASE CONNECTION
# =========================
def get_db():
    global mongo_client, mongo_db

    if mongo_db is not None:
        return mongo_db
    
    # Check if we should skip MongoDB
    if os.getenv("USE_IN_MEMORY_DB", "false").lower() == "true":
        return None

    try:
        mongo_client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=3000)
        mongo_client.admin.command("ping")
        mongo_db = mongo_client[MONGODB_DB_NAME]
        return mongo_db
    except Exception as e:
        app.logger.warning(f"MongoDB not available: {e}")
        return None


# =========================
# DATABASE INITIALIZATION
# =========================
def init_db():
    db = get_db()
    if db is None:
        init_voice_password_store(None)
        app.logger.info("Running without MongoDB - using in-memory mode")
        return

    try:
        db.questions.create_index("domain")
        db.candidates.create_index([("created_at", -1)])
        init_voice_password_store(db)
        app.logger.info("MongoDB initialized successfully")
    except Exception as e:
        app.logger.warning(f"MongoDB initialization failed: {e}")


def serialize_mongo_doc(document):

    if not document:
        return document

    doc = dict(document)
    if "_id" in doc:
        doc["id"] = str(doc.pop("_id"))
    return doc


def sync_fastapi_session(candidate_name, candidate_email, mode, metadata, questions, greeting=""):

    normalized_questions = []
    for item in questions[:5]:
        normalized_questions.append(
            {
                "question": item.get("question", ""),
                "expected_keywords": item.get("expected_keywords", item.get("keywords", [])),
                "source": item.get("source", "legacy-flask"),
            }
        )

    payload = {
        "candidate_name": candidate_name,
        "candidate_email": (candidate_email or "").strip(),
        "mode": mode,
        "metadata": metadata or {},
        "questions": normalized_questions,
        "greeting": greeting or "",
    }
    endpoint = f"{FASTAPI_BASE_URL}/interviews/legacy/start"
    response = requests.post(endpoint, json=payload, timeout=REQUEST_TIMEOUT)
    if not response.ok:
        app.logger.error("Failed to create FastAPI session: %s %s", response.status_code, response.text)
        raise RuntimeError("Could not start interview session. Please restart the services and try again.")

    data = response.json()
    return data.get("session_id")



def require_admin_auth():
    return session.get('admin_logged_in', False) and session.get('user_role') == 'admin'


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('user_role') and session.get('user_role') != 'admin':
            abort(403)
        if not session.get('admin_logged_in'):
            return redirect(url_for('admin_login', next=request.url))
        if session.get('user_role') != 'admin':
            abort(403)
        return f(*args, **kwargs)
    return decorated_function


def voice_password_is_authenticated():
    return bool(session.get("voice_password_authenticated"))


def voice_password_required_redirect():
    if not REQUIRE_VOICE_PASSWORD or voice_password_is_authenticated():
        return None
    return redirect(url_for("voice_password_login", next=request.url, notice="voice-required"))


def auth_required_redirect():
    """
    Ensures Voice auth is satisfied if required.
    """
    voice_guard = voice_password_required_redirect()
    if voice_guard:
        return voice_guard

    return None


def security_level_for_count(count: int) -> str:
    if count <= 1:
        return "yellow"
    if count == 2:
        return "orange"
    return "red"


def reset_security_warning_state():
    session["warnings"] = 0
    session["security_warnings"] = 0
    session["security_events"] = []
    session["termination_reason"] = ""


def record_security_warning(rule: str, message: str, details: dict | None = None) -> dict:
    count = int(session.get("security_warnings", session.get("warnings", 0)) or 0) + 1
    session["security_warnings"] = count
    session["warnings"] = count
    level = security_level_for_count(count)
    terminate = count >= SECURITY_MAX_WARNINGS
    termination_reason = message if terminate else ""
    if terminate:
        session["termination_reason"] = termination_reason

    event = {
        "rule": (rule or "proctoring").strip(),
        "message": (message or "Proctoring warning detected.").strip(),
        "count": count,
        "level": level,
        "terminate": terminate,
        "termination_reason": termination_reason,
        "details": dict(details or {}),
        "created_at": datetime.datetime.utcnow().isoformat(),
    }
    events = list(session.get("security_events", []))
    events.append(event)
    session["security_events"] = events[-50:]

    db = get_db()
    try:
        if db is not None:
            db.security_warning_logs.insert_one(
                {
                    **event,
                    "username": session.get("voice_password_username", ""),
                    "session_id": session.get("api_session_id", ""),
                    "candidate_name": session.get("name", ""),
                    "candidate_email": session.get("email", ""),
                }
            )
    except Exception:
        app.logger.debug("Could not write security warning log", exc_info=True)

    return event


def generate_voice_login_challenge() -> dict:
    """
    Generate a fresh voice login challenge with a randomized sentence.
    Uses a large sentence pool to ensure different challenges on each login/retry.
    """
    # Get previous challenge to avoid repeating the same sentence
    previous_challenge = session.get("voice_login_challenge", {})
    previous_sentence = previous_challenge.get("sentence", "")

    # Select a sentence (prefer a different one if possible)
    available_sentences = [s for s in VOICE_LOGIN_CHALLENGE_SENTENCES if s != previous_sentence]
    if not available_sentences:
        available_sentences = VOICE_LOGIN_CHALLENGE_SENTENCES

    new_sentence = random.choice(available_sentences)

    challenge = {
        "sentence": new_sentence,
        "created_at": datetime.datetime.utcnow().isoformat(),
        "previous_sentence": previous_sentence,  # Track for debugging
    }

    # Clear old challenge and store new one
    session.pop("voice_login_challenge", None)
    session["voice_login_challenge"] = challenge

    app.logger.info(
        "[VoiceChallenge] Generated fresh sentence challenge - hash=%s previous_hash=%s",
        hash(new_sentence) % 10000,
        hash(previous_sentence) % 10000 if previous_sentence else "none"
    )
    return challenge


def normalize_voice_challenge_text(value: str) -> str:
    """Normalize text for voice challenge comparison."""
    value = (value or "").lower()
    # Remove punctuation but keep alphanumeric and spaces
    value = re.sub(r"[^a-z0-9\s]", " ", value)
    # Collapse multiple spaces
    return re.sub(r"\s+", " ", value).strip()


def calculate_sentence_similarity(transcript: str, expected_sentence: str) -> float:
    """
    Calculate similarity between spoken transcript and expected sentence.
    Uses token-based matching with tolerance for minor variations.
    """
    transcript_normalized = normalize_voice_challenge_text(transcript)
    expected_normalized = normalize_voice_challenge_text(expected_sentence)

    transcript_tokens = set(transcript_normalized.split())
    expected_tokens = expected_normalized.split()

    if not expected_tokens:
        return 0.0

    # Count matches (tokens that appear in both)
    matched = sum(1 for token in expected_tokens if token in transcript_tokens)

    # Calculate similarity as ratio of matched to expected tokens
    return round(matched / len(expected_tokens), 3)


def sentence_matches_challenge(transcript: str, expected_sentence: str, threshold: float = 0.7) -> tuple[bool, float, dict]:
    """
    Check if transcript reasonably matches the expected challenge sentence.

    Returns:
        (matched: bool, similarity_score: float, details: dict)
    """
    similarity = calculate_sentence_similarity(transcript, expected_sentence)

    # Get normalized versions for debugging
    transcript_normalized = normalize_voice_challenge_text(transcript)
    expected_normalized = normalize_voice_challenge_text(expected_sentence)

    details = {
        "similarity": similarity,
        "threshold": threshold,
        "transcript_normalized": transcript_normalized,
        "expected_normalized": expected_normalized,
        "transcript_tokens": transcript_normalized.split(),
        "expected_tokens": expected_normalized.split(),
    }

    # Check if similarity meets threshold
    matched = similarity >= threshold

    return matched, similarity, details


def passage_match_score(transcript: str, expected_passage: str) -> float:
    transcript_tokens = set(normalize_voice_challenge_text(transcript).split())
    expected_tokens = [
        token
        for token in normalize_voice_challenge_text(expected_passage).split()
        if len(token) >= 3
    ]
    if not expected_tokens:
        return 0.0
    matched = sum(1 for token in expected_tokens if token in transcript_tokens)
    return round(matched / len(expected_tokens), 3)


def transcribe_voice_challenge(audio_path: str, context_text: str) -> str:
    endpoint = f"{SPEECH_SERVICE_URL.rstrip('/')}/transcribe"
    with open(audio_path, "rb") as audio_file:
        response = requests.post(
            endpoint,
            files={"audio": ("voice-login.wav", audio_file, "audio/wav")},
            data={"context_question": context_text or ""},
            timeout=VOICE_AUTH_TRANSCRIBE_TIMEOUT,
        )
    if not response.ok:
        detail = response.text
        try:
            detail = response.json().get("detail", detail)
        except Exception:
            pass
        raise ValueError(f"Voice challenge transcription failed: {detail}")
    return (response.json().get("text") or "").strip()


def validate_voice_login_challenge(audio_path: str) -> dict:
    """
    Validate the voice login challenge by verifying the spoken sentence matches.
    Uses tolerant matching to allow minor variations in speech transcription.
    Includes comprehensive debug logging for troubleshooting.
    """
    challenge = session.get("voice_login_challenge") or {}
    expected_sentence = str(challenge.get("sentence", "")).strip()

    # Debug logging: Challenge details
    app.logger.info(
        "[VoiceChallenge] Validation started - expected_sentence_hash=%s, session_id=%s",
        hash(expected_sentence) % 10000 if expected_sentence else "none",
        session.get("api_session_id", "unknown")[:8] if session.get("api_session_id") else "none"
    )

    if not expected_sentence:
        app.logger.error("[VoiceChallenge] Challenge expired or missing - no sentence in session")
        raise ValueError("Voice challenge expired. Reload the login page and try again.")

    # Transcribe with context hint for better accuracy
    context_hint = f"Read this sentence aloud: {expected_sentence}"
    transcript = transcribe_voice_challenge(audio_path, context_hint)

    # Debug logging: Raw transcript
    app.logger.info("[VoiceChallenge] Raw transcript received: %r", transcript)

    # Use tolerant sentence matching
    sentence_match, similarity, match_details = sentence_matches_challenge(
        transcript, expected_sentence, threshold=0.6
    )

    # Debug logging with all matching details
    app.logger.info(
        "[VoiceChallenge] Matching result - expected_hash=%s, "
        "raw_transcript=%r, similarity=%.3f, threshold=%.3f, matched=%s",
        hash(expected_sentence) % 10000,
        transcript,
        similarity,
        match_details["threshold"],
        sentence_match,
    )

    # Detailed debug logging of token matching
    app.logger.debug(
        "[VoiceChallenge] Token analysis - expected_tokens=%s, transcript_tokens=%s",
        match_details["expected_tokens"],
        match_details["transcript_tokens"]
    )

    if not sentence_match:
        app.logger.warning(
            "[VoiceChallenge] Sentence mismatch - similarity=%.3f below threshold=%.3f",
            similarity,
            match_details["threshold"]
        )

        # Provide helpful error message
        spoken_preview = transcript[:60] + "..." if len(transcript) > 60 else transcript
        raise ValueError(
            f"Your speech did not match the challenge sentence. "
            f"Similarity: {int(similarity * 100)}%. "
            f"Heard: '{spoken_preview}'. "
            f"Please read the displayed sentence clearly and try again."
        )

    # Success - log and return
    app.logger.info(
        "[VoiceChallenge] Validation successful - similarity=%.3f, threshold=%.3f",
        similarity,
        match_details["threshold"]
    )

    return {
        "transcript": transcript,
        "expected_sentence": expected_sentence,
        "similarity_score": similarity,
        "threshold": match_details["threshold"],
        "matched": sentence_match,
        "normalized_transcript": match_details["transcript_normalized"],
    }




def reset_voice_interview_state():
    session["voice_violation_count"] = 0
    session["voice_suspicious"] = False
    session["voice_last_warning"] = ""


def record_voice_violation(message: str) -> tuple[int, bool]:
    count = int(session.get("voice_violation_count", 0) or 0) + 1
    session["voice_violation_count"] = count
    session["voice_last_warning"] = (message or "").strip()[:300]
    suspicious = count >= max(2, VOICE_INTERVIEW_MAX_VIOLATIONS - 1)
    if suspicious:
        session["voice_suspicious"] = True
    security_event = record_security_warning(
        "voice_identity",
        message or "Voice identity warning",
        {"voice_violation_count": count},
    )
    terminate_recommended = bool(security_event.get("terminate")) or count >= VOICE_INTERVIEW_MAX_VIOLATIONS
    return int(security_event.get("count", count)), terminate_recommended


def normalize_login_identifier(value):
    return (value or "").strip().lower()


def sync_admin_user_record():
    db = get_db()
    if db is None:
        return
    admin_identifier = normalize_login_identifier(ADMIN_EMAIL or ADMIN_USERNAME)
    if not admin_identifier:
        return
    db.users.update_one(
        {"email": admin_identifier},
        {
            "$set": {
                "name": "System Administrator",
                "email": admin_identifier,
                "username": ADMIN_USERNAME,
                "role": "admin",
                "updated_at": datetime.datetime.utcnow(),
            },
            "$setOnInsert": {
                "created_at": datetime.datetime.utcnow(),
            },
        },
        upsert=True,
    )


def verify_admin_credentials(login_identifier, password):
    normalized = normalize_login_identifier(login_identifier)
    allowed = {
        normalize_login_identifier(ADMIN_USERNAME),
        normalize_login_identifier(ADMIN_EMAIL),
    }
    if normalized not in {item for item in allowed if item}:
        return False
    if ADMIN_PASSWORD_HASH:
        return check_password_hash(ADMIN_PASSWORD_HASH, password or "")
    return password == ADMIN_PASSWORD


def get_admin_api_auth():
    return (ADMIN_USERNAME, ADMIN_PASSWORD)


def fetch_admin_api_request(method, path, params=None):
    response = requests.request(
        method=method,
        url=f"{FASTAPI_BASE_URL}{path}",
        params=params,
        auth=get_admin_api_auth(),
        timeout=REQUEST_TIMEOUT,
    )
    payload = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
    return response, payload


def fetch_admin_api(path, params=None):
    return fetch_admin_api_request("GET", path, params=params)


def normalize_question_score(value):
    try:
        numeric = float(value or 0)
    except (TypeError, ValueError):
        numeric = 0.0
    if numeric > 10:
        numeric = numeric / 10.0
    return max(0, min(10, int(round(numeric))))


def performance_label_from_total(total_score):
    if total_score >= 40:
        return "Excellent"
    if total_score >= 30:
        return "Good"
    if total_score >= 20:
        return "Average"
    return "Needs Improvement"


def normalize_admin_result_record(record):
    if not isinstance(record, dict):
        return {}

    items = record.get("items") or record.get("report", {}).get("items") or []
    safe_items = []
    for index, item in enumerate(items[:5], start=1):
        if not isinstance(item, dict):
            continue
        safe_items.append(
            {
                "question_id": item.get("question_id", ""),
                "question_number": item.get("question_number", index),
                "question": item.get("question", ""),
                "answer": item.get("answer", item.get("user_answer", "")),
                "score": normalize_question_score(item.get("score", 0)),
                "max_score": int(item.get("max_score", 10) or 10),
                "feedback": item.get("feedback", ""),
                "improvement_suggestion": item.get("improvement_suggestion", ""),
            }
        )

    total_score = record.get("total_score")
    if total_score is None:
        total_score = sum(item.get("score", 0) for item in safe_items)
    try:
        total_score = int(total_score or 0)
    except (TypeError, ValueError):
        total_score = 0
    total_score = max(0, min(total_score, 50))

    question_scores = record.get("question_scores") or [
        {
            "question_id": item.get("question_id", ""),
            "question_number": item.get("question_number", index),
            "score": item.get("score", 0),
            "max_score": item.get("max_score", 10),
        }
        for index, item in enumerate(safe_items, start=1)
    ]
    safe_question_scores = [
        {
            "question_id": item.get("question_id", ""),
            "question_number": item.get("question_number", index),
            "score": normalize_question_score(item.get("score", 0)),
            "max_score": int(item.get("max_score", 10) or 10),
        }
        for index, item in enumerate(question_scores[:5], start=1)
        if isinstance(item, dict)
    ]

    return {
        **record,
        "candidate_name": record.get("candidate_name", ""),
        "candidate_email": record.get("candidate_email", ""),
        "scores": record.get("scores") or {},
        "ai_feedback_report": record.get("ai_feedback_report") or record.get("report", {}).get("ai_feedback_report") or {},
        "strengths": record.get("strengths") or [],
        "weaknesses": record.get("weaknesses") or [],
        "alerts": record.get("alerts") or [],
        "final_feedback": record.get("final_feedback", ""),
        "items": safe_items,
        "question_scores": safe_question_scores,
        "total_score": total_score,
        "overall_score": int(record.get("overall_score", round((total_score / 50) * 100)) or 0),
        "performance_label": record.get("performance_label") or performance_label_from_total(total_score),
        "result_status": "PASS" if total_score >= 25 else "FAIL",
    }


@app.errorhandler(403)
def forbidden(_error):
    return render_template("403.html"), 403


# =========================
# API ADMIN AUTHENTICATION
# =========================
@app.route("/api/admin/login", methods=["POST"])
def api_admin_login():
    data = request.get_json() or {}
    username = data.get("username", data.get("email", "")).strip()
    password = data.get("password", "").strip()
    
    if verify_admin_credentials(username, password):
        sync_admin_user_record()
        session.permanent = True
        session['admin_logged_in'] = True
        session['admin_username'] = ADMIN_USERNAME
        session['admin_email'] = ADMIN_EMAIL
        session['user_role'] = 'admin'
        return jsonify({"success": True, "role": "admin", "redirect": "/admin"})
    else:
        return jsonify({"success": False, "error": "Invalid credentials"}), 401


@app.route("/api/admin/logout", methods=["POST"])
def api_admin_logout():
    session.pop('admin_logged_in', None)
    session.pop('admin_username', None)
    session.pop('admin_email', None)
    session.pop('user_role', None)
    return jsonify({"success": True})


def get_sentence_model():
    global sentence_model, SentenceTransformer, util, _sentence_transformers_import_attempted

    if not _sentence_transformers_import_attempted and SentenceTransformer is None:
        _sentence_transformers_import_attempted = True
        try:
            from sentence_transformers import SentenceTransformer as _SentenceTransformer, util as _util
            SentenceTransformer = _SentenceTransformer
            util = _util
            app.logger.info("sentence_transformers loaded lazily")
        except ImportError:
            SentenceTransformer = None
            util = None
            app.logger.warning("sentence_transformers is unavailable; semantic scoring fallback will be used")

    if sentence_model is None and SentenceTransformer is not None:
        sentence_model = SentenceTransformer(SENTENCE_TRANSFORMER_MODEL)

    return sentence_model


def apply_technical_corrections(text):

    corrected = text or ""
    for canonical, variants in TECHNICAL_TERM_CORRECTIONS.items():
        for variant in variants:
            corrected = re.sub(
                rf"\b{re.escape(variant)}\b",
                canonical,
                corrected,
                flags=re.IGNORECASE,
            )
    corrected = re.sub(r"\s+", " ", corrected).strip()
    return corrected


def build_recruiter_summary(questions, answers, feedback_items, percentage, result_status):

    try:
        prompt = f"""
You are an AI recruiter assistant.
Based on this interview performance, create a concise recruiter summary.

Overall Score: {percentage}%
Final Result: {result_status}

Questions and answers:
{chr(10).join([f"Q: {q['question']}{chr(10)}A: {answers[i] if i < len(answers) else 'No answer'}{chr(10)}Feedback: {feedback_items[i] if i < len(feedback_items) else ''}" for i, q in enumerate(questions)])}

Return exactly in this format:
Communication Level: <Low/Moderate/High>
Technical Confidence: <Low/Moderate/High>
Strengths: <short sentence>
Weaknesses: <short sentence>
Hiring Recommendation: <Hire/Consider/Needs Improvement>
"""
        summary_text = call_gemini(prompt, timeout=10)
        lines = [line.strip() for line in summary_text.splitlines() if ":" in line]
        parsed = {}
        for line in lines:
            key, value = line.split(":", 1)
            parsed[key.strip().lower()] = value.strip()
        if parsed:
            return {
                "communication_level": parsed.get("communication level", "Moderate"),
                "technical_confidence": parsed.get("technical confidence", "Moderate"),
                "strengths": parsed.get("strengths", "Shows reasonable understanding of core concepts."),
                "weaknesses": parsed.get("weaknesses", "Needs more depth and clearer examples in some answers."),
                "hiring_recommendation": parsed.get("hiring recommendation", "Consider"),
            }
    except Exception as exc:
        app.logger.warning("Recruiter summary fallback used: %s", exc)

    answered_count = sum(1 for answer in answers if (answer or "").strip() not in {"", "NO_ANSWER", "SKIPPED"})
    avg_answer_words = 0
    if answers:
        avg_answer_words = sum(len((answer or "").split()) for answer in answers) / len(answers)

    if avg_answer_words >= 20:
        communication_level = "High"
    elif avg_answer_words >= 8:
        communication_level = "Moderate"
    else:
        communication_level = "Low"

    if percentage >= 75:
        technical_confidence = "High"
        recommendation = "Hire"
    elif percentage >= 55:
        technical_confidence = "Moderate"
        recommendation = "Consider"
    else:
        technical_confidence = "Low"
        recommendation = "Needs Improvement"

    return {
        "communication_level": communication_level,
        "technical_confidence": technical_confidence,
        "strengths": f"Answered {answered_count} questions with an overall score of {percentage}%.",
        "weaknesses": "Needs sharper technical depth and more structured examples in weaker responses.",
        "hiring_recommendation": recommendation,
    }


def wrap_pdf_text(text, max_chars=95):

    words = (text or "").split()
    if not words:
        return [""]

    lines = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        if len(candidate) <= max_chars:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def ensure_pdf_space(pdf, y, required_height):

    if y > required_height:
        return y

    pdf.showPage()
    return 780


def generate_detailed_report_pdf(candidate_name, interview_domain, percentage, result_status, feedback, recruiter_summary):

    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer)
    y = 780
    page_width = 595

    status_color = (0.10, 0.64, 0.33) if result_status == "Pass" else (0.86, 0.18, 0.18)

    pdf.setFillColorRGB(0.06, 0.12, 0.24)
    pdf.roundRect(36, 730, 523, 70, 14, fill=1, stroke=0)
    pdf.setFillColorRGB(1, 1, 1)
    pdf.setFont("Helvetica-Bold", 18)
    pdf.drawString(54, 772, "AgnoHire AI Interview Report")
    pdf.setFont("Helvetica", 10)
    pdf.drawString(54, 752, f"Generated on {datetime.date.today()} for recruiter review")

    pdf.setFillColorRGB(*status_color)
    pdf.roundRect(445, 746, 92, 28, 10, fill=1, stroke=0)
    pdf.setFillColorRGB(1, 1, 1)
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawCentredString(491, 756, result_status.upper())
    y = 706

    pdf.setFillColorRGB(0.07, 0.10, 0.16)
    pdf.roundRect(36, y - 68, 523, 58, 12, fill=0, stroke=1)
    pdf.setFont("Helvetica", 11)
    pdf.drawString(54, y - 24, f"Candidate Name: {candidate_name}")
    pdf.drawString(54, y - 44, f"Interview Type: {interview_domain}")
    pdf.drawString(300, y - 24, f"Overall Score: {percentage}%")
    pdf.drawString(300, y - 44, f"Hiring Recommendation: {recruiter_summary.get('hiring_recommendation', 'Consider')}")
    y -= 92

    pdf.setFillColorRGB(0.95, 0.97, 1.0)
    pdf.roundRect(36, y - 112, 523, 102, 12, fill=1, stroke=0)
    pdf.setFillColorRGB(0.07, 0.10, 0.16)
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(50, y - 8, "AI Recruiter Summary")
    y -= 22

    pdf.setFont("Helvetica", 10)
    summary_lines = [
        f"Communication Level: {recruiter_summary.get('communication_level', 'Moderate')}",
        f"Technical Confidence: {recruiter_summary.get('technical_confidence', 'Moderate')}",
        f"Strengths: {recruiter_summary.get('strengths', '')}",
        f"Weaknesses: {recruiter_summary.get('weaknesses', '')}",
        f"Hiring Recommendation: {recruiter_summary.get('hiring_recommendation', 'Consider')}",
    ]
    for line in summary_lines:
        for wrapped in wrap_pdf_text(line, max_chars=85):
            pdf.drawString(50, y - 6, wrapped)
            y -= 15

    y -= 14
    y = ensure_pdf_space(pdf, y, 130)

    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(50, y, "Detailed Feedback")
    y -= 22

    for index, item in enumerate(feedback, start=1):
        lines = wrap_pdf_text(item, max_chars=88)
        block_height = 32 + (len(lines) * 14)
        y = ensure_pdf_space(pdf, y, block_height + 70)

        pdf.setFillColorRGB(0.98, 0.98, 0.99)
        pdf.roundRect(42, y - block_height + 6, 510, block_height, 10, fill=1, stroke=0)
        pdf.setFillColorRGB(0.07, 0.10, 0.16)
        pdf.setFont("Helvetica-Bold", 11)
        pdf.drawString(54, y - 14, f"Question {index}")
        pdf.setFont("Helvetica", 10)
        line_y = y - 32
        for line in lines:
            pdf.drawString(54, line_y, line)
            line_y -= 14
        y -= block_height + 10

    y = ensure_pdf_space(pdf, y, 90)
    pdf.setFillColorRGB(0.06, 0.12, 0.24)
    pdf.line(36, 48, page_width - 36, 48)
    pdf.setFillColorRGB(0.35, 0.40, 0.48)
    pdf.setFont("Helvetica", 9)
    pdf.drawString(36, 34, "AI-generated interview summary for recruiter reference")

    pdf.save()
    buffer.seek(0)
    return buffer.getvalue()


def send_result_email(candidate_email, candidate_name, percentage, result_status, interview_domain, feedback, recruiter_summary):

    if not candidate_email:
        return

    if not SMTP_HOST or not SMTP_USERNAME or not SMTP_PASSWORD or not EMAIL_SENDER:
        app.logger.warning("Result email skipped because SMTP settings are incomplete.")
        return

    passed = str(result_status).strip().lower() == "pass"
    subject = "Congratulations! You Passed the Interview" if passed else "Interview Result - Thank You for Attending"
    status_bg = "#16a34a" if result_status == "Pass" else "#dc2626"
    if passed:
        body = (
            f"Hello {candidate_name},\n\n"
            "Thank you for attending the interview.\n"
            "Congratulations! You have successfully passed the interview.\n\n"
            f"Total Score: {percentage}%\n\n"
            "Positive Feedback:\n"
            + "\n".join(f"- {item}" for item in (feedback or []))
            + "\n\nWe will contact you regarding the next steps.\n"
        )
        html_feedback = "".join(
            f"<li style='margin-bottom:10px;'>{html.escape(item)}</li>"
            for item in (feedback or [])
        )
        html_body = f"""
        <html>
          <body style="margin:0;padding:24px;background:#eef4ff;font-family:Segoe UI,Arial,sans-serif;color:#0f172a;">
            <div style="max-width:720px;margin:0 auto;background:#ffffff;border-radius:18px;overflow:hidden;border:1px solid #dbe3ef;">
              <div style="background:#0f172a;padding:24px 28px;color:#ffffff;">
                <div style="font-size:22px;font-weight:700;">Congratulations!</div>
              </div>

              <div style="padding:28px;">
                <p style="margin-top:0;font-size:16px;">Hello <strong>{html.escape(candidate_name)}</strong>,</p>
                <p>Thank you for attending the interview.</p>
                <p><strong>Congratulations! You have successfully passed the interview.</strong></p>

                <div style="display:flex;gap:12px;flex-wrap:wrap;margin:22px 0;">
                  <div style="padding:14px 18px;border-radius:14px;background:#f8fafc;border:1px solid #dbe3ef;">
                    <div style="font-size:12px;text-transform:uppercase;color:#64748b;font-weight:700;">Score</div>
                    <div style="margin-top:6px;font-size:28px;font-weight:800;">{percentage}%</div>
                  </div>
                  <div style="padding:14px 18px;border-radius:14px;background:{status_bg};color:#ffffff;min-width:120px;">
                    <div style="font-size:12px;text-transform:uppercase;font-weight:700;opacity:0.9;">Status</div>
                    <div style="margin-top:6px;font-size:24px;font-weight:800;">{html.escape(result_status)}</div>
                  </div>
                </div>

                <div style="margin-top:22px;">
                  <div style="font-size:18px;font-weight:700;margin-bottom:10px;">Positive Feedback</div>
                  <ul style="padding-left:20px;line-height:1.7;margin:0;">
                    {html_feedback or '<li>No detailed feedback generated.</li>'}
                  </ul>
                </div>

                <p style="margin-top:24px;line-height:1.7;color:#475569;"><strong>We will contact you regarding the next steps.</strong></p>
              </div>
            </div>
          </body>
        </html>
        """
    else:
        body = (
            f"Hello {candidate_name},\n\n"
            "Thank you for attending the interview.\n"
            "We regret to inform you that you were not selected this time.\n\n"
            "We encourage you to continue improving your skills and apply again in the future. "
            "We wish you all the best in your career journey.\n"
        )
        html_body = f"""
        <html>
          <body style="margin:0;padding:24px;background:#eef4ff;font-family:Segoe UI,Arial,sans-serif;color:#0f172a;">
            <div style="max-width:720px;margin:0 auto;background:#ffffff;border-radius:18px;overflow:hidden;border:1px solid #dbe3ef;">
              <div style="background:#0f172a;padding:24px 28px;color:#ffffff;">
                <div style="font-size:22px;font-weight:700;">Interview Result</div>
              </div>

              <div style="padding:28px;">
                <p style="margin-top:0;font-size:16px;">Hello <strong>{html.escape(candidate_name)}</strong>,</p>
                <p>Thank you for attending the interview.</p>
                <p><strong>We regret to inform you that you were not selected this time.</strong></p>
                <p>We encourage you to continue improving your skills and apply again in the future. We wish you all the best in your career journey.</p>
              </div>
            </div>
          </body>
        </html>
        """

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = formataddr(("AI Interview System", EMAIL_SENDER))
    message["To"] = candidate_email
    message.set_content(body)
    message.add_alternative(html_body, subtype="html")

    if passed:
        pdf_bytes = generate_detailed_report_pdf(
            candidate_name=candidate_name,
            interview_domain=interview_domain,
            percentage=percentage,
            result_status=result_status,
            feedback=feedback,
            recruiter_summary=recruiter_summary,
        )
        message.add_attachment(
            pdf_bytes,
            maintype="application",
            subtype="pdf",
            filename="Interview_Report.pdf",
        )

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as server:
            server.ehlo()
            if SMTP_USE_TLS:
                server.starttls()
                server.ehlo()
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.send_message(message)
        app.logger.info("Interview result email sent to %s", candidate_email)
    except Exception as exc:
        app.logger.warning("Failed to send interview result email to %s: %s", candidate_email, exc)


def schedule_result_email(candidate_email, candidate_name, percentage, result_status, interview_domain, feedback, recruiter_summary):

    if not candidate_email:
        return

    timer = threading.Timer(
        RESULT_EMAIL_DELAY_SECONDS,
        send_result_email,
        args=(candidate_email, candidate_name, percentage, result_status, interview_domain, feedback, recruiter_summary),
    )
    timer.daemon = True
    timer.start()


def call_gemini(prompt, timeout=REQUEST_TIMEOUT):
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY is not set")

    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
    )
    headers = {"Content-Type": "application/json"}
    data = {"contents": [{"parts": [{"text": prompt}]}]}

    response = requests.post(url, headers=headers, json=data, timeout=timeout)
    response.raise_for_status()
    result = response.json()

    return result["candidates"][0]["content"]["parts"][0]["text"].strip()


# =========================
# AI QUESTION GENERATOR
# =========================
def generate_ai_question(domain, difficulty):

    fresher_fallback = [
        f"Tell me one {domain} project you did in college.",
        f"If your {domain} code is not working, what is the first thing you check?",
        f"If your {domain} program is slow, what simple fix would you try first?",
        f"Before final submission of a {domain} project, what two checks do you do?",
        f"Name one real use of {domain} in a student project.",
    ]

    tough_patterns = [
        "system design",
        "microservices",
        "distributed",
        "consistency",
        "kubernetes",
        "scalability",
        "eventual consistency",
        "high availability",
        "load balancer",
        "sharding",
        "fault tolerance",
    ]

    basic_patterns = ["what is", "where is", "advantages", "define ", "explain the basics"]

    try:

        prompt = f"""
You are interviewing a fresher (entry-level candidate).
Create exactly ONE {difficulty} level interview question for {domain}.

Rules:
- Ask a SIMPLE fresher-level question only.
- Keep language easy and direct (one sentence).
- Ask about very basic coding tasks, simple debugging, and student mini-project experience.
- Strictly avoid advanced topics like system design, distributed systems, scalability design, architecture patterns.
- Do NOT ask textbook-style "what is", "where is it used", or "advantages/disadvantages" questions.
- Keep it under 16 words.
- Return only one question line, no numbering.
"""

        question = call_gemini(prompt, timeout=8)
        lowered = question.lower()

        if any(p in lowered for p in basic_patterns):
            return random.choice(fresher_fallback)

        if any(p in lowered for p in tough_patterns):
            return random.choice(fresher_fallback)

        if len(question.split()) > 16:
            return random.choice(fresher_fallback)

        return question

    except (requests.RequestException, KeyError, IndexError, RuntimeError, ValueError) as exc:
        app.logger.warning("Falling back to local question for domain '%s': %s", domain, exc)
        return random.choice(fresher_fallback)


def get_easy_domain_questions(domain, total=5):

    domain_question_bank = {
        "Java": [
            "Explain encapsulation with a simple class example.",
            "What is the difference between method overloading and overriding?",
            "What is the difference between abstract class and interface?",
            "Explain inheritance and polymorphism with one real example.",
            "What is exception handling in Java and why is it needed?",
            "Difference between checked and unchecked exceptions in Java.",
            "What is the difference between final, finally, and finalize?",
            "What is the use of try-catch-finally block in Java?",
            "Difference between ArrayList and LinkedList in Java.",
            "Difference between String, StringBuilder, and StringBuffer.",
        ],
        "Python": [
            "Difference between list and tuple in Python.",
            "What is the use of dictionary in Python?",
            "Difference between *args and **kwargs.",
            "What is exception handling in Python with example?",
            "Difference between break, continue, and pass.",
            "What is the use of __init__ in Python classes?",
            "Difference between shallow copy and deep copy.",
            "What is list comprehension in Python?",
        ],
        "C++": [
            "Difference between class and struct in C++.",
            "What is constructor and destructor in C++?",
            "Difference between function overloading and overriding.",
            "What is the use of virtual function in C++?",
            "Difference between pointer and reference in C++.",
            "What is exception handling in C++?",
            "What is STL and name any two STL containers.",
            "Difference between stack and heap memory in C++.",
        ],
        "C Programming": [
            "Difference between array and pointer in C.",
            "What is structure in C and why do we use it?",
            "Difference between call by value and call by reference.",
            "What is dynamic memory allocation in C?",
            "Difference between malloc and calloc.",
            "What is the use of pointers in C?",
            "What is file handling in C?",
            "Difference between while loop and do-while loop.",
        ],
        "DBMS": [
            "What is normalization and why is it important?",
            "Difference between primary key and foreign key.",
            "What is the difference between DBMS and RDBMS?",
            "Explain ACID properties in simple terms.",
            "What is transaction in DBMS?",
            "Difference between DELETE, TRUNCATE, and DROP.",
            "What is indexing and why is it used?",
            "Difference between one-to-one and one-to-many relationship.",
        ],
        "SQL": [
            "Difference between WHERE and HAVING clause.",
            "Difference between INNER JOIN and LEFT JOIN.",
            "What is GROUP BY in SQL?",
            "What is a subquery in SQL?",
            "Difference between UNION and UNION ALL.",
            "What is the use of ORDER BY in SQL?",
            "Difference between CHAR and VARCHAR.",
            "What is primary key and unique key in SQL?",
        ],
    }

    easy_pool = domain_question_bank.get(
        domain,
        [
            f"Explain one important concept in {domain} with example.",
            f"What is the difference between two basic concepts in {domain} you learned?",
            f"Why is {domain} used in software development?",
            f"Name one common error in {domain} and how to avoid it.",
            f"Explain one beginner-level topic in {domain} in simple words.",
            f"Difference between theory and practical use of {domain}.",
        ],
    )

    if total >= len(easy_pool):
        random.shuffle(easy_pool)
        return easy_pool

    return random.sample(easy_pool, total)

# =========================
# AI ANSWER EVALUATION
# =========================
def extract_score(evaluation_text):

    match = re.search(r"Score\s*:\s*(\d+(?:\.\d+)?)", evaluation_text, re.IGNORECASE)
    if not match:
        return 0

    value = float(match.group(1))
    value = max(0.0, min(10.0, value))
    return int(round(value))


def evaluate_keyword_answer(question, answer, keywords):

    clean_answer = (answer or "").strip().lower()
    normalized_keywords = [k.strip() for k in (keywords or []) if k.strip()]

    if not normalized_keywords:
        return "Score: 0\nFeedback: No keywords were configured for this company question."

    matched = [k for k in normalized_keywords if k.lower() in clean_answer]
    missing = [k for k in normalized_keywords if k not in matched]
    score = int(round((len(matched) / len(normalized_keywords)) * 10))

    feedback = f"Matched {len(matched)} of {len(normalized_keywords)} keywords."
    if missing:
        feedback += f" Missing keywords: {', '.join(missing[:5])}."

    return f"Score: {score}\nFeedback: {feedback}"


def split_keywords(raw):

    return [item.strip(" -\t\r\n") for item in re.split(r"[\n,;]+", raw or "") if item.strip()]


def parse_company_questions_from_text(text, evaluation_mode):

    if evaluation_mode == "keyword":
        blocks = re.split(r"\n\s*\n", text)
        parsed = []
        for block in blocks:
            question_match = re.search(r"Question\s*:\s*(.+)", block, re.IGNORECASE)
            keywords_match = re.search(r"Keywords?\s*:\s*(.+)", block, re.IGNORECASE | re.DOTALL)
            if not question_match:
                continue
            parsed.append(
                {
                    "question": question_match.group(1).strip(),
                    "keywords": split_keywords(keywords_match.group(1) if keywords_match else ""),
                }
            )

        if parsed:
            return parsed[:5]

    questions = []
    for line in text.splitlines():
        cleaned = re.sub(r"^[\-\d.)\s]+", "", line.strip())
        lowered = cleaned.lower()
        looks_like_question = (
            len(cleaned) >= 10
            and (
                cleaned.endswith("?")
                or lowered.startswith(("what ", "how ", "why ", "explain ", "describe ", "tell ", "define "))
            )
        )
        if looks_like_question:
            questions.append({"question": cleaned, "keywords": []})

    return questions[:5]


def parse_company_upload(file_storage, evaluation_mode):

    filename = (file_storage.filename or "").lower()
    ext = filename.rsplit(".", 1)[-1] if "." in filename else ""

    if ext == "pdf":
        reader = PyPDF2.PdfReader(file_storage)
        text = ""
        for page in reader.pages:
            text += (page.extract_text() or "") + "\n"
        return parse_company_questions_from_text(text, evaluation_mode)

    if ext == "txt":
        text = file_storage.read().decode("utf-8", errors="ignore")
        return parse_company_questions_from_text(text, evaluation_mode)

    if ext == "csv":
        text = file_storage.read().decode("utf-8", errors="ignore")
        rows = list(csv.DictReader(io.StringIO(text)))
        parsed = []
        for row in rows:
            question = (row.get("question") or row.get("Question") or "").strip()
            keywords = row.get("keywords") or row.get("Keywords") or ""
            if question:
                parsed.append(
                    {
                        "question": question,
                        "keywords": split_keywords(keywords) if evaluation_mode == "keyword" else [],
                    }
                )
        return parsed[:5]

    if ext in {"xlsx", "xls"}:
        try:
            import pandas as pd
        except ImportError as exc:
            raise RuntimeError("Excel upload requires pandas and openpyxl.") from exc

        dataframe = pd.read_excel(file_storage)
        parsed = []
        for _, row in dataframe.fillna("").iterrows():
            question = str(row.get("question") or row.get("Question") or "").strip()
            keywords = str(row.get("keywords") or row.get("Keywords") or "")
            if question:
                parsed.append(
                    {
                        "question": question,
                        "keywords": split_keywords(keywords) if evaluation_mode == "keyword" else [],
                    }
                )
        return parsed[:5]

    raise RuntimeError("Unsupported file format. Use PDF, TXT, CSV, or Excel.")

def evaluate_answer_with_sentence_transformer(question, answer):

    model = get_sentence_model()
    if model is None or util is None:
        return None

    question_embedding = model.encode(question, convert_to_tensor=True)
    answer_embedding = model.encode(answer, convert_to_tensor=True)
    similarity = float(util.cos_sim(question_embedding, answer_embedding)[0][0])
    similarity = max(0.0, min(1.0, (similarity + 1.0) / 2.0))

    word_count = len(answer.split())
    detail_bonus = 0.1 if word_count > 20 else 0.0
    score = int(round(min(1.0, similarity + detail_bonus) * 10))

    if score >= 8:
        feedback = "Strong semantic alignment with the question and good answer detail."
        suggestion = "Add one concrete example to make the answer more interview-ready."
    elif score >= 5:
        feedback = "The answer is relevant, but it needs stronger technical depth and structure."
        suggestion = "Explain the concept more clearly and connect it to a practical example."
    else:
        feedback = "The answer has weak semantic alignment or is too brief."
        suggestion = "Answer directly, define the concept, and include one short real-world use case."

    return f"Score: {score}\nFeedback: {feedback}\nImprovement: {suggestion}"


def evaluate_answer(question, answer):

    clean_answer = (answer or "").strip()

    if clean_answer == "" or clean_answer == "NO_ANSWER":
        return "Score: 0\nFeedback: No answer provided."

    if clean_answer == "SKIPPED":
        return "Score: 1\nFeedback: Question was skipped."

    try:

        prompt = f"""
You are evaluating a fresher interview response.

Question:
{question}

Candidate Answer:
{clean_answer}

Scoring rubric (0 to 10):
- Relevance to question: 0-4
- Technical correctness: 0-4
- Clarity and completeness: 0-2

Important rules:
- Give fair, question-aligned score only.
- Avoid random extreme scoring.
- Use 0 or 10 only when clearly deserved.
- If answer is partially correct, use mid-range score.

Return exactly this format:
Score: <0-10>
Feedback: <1-2 concise sentences>
"""

        evaluation = call_gemini(prompt, timeout=10)

        score = extract_score(evaluation)
        if "Feedback:" not in evaluation:
            evaluation = f"Score: {score}\nFeedback: Answer evaluated based on relevance, correctness, and clarity."

        return evaluation

    except (requests.RequestException, KeyError, IndexError, RuntimeError, ValueError) as exc:
        app.logger.warning("Using fallback evaluation for question '%s': %s", question, exc)
        st_evaluation = evaluate_answer_with_sentence_transformer(question, clean_answer)
        if st_evaluation:
            return st_evaluation

        answer_words = len(clean_answer.split())
        if answer_words <= 3:
            score = 2
        elif answer_words <= 10:
            score = 4
        elif answer_words <= 25:
            score = 6
        else:
            score = 7

        return (
            f"Score: {score}\n"
            "Feedback: Partial automatic evaluation used because hosted AI and local semantic model were unavailable."
        )


# =========================
# VOICE PASSWORD AUTHENTICATION
# =========================
@app.route("/voice-password")
def voice_password_home():
    return render_template(
        "voice_password.html",
        authenticated=voice_password_is_authenticated(),
        username=session.get("voice_password_username", ""),
        email=session.get("voice_password_email", ""),
        threshold=os.getenv("VOICE_PASSWORD_THRESHOLD", "0.86"),
    )


@app.route("/voice-password/register")
def voice_password_register():
    passages = random.sample(
        VOICE_REGISTRATION_PASSAGES,
        k=min(3, len(VOICE_REGISTRATION_PASSAGES)),
    )
    return render_template(
        "voice_password_register.html",
        passages=passages,
        record_seconds=VOICE_REGISTER_RECORD_SECONDS,
    )


@app.route("/voice-password/login")
def voice_password_login():
    challenge = generate_voice_login_challenge()
    return render_template(
        "voice_password_login.html",
        next_url=request.args.get("next") or url_for("index"),
        notice=request.args.get("notice", ""),
        just_registered=request.args.get("registered", "") == "1",
        initial_username=request.args.get("username", ""),
        challenge=challenge,
        record_seconds=VOICE_LOGIN_RECORD_SECONDS,
    )


@app.route("/voice-password/logout", methods=["POST", "GET"])
def voice_password_logout():
    session.pop("voice_password_authenticated", None)
    session.pop("voice_password_username", None)
    session.pop("voice_password_email", None)
    session.pop("voice_password_score", None)
    session.pop("voice_violation_count", None)
    session.pop("voice_suspicious", None)
    session.pop("voice_last_warning", None)
    return redirect(url_for("index"))


@app.route("/api/voice-password/status")
def api_voice_password_status():
    return jsonify(
        {
            "authenticated": voice_password_is_authenticated(),
            "username": session.get("voice_password_username", ""),
            "email": session.get("voice_password_email", ""),
            "required": REQUIRE_VOICE_PASSWORD,
        }
    )


@app.route("/api/voice-password/check-username")
def api_voice_password_check_username():
    username = request.args.get("username", "").strip()
    if len(username) < 4:
        return jsonify({"available": False, "message": "Username must be at least 4 characters."})
    return jsonify({"available": not voice_user_exists(get_db(), username)})


@app.route("/api/voice-password/challenge", methods=["POST"])
def api_voice_password_challenge():
    challenge = generate_voice_login_challenge()
    return jsonify({"success": True, "challenge": challenge})


@app.route("/api/voice-password/register", methods=["POST"])
@app.route("/voice/register", methods=["POST"])
def api_voice_password_register():
    username = request.form.get("username", "").strip()
    email = request.form.get("email", "").strip()

    if len(username) < 4:
        return jsonify({"success": False, "message": "Username must be at least 4 characters."}), 400
    if voice_user_exists(get_db(), username):
        return jsonify({"success": False, "message": "This username already has a voice profile."}), 409

    uploaded_samples = [
        request.files.get("audio_1"),
        request.files.get("audio_2"),
        request.files.get("audio_3"),
    ]
    uploaded_samples = [sample for sample in uploaded_samples if sample and sample.filename]
    if len(uploaded_samples) != 3:
        return jsonify({"success": False, "message": "Please record all three voice samples."}), 400

    embeddings = []
    temp_paths = []
    try:
        for sample in uploaded_samples:
            temp_path = save_uploaded_voice_sample(sample)
            temp_paths.append(temp_path)
            embeddings.append(extract_voice_embedding(temp_path))

        profile_embedding = average_embeddings(embeddings)
        saved = save_voice_profile(get_db(), username, email, profile_embedding, len(embeddings))
        if not saved:
            return jsonify({"success": False, "message": "This username already has a voice profile."}), 409

        return jsonify(
            {
                "success": True,
                "message": f"Voice password registered for {username}. You can log in now.",
                "username": username,
                "samples": len(embeddings),
                "redirect": url_for("voice_password_login", registered=1, username=username),
            }
        )
    except ValueError as exc:
        return jsonify({"success": False, "message": str(exc)}), 400
    except Exception as exc:
        app.logger.exception("Voice password registration failed")
        return jsonify({"success": False, "message": f"Voice registration failed: {exc}"}), 500
    finally:
        for temp_path in temp_paths:
            cleanup_file(temp_path)


@app.route("/api/voice-password/login", methods=["POST"])
@app.route("/voice/login", methods=["POST"])
def api_voice_password_login():
    username = request.form.get("username", "").strip()
    next_url = request.form.get("next") or url_for("index")
    audio = request.files.get("audio")
    if not audio or not audio.filename:
        return jsonify({"success": False, "message": "Please record your voice password."}), 400

    temp_path = None
    try:
        temp_path = save_uploaded_voice_sample(audio)
        challenge_result = validate_voice_login_challenge(temp_path)
        probe_embedding = extract_voice_embedding(temp_path)
        result = authenticate_voice_profile(get_db(), probe_embedding, username=username)

        if not result.get("authenticated"):
            return jsonify({"success": False, **result}), 401

        session.permanent = True
        session["voice_password_authenticated"] = True
        session["voice_password_username"] = result.get("username", "")
        session["voice_password_email"] = result.get("email", "")
        session["voice_password_score"] = result.get("score", 0)
        session.pop("voice_login_challenge", None)
        reset_voice_interview_state()

        return jsonify(
            {
                "success": True,
                "redirect": next_url,
                "message": result.get("message", "Voice password accepted."),
                "username": result.get("username", ""),
                "email": result.get("email", ""),
                "score": result.get("score", 0),
                "threshold": result.get("threshold", 0),
                "transcript": challenge_result.get("transcript", ""),
                "similarity_score": challenge_result.get("similarity_score", 0),
                "matched": challenge_result.get("matched", False),
            }
        )
    except ValueError as exc:
        return jsonify({"success": False, "message": str(exc)}), 400
    except Exception as exc:
        app.logger.exception("Voice password login failed")
        return jsonify({"success": False, "message": f"Voice login failed: {exc}"}), 500
    finally:
        cleanup_file(temp_path)


@app.route("/api/voice-password/verify-interview", methods=["POST"])
@app.route("/voice/verify-interview", methods=["POST"])
def api_voice_password_verify_interview():
    if not REQUIRE_VOICE_PASSWORD:
        return jsonify({"success": True, "authenticated": True, "required": False})
    if not voice_password_is_authenticated():
        return jsonify(
            {
                "success": False,
                "authenticated": False,
                "message": "Voice password session is not authenticated.",
            }
        ), 401

    audio = request.files.get("audio")
    if not audio or not audio.filename:
        return jsonify({"success": False, "authenticated": False, "message": "No interview audio received."}), 400

    temp_path = None
    try:
        temp_path = save_uploaded_voice_sample(audio)
        db = get_db()
        expected_username = session.get("voice_password_username", "")
        profile = get_voice_profile(db, expected_username)
        if not profile:
            return jsonify(
                {
                    "success": False,
                    "authenticated": False,
                    "message": "Registered voice profile was not found. Please log in again.",
                }
            ), 404

        enrolled_embedding = np.load(io.BytesIO(profile["embedding"]))
        analysis = analyze_interview_voice(temp_path, enrolled_embedding=enrolled_embedding)
        result = authenticate_voice_profile(db, analysis["embedding"], username=expected_username)

        question_number = request.form.get("question_number", "")
        source = request.form.get("source", "")
        session_id = request.form.get("session_id", "").strip() or session.get("api_session_id", "").strip()

        warning_message = ""
        violation_type = ""
        if analysis["multiple_speakers_detected"]:
            warning_message = "Multiple voices detected during interview"
            violation_type = "multiple_speakers"
        elif not result.get("authenticated"):
            warning_message = "Voice mismatch detected"
            violation_type = "voice_mismatch"

        violation_count = int(session.get("voice_violation_count", 0) or 0)
        suspicious = bool(session.get("voice_suspicious", False))
        terminate_recommended = False
        if warning_message:
            violation_count, terminate_recommended = record_voice_violation(warning_message)
            suspicious = bool(session.get("voice_suspicious", False))

        log_voice_verification(
            db,
            username=expected_username,
            session_id=session_id,
            question_number=question_number,
            source=source,
            authenticated=bool(result.get("authenticated")) and not analysis["multiple_speakers_detected"],
            score=float(result.get("score", 0.0) or 0.0),
            threshold=float(result.get("threshold", 0.0) or 0.0),
            multiple_speakers_detected=analysis["multiple_speakers_detected"],
            different_voice_detected=(not result.get("authenticated")) or analysis["different_voice_detected"],
            speaker_count_estimate=analysis["speaker_count_estimate"],
            reasons=analysis["reasons"],
        )

        response_payload = {
            "success": True,
            **result,
            "authenticated": bool(result.get("authenticated")) and not analysis["multiple_speakers_detected"],
            "required": True,
            "expected_username": expected_username,
            "question_number": question_number,
            "source": source,
            "session_id": session_id,
            "warning_message": warning_message,
            "violation_type": violation_type,
            "violation_count": violation_count,
            "suspicious": suspicious,
            "terminate_recommended": terminate_recommended,
            "multiple_speakers_detected": analysis["multiple_speakers_detected"],
            "speaker_count_estimate": analysis["speaker_count_estimate"],
            "different_voice_detected": (not result.get("authenticated")) or analysis["different_voice_detected"],
            "mixed_voice_detected": analysis["mixed_voice_detected"],
            "segment_count": analysis["segment_count"],
            "mean_similarity": analysis["mean_similarity"],
            "min_similarity": analysis["min_similarity"],
            "max_similarity": analysis["max_similarity"],
            "similarity_scores": analysis["similarity_scores"],
            "reasons": analysis["reasons"],
        }
        if warning_message:
            response_payload["message"] = warning_message
        return jsonify(response_payload)
    except ValueError as exc:
        return jsonify({"success": False, "authenticated": False, "message": str(exc)}), 400
    except Exception as exc:
        app.logger.exception("Interview voice verification failed")
        return jsonify({"success": False, "authenticated": False, "message": f"Voice verification failed: {exc}"}), 500
    finally:
        cleanup_file(temp_path)


# =========================
# HOME PAGE
# =========================
@app.route("/")
def index():
    sync_admin_user_record()

    domains = [
        "C Programming",
        "C++",
        "Java",
        "Python",
        "SQL",
        "DBMS",
        "Operating Systems",
        "Computer Networks",
        "Data Structures",
        "Algorithms",
        "Machine Learning",
        "Artificial Intelligence",
        "Cloud Computing",
        "Cyber Security",
        "React",
        "Spring Boot",
    ]

    return render_template(
        "index.html",
        domains=domains,
        admin_logged_in=session.get("admin_logged_in", False) and session.get("user_role") == "admin",
        voice_authenticated=voice_password_is_authenticated(),
        voice_required=REQUIRE_VOICE_PASSWORD,
        voice_username=session.get("voice_password_username", ""),
        voice_email=session.get("voice_password_email", ""),
        voice_score=session.get("voice_password_score", ""),
    )


# =========================
# START DOMAIN INTERVIEW
# =========================
@app.route("/start", methods=["POST"])
def start():
    auth_guard = auth_required_redirect()
    if auth_guard:
        return auth_guard

    session["name"] = request.form["name"]
    session["email"] = request.form.get("email", "").strip()
    session["domain"] = request.form["domain"]
    session["current"] = 0
    session["answers"] = []
    reset_security_warning_state()
    session["user_role"] = "user"
    session["result_saved"] = False
    session["result_email_scheduled"] = False
    reset_voice_interview_state()
    session["welcome"] = f"Welcome {session['name']}. Your AI interview starts now."
    # Instant load: avoid multiple external API calls on interview start.
    quick_questions = get_easy_domain_questions(session["domain"], total=5)
    session["questions"] = [{"question": q} for q in quick_questions]
    session["api_session_id"] = sync_fastapi_session(
        candidate_name=session["name"],
        candidate_email=session.get("email", ""),
        mode="domain",
        metadata={"domain": session["domain"], "source": "legacy-flask"},
        questions=session["questions"],
        greeting=session["welcome"],
    )

    return redirect(url_for("interview", session_id=session["api_session_id"]))


# =========================
# RESUME INTERVIEW
# =========================
@app.route("/resume_interview", methods=["POST"])
def resume_interview():
    auth_guard = auth_required_redirect()
    if auth_guard:
        return auth_guard

    session["name"] = request.form["name"]
    session["email"] = request.form.get("email", "").strip()
    session["domain"] = "Resume Interview"
    session["current"] = 0
    session["answers"] = []
    reset_security_warning_state()
    session["user_role"] = "user"
    session["result_saved"] = False
    session["result_email_scheduled"] = False
    reset_voice_interview_state()

    file = request.files["resume"]

    try:
        reader = PyPDF2.PdfReader(file)
        text = ""
        for page in reader.pages:
            text += page.extract_text() or ""
    except Exception as exc:
        app.logger.warning("Resume parsing failed: %s", exc)
        text = ""

    prompt = f"""
You are interviewing a candidate based on the resume.
Generate exactly 5 interview questions to assess whether the candidate is technically strong.

Rules:
- Questions must be based on the candidate's actual projects, tools, and technologies in resume.
- Include tool-focused questions (for example: Git, Docker, Postman, Jira, CI/CD, cloud tools, DB tools) only if tools appear in resume.
- Include depth-check questions: ownership, debugging approach, trade-offs, and production readiness.
- Keep questions practical and clear; avoid generic textbook questions like "what is X".
- Return only 5 questions, one per line, no numbering.

Resume:
{text}
"""

    try:
        questions_text = call_gemini(prompt, timeout=10)
        questions = [q for q in questions_text.split("\n") if q.strip() != ""]
    except (requests.RequestException, KeyError, IndexError, RuntimeError, ValueError) as exc:
        app.logger.warning("Using fallback resume questions: %s", exc)

        questions = [
            "Pick one project from your resume and explain your exact technical contribution.",
            "Which tool from your resume did you use most, and how did it improve your workflow?",
            "Describe one tough bug you solved and the steps you followed to debug it.",
            "How did you validate your project quality before demo or deployment?",
            "What tells you that your strongest technology skill is production-ready?",
        ]

    session["questions"] = [{"question": q} for q in questions[:5]]
    session["welcome"] = f"Welcome {session['name']}. Your AI interview starts now."
    session["api_session_id"] = sync_fastapi_session(
        candidate_name=session["name"],
        candidate_email=session.get("email", ""),
        mode="resume",
        metadata={"domain": session["domain"], "source": "legacy-flask"},
        questions=session["questions"],
        greeting=session["welcome"],
    )

    return redirect(url_for("interview", session_id=session["api_session_id"]))


@app.route("/company_interview", methods=["POST"])
def company_interview():
    auth_guard = auth_required_redirect()
    if auth_guard:
        return auth_guard

    session["name"] = request.form["name"]
    session["email"] = request.form.get("email", "").strip()
    session["domain"] = "Company Based Interview"
    session["current"] = 0
    session["answers"] = []
    reset_security_warning_state()
    session["user_role"] = "user"
    session["result_saved"] = False
    session["result_email_scheduled"] = False
    reset_voice_interview_state()
    session["evaluation_mode"] = request.form.get("evaluation_mode", "ai")

    company_file = request.files["company_file"]

    try:
        parsed_questions = parse_company_upload(company_file, session["evaluation_mode"])
    except Exception as exc:
        app.logger.warning("Company question parsing failed: %s", exc)
        parsed_questions = []

    if not parsed_questions:
        if session["evaluation_mode"] == "keyword":
            parsed_questions = [
                {
                    "question": "What is REST API?",
                    "keywords": ["HTTP", "Stateless", "GET", "POST", "PUT", "DELETE", "Client Server"],
                },
                {
                    "question": "What is normalization in DBMS?",
                    "keywords": ["redundancy", "dependency", "tables", "consistency"],
                },
                {
                    "question": "Explain object-oriented programming.",
                    "keywords": ["class", "object", "inheritance", "encapsulation", "polymorphism"],
                },
                {
                    "question": "What is exception handling?",
                    "keywords": ["error", "try", "catch", "finally"],
                },
                {
                    "question": "What is an API?",
                    "keywords": ["interface", "communication", "request", "response"],
                },
            ]
        else:
            parsed_questions = [
                {"question": "Explain one challenge from a company project and how you solved it.", "keywords": []},
                {"question": "How do you debug a production issue in a web application?", "keywords": []},
                {"question": "What makes an API scalable and maintainable?", "keywords": []},
                {"question": "How do you improve code quality in a team project?", "keywords": []},
                {"question": "Describe your approach to testing a backend service.", "keywords": []},
            ]

    session["questions"] = parsed_questions[:5]
    session["welcome"] = f"Welcome {session['name']}. Your AI interview starts now."
    session["api_session_id"] = sync_fastapi_session(
        candidate_name=session["name"],
        candidate_email=session.get("email", ""),
        mode="company-keyword" if session.get("evaluation_mode") == "keyword" else "company-ai",
        metadata={
            "domain": session["domain"],
            "evaluation_mode": session.get("evaluation_mode", "ai"),
            "source": "legacy-flask",
        },
        questions=session["questions"],
        greeting=session["welcome"],
    )

    return redirect(url_for("interview", session_id=session["api_session_id"]))


# =========================
# INTERVIEW PAGE
# =========================
@app.route("/interview")
def interview():
    auth_guard = auth_required_redirect()
    if auth_guard:
        return auth_guard

    current = session.get("current", 0)
    questions = session.get("questions", [])

    if not questions:
        return redirect(url_for("index"))

    if current >= len(questions):
        return redirect(url_for("result"))

    question = questions[current]

    return render_template(
        "interview.html",
        question=question,
        index=current + 1,
        total=5,
        api_session_id=session.get("api_session_id", ""),
        api_base_url=FASTAPI_BASE_URL,
        speech_service_url=SPEECH_SERVICE_URL,
        interviewer_image_url=INTERVIEWER_IMAGE_URL,
        voice_authenticated=voice_password_is_authenticated(),
        voice_required=REQUIRE_VOICE_PASSWORD,
        voice_username=session.get("voice_password_username", ""),
        stt_confidence_threshold=STT_CONFIDENCE_THRESHOLD,
        silence_timeout_ms=SILENCE_TIMEOUT_MS,
        vad_speech_threshold=VAD_SPEECH_THRESHOLD,
        audio_buffer_ms=AUDIO_BUFFER_MS,
        # Camera presence enforcement settings
        max_no_face_seconds=proctoring_settings.max_no_face_seconds,
        max_absence_warnings=proctoring_settings.max_absence_warnings,
        reentry_verification_required=proctoring_settings.reentry_verification_required,
        face_presence_check_interval_ms=proctoring_settings.face_presence_check_interval_ms,
        no_face_persistence_ms=proctoring_settings.no_face_persistence_ms,
        replacement_detection_threshold=proctoring_settings.replacement_detection_threshold,
    )


# =========================
# SAVE ANSWER
# =========================
@app.route("/save_answer", methods=["POST"])
def save_answer():

    if "questions" not in session:
        return redirect(url_for("index"))

    answer = request.form.get("answer", "").strip()

    if not answer:
        answer = "NO_ANSWER"

    answers = session.get("answers", [])
    answers.append(answer)

    session["answers"] = answers
    session["current"] = len(answers)

    return redirect(url_for("interview"))

# =========================
# RESULT PAGE
# =========================
@app.route("/result")
def result():

    if "name" not in session or "domain" not in session or "questions" not in session:
        return redirect(url_for("index"))

    questions = session.get("questions", [])[:5]
    answers = session.get("answers", [])[:5]

    if not questions:
        return redirect(url_for("index"))

    cached_result = session.get("result_data")

    if cached_result:
        percentage = cached_result["percentage"]
        result_status = cached_result["result"]
        feedback = cached_result["feedback"]
        recruiter_summary = cached_result.get("recruiter_summary", {})
        total_score = cached_result.get("total_score", 0)
        question_scores = cached_result.get("question_scores", [])
        performance_label = cached_result.get("performance_label", performance_label_from_total(total_score))
    else:
        total_score = 0
        feedback = []
        question_scores = []

        for i, q in enumerate(questions):

            ans = answers[i] if i < len(answers) else ""

            if session.get("domain") == "Company Based Interview" and session.get("evaluation_mode") == "keyword":
                evaluation = evaluate_keyword_answer(q["question"], ans, q.get("keywords", []))
            else:
                evaluation = evaluate_answer(q["question"], ans)

            feedback.append(evaluation)

            score = normalize_question_score(extract_score(evaluation))
            question_scores.append({"question_number": i + 1, "score": score, "max_score": 10})

            total_score += score

        percentage = int((total_score / 50) * 100)
        result_status = "Pass" if percentage >= 60 else "Fail"
        performance_label = performance_label_from_total(total_score)
        recruiter_summary = build_recruiter_summary(
            questions=questions,
            answers=answers,
            feedback_items=feedback,
            percentage=percentage,
            result_status=result_status,
        )
        session["result_data"] = {
            "percentage": percentage,
            "result": result_status,
            "feedback": feedback,
            "recruiter_summary": recruiter_summary,
            "total_score": total_score,
            "question_scores": question_scores,
            "performance_label": performance_label,
        }

    if not session.get("result_saved"):
        db = get_db()
        db.candidates.insert_one(
            {
                "name": session["name"],
                "email": session.get("email", ""),
                "domain": session["domain"],
                "score": percentage,
                "result": result_status,
                "date": str(datetime.date.today()),
                "created_at": datetime.datetime.utcnow(),
            }
        )
        session["result_saved"] = True

    if not session.get("result_email_scheduled") and session.get("email"):
        schedule_result_email(
            candidate_email=session.get("email"),
            candidate_name=session["name"],
            percentage=percentage,
            result_status=result_status,
            interview_domain=session["domain"],
            feedback=feedback,
            recruiter_summary=recruiter_summary,
        )
        session["result_email_scheduled"] = True

    return render_template(
        "result.html",
        total=5,
        percentage=percentage,
        total_score=total_score,
        question_scores=question_scores,
        performance_label=performance_label,
        result=result_status,
        feedback=feedback,
        email=session.get("email", ""),
        recruiter_summary=recruiter_summary,
    )


@app.route("/completed")
def completed():

    session_id = request.args.get("session_id", "").strip() or session.get("api_session_id", "").strip()
    candidate_name = request.args.get("candidate_name", "").strip() or session.get("name", "Candidate")
    termination_reason = request.args.get("reason", "").strip()
    completion_title = "Interview Completed"
    completion_subtext = "Your results and feedback will be sent to your email within 5 minutes."

    if session_id:
        try:
            requests.post(
                f"{FASTAPI_BASE_URL}/submit-interview",
                json={"session_id": session_id},
                timeout=REQUEST_TIMEOUT,
            )
            completion_response = requests.get(
                f"{FASTAPI_BASE_URL}/interviews/{session_id}/completion",
                timeout=REQUEST_TIMEOUT,
            )
            if completion_response.ok:
                completion_payload = completion_response.json()
                candidate_name = completion_payload.get("candidate_name") or candidate_name
                completion_title = completion_payload.get("title") or completion_title
                completion_subtext = completion_payload.get("subtext") or completion_subtext
                termination_reason = completion_payload.get("termination_reason") or termination_reason
        except Exception as exc:
            app.logger.warning("Could not trigger delayed result processing: %s", exc)

    if not termination_reason:
        termination_reason = "Interview completed successfully"
    return render_template(
        "completed.html",
        candidate_name=candidate_name,
        termination_reason=termination_reason,
        completion_title=completion_title,
        completion_subtext=completion_subtext,
    )


# =========================
# DASHBOARD
# =========================
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if session.get('admin_logged_in') and session.get('user_role') == 'admin':
        return redirect(url_for('admin_dashboard'))
    
    sync_admin_user_record()
    error = None
    if request.method == "POST":
        username = request.form.get("username", request.form.get("email", "")).strip()
        password = request.form.get("password", "").strip()
        
        if verify_admin_credentials(username, password):
            session.permanent = True
            session['admin_logged_in'] = True
            session['admin_username'] = ADMIN_USERNAME
            session['admin_email'] = ADMIN_EMAIL
            session['user_role'] = 'admin'
            next_page = request.args.get('next') or url_for('admin_dashboard')
            return redirect(next_page)
        else:
            error = "Invalid admin email/username or password"
    
    return render_template("admin_login.html", error=error)


@app.route("/admin/logout")
def admin_logout():
    session.pop('admin_logged_in', None)
    session.pop('admin_username', None)
    session.pop('admin_email', None)
    session.pop('user_role', None)
    return redirect(url_for('admin_login'))


@app.route("/admin/dashboard")
@admin_required
def admin_dashboard():
    return redirect(url_for('admin'))


@app.route("/delete_candidate/<id>", methods=["POST"])
@admin_required
def delete_candidate(id):
    if not require_admin_auth():
        return ("Authentication required", 401, {"WWW-Authenticate": 'Basic realm="Admin Panel"'})

    db = get_db()
    try:
        db.candidates.delete_one({"_id": parse_object_id(id)})
    except ValueError:
        pass

    return redirect(url_for("admin"))


# =========================
# ADMIN PANEL
# =========================
@app.route("/admin")
@admin_required
def admin():
    analytics = {}
    sessions = []
    error = ""
    notice = request.args.get("notice", "").strip()
    try:
        reports_response, reports_payload = fetch_admin_api("/admin/reports")
        sessions_response, sessions_payload = fetch_admin_api("/admin/sessions", params={"limit": 10})
        if reports_response.ok:
            analytics = reports_payload
        else:
            error = reports_payload.get("detail", "Could not load admin dashboard analytics.")
        if sessions_response.ok:
            sessions = sessions_payload.get("sessions", [])
        elif not error:
            error = sessions_payload.get("detail", "Could not load recent candidate sessions.")
    except Exception as exc:
        error = f"Could not connect to admin dashboard API: {exc}"

    return render_template("admin_dashboard.html", analytics=analytics, sessions=sessions, error=error, notice=notice)


@app.route("/admin/results")
@admin_required
def admin_results():
    query = request.args.get("q", "").strip()
    status_filter = request.args.get("status", "").strip().upper()
    results = []
    error = ""
    notice = request.args.get("notice", "").strip()
    try:
        response, payload = fetch_admin_api("/admin/results", params={"search": query, "status": status_filter})
        if response.ok:
            results = [normalize_admin_result_record(item) for item in payload.get("results", [])]
        else:
            error = payload.get("detail", "Could not load admin results.")
    except Exception as exc:
        error = f"Could not connect to admin results API: {exc}"

    return render_template("admin_results.html", results=results, query=query, status_filter=status_filter, error=error, notice=notice)


@app.route("/admin/result/<session_id>")
@admin_required
def admin_result_detail(session_id):
    record = None
    error = ""
    notice = request.args.get("notice", "").strip()
    try:
        response, payload = fetch_admin_api(f"/admin/results/{session_id}")
        if response.ok:
            record = normalize_admin_result_record(payload)
            if not record:
                error = "Result data is unavailable for this candidate."
        else:
            error = payload.get("detail", "Result not found.")
    except Exception as exc:
        error = f"Could not load result detail: {exc}"
    try:
        return render_template("admin_result_detail.html", record=record, error=error, notice=notice)
    except Exception as exc:
        app.logger.exception("Failed to render admin result detail for %s", session_id)
        return render_template("admin_result_detail.html", record=None, error=f"Internal Server Error: {exc}", notice=notice), 500


@app.route("/admin/result/<session_id>/feedback-report.pdf")
@admin_required
def admin_result_feedback_pdf(session_id):
    try:
        response = requests.get(
            f"{FASTAPI_BASE_URL}/interviews/{session_id}/report/pdf",
            auth=get_admin_api_auth(),
            timeout=REQUEST_TIMEOUT,
        )
        if not response.ok:
            return redirect(url_for("admin_result_detail", session_id=session_id, notice="Could not generate feedback PDF."))
        return send_file(
            io.BytesIO(response.content),
            as_attachment=True,
            download_name=f"{session_id}-feedback-report.pdf",
            mimetype="application/pdf",
        )
    except Exception as exc:
        app.logger.warning("Failed to download feedback report for %s: %s", session_id, exc)
        return redirect(url_for("admin_result_detail", session_id=session_id, notice="Could not download feedback PDF."))


@app.route("/admin/users")
@admin_required
def admin_users():
    query = request.args.get("q", "").strip()
    sessions = []
    users = []
    error = ""
    notice = request.args.get("notice", "").strip()
    try:
        response, payload = fetch_admin_api("/admin/users", params={"search": query})
        if response.ok:
            sessions = payload.get("sessions", [])
            users = payload.get("users", [])
        else:
            error = payload.get("detail", "Could not load users/sessions.")
    except Exception as exc:
        error = f"Could not connect to users API: {exc}"

    return render_template("admin_users.html", sessions=sessions, users=users, query=query, error=error, notice=notice)


@app.route("/admin/users/<session_id>")
@admin_required
def admin_user_detail(session_id):
    detail = None
    error = ""
    notice = request.args.get("notice", "").strip()
    try:
        response, payload = fetch_admin_api(f"/admin/sessions/{session_id}")
        if response.ok:
            detail = payload
            if isinstance(detail, dict) and isinstance(detail.get("final_report"), dict):
                detail["final_report"] = normalize_admin_result_record(detail.get("final_report"))
        else:
            error = payload.get("detail", "Session not found.")
    except Exception as exc:
        error = f"Could not load user detail: {exc}"

    return render_template("admin_user_detail.html", detail=detail, error=error, notice=notice)


@app.route("/admin/reports")
@admin_required
def admin_reports():
    analytics = {}
    error = ""
    try:
        response, payload = fetch_admin_api("/admin/reports")
        if response.ok:
            analytics = payload
        else:
            error = payload.get("detail", "Could not load reports.")
    except Exception as exc:
        error = f"Could not load reports: {exc}"
    return render_template("admin_reports.html", analytics=analytics, error=error)


@app.route("/admin/reset-data", methods=["POST"])
@admin_required
def admin_reset_data():
    try:
        response, payload = fetch_admin_api_request("POST", "/admin/reset-data")
        if response.ok:
            return redirect(url_for("admin", notice="All candidate interview data has been reset."))
        notice = payload.get("detail", "Could not reset candidate data.")
    except Exception as exc:
        notice = f"Could not reset candidate data: {exc}"
    return redirect(url_for("admin", notice=notice))


@app.route("/admin/users/<session_id>/delete", methods=["POST"])
@admin_required
def admin_delete_user_data(session_id):
    try:
        response, payload = fetch_admin_api_request("DELETE", f"/admin/sessions/{session_id}")
        if response.ok:
            candidate_name = payload.get("candidate_name", "Candidate")
            return redirect(url_for("admin_users", notice=f"Deleted interview data for {candidate_name}."))
        notice = payload.get("detail", "Could not delete candidate data.")
    except Exception as exc:
        notice = f"Could not delete candidate data: {exc}"
    return redirect(url_for("admin_user_detail", session_id=session_id, notice=notice))


@app.route("/admin/result/<session_id>/delete", methods=["POST"])
@admin_required
def admin_delete_result_data(session_id):
    try:
        response, payload = fetch_admin_api_request("DELETE", f"/admin/sessions/{session_id}")
        if response.ok:
            candidate_name = payload.get("candidate_name", "Candidate")
            return redirect(url_for("admin_results", notice=f"Deleted interview data for {candidate_name}."))
        notice = payload.get("detail", "Could not delete candidate data.")
    except Exception as exc:
        notice = f"Could not delete candidate data: {exc}"
    return redirect(url_for("admin_result_detail", session_id=session_id, notice=notice))


@app.route("/add_question", methods=["POST"])
@admin_required
def add_question():
    if not require_admin_auth():
        return ("Authentication required", 401, {"WWW-Authenticate": 'Basic realm="Admin Panel"'})

    domain = request.form["domain"]
    question = request.form["question"]
    correct = request.form["correct"]
    keywords = request.form["keywords"]

    db = get_db()
    db.questions.insert_one(
        {
            "domain": domain,
            "question": question,
            "correct_answer": correct,
            "keywords": keywords,
            "created_at": datetime.datetime.utcnow(),
        }
    )

    return redirect(url_for("admin"))


@app.route("/delete/<id>", methods=["POST"])
@admin_required
def delete(id):
    if not require_admin_auth():
        return ("Authentication required", 401, {"WWW-Authenticate": 'Basic realm="Admin Panel"'})

    db = get_db()
    try:
        db.questions.delete_one({"_id": parse_object_id(id)})
    except ValueError:
        pass

    return redirect(url_for("admin"))


# =========================
# PDF REPORT DOWNLOAD
# =========================
@app.route("/download_report/<name>/<int:score>")
@admin_required
def download_report(name, score):
    if not require_admin_auth():
        return ("Authentication required", 401, {"WWW-Authenticate": 'Basic realm="Admin Panel"'})

    pdf_bytes = generate_detailed_report_pdf(
        candidate_name=name,
        interview_domain="Interview",
        percentage=score,
        result_status="Pass" if score >= 60 else "Fail",
        feedback=["Downloaded from dashboard summary."],
        recruiter_summary={
            "communication_level": "Moderate",
            "technical_confidence": "Moderate" if score >= 60 else "Low",
            "strengths": "Candidate completed the interview workflow.",
            "weaknesses": "Detailed answer-level data is not stored in this dashboard export.",
            "hiring_recommendation": "Hire" if score >= 75 else ("Consider" if score >= 60 else "Needs Improvement"),
        },
    )

    return send_file(
        io.BytesIO(pdf_bytes),
        as_attachment=True,
        download_name="Interview_Report.pdf",
        mimetype="application/pdf",
    )


# =========================
# CHEATING DETECTION
# =========================
@app.route("/cheating_alert", methods=["POST"])
def cheating_alert():
    payload = request.get_json(silent=True) or {}
    message = (payload.get("message") or "Proctoring warning detected.").strip()
    rule = (payload.get("rule") or "proctoring").strip()
    event = record_security_warning(rule, message, payload.get("details") or {})

    if event["terminate"]:
        return {
            "status": "terminated",
            "count": event["count"],
            "level": event["level"],
            "termination_reason": event["termination_reason"],
            "message": event["message"],
        }

    return {
        "status": "warning",
        "count": event["count"],
        "level": event["level"],
        "message": event["message"],
    }


# =========================
# ANALYTICS
# =========================
@app.route("/analytics")
@admin_required
def analytics():
    if not require_admin_auth():
        return ("Authentication required", 401, {"WWW-Authenticate": 'Basic realm="Admin Panel"'})

    db = get_db()
    data = list(db.candidates.find({}, {"name": 1, "score": 1}))

    names = [d.get("name", "Unknown") for d in data]
    scores = [d.get("score", 0) for d in data]

    return render_template("analytics.html", names=names, scores=scores)


# =========================
# ADMIN VOICE USER MANAGEMENT
# =========================
@app.route("/admin/voice-users")
@admin_required
def admin_voice_users():
    """Admin page to list all voice-registered users."""
    query = request.args.get("q", "").strip()
    profiles = []
    stats = {}
    error = ""
    notice = request.args.get("notice", "").strip()

    try:
        db = get_db()
        profiles = list_all_voice_profiles(db, search=query, limit=200)
        stats = get_voice_profile_stats(db)
    except Exception as exc:
        error = f"Could not load voice profiles: {exc}"
        app.logger.error("[AdminVoiceUsers] Error loading profiles: %s", exc)

    return render_template(
        "admin_voice_users.html",
        profiles=profiles,
        stats=stats,
        query=query,
        error=error,
        notice=notice,
    )


@app.route("/admin/voice-users/<username>")
@admin_required
def admin_voice_user_detail(username):
    """Admin page to view voice user details with logs."""
    error = ""
    notice = request.args.get("notice", "").strip()
    detail = None

    try:
        db = get_db()
        detail = get_voice_profile_with_auth_logs(db, username)
        if not detail:
            error = f"Voice profile not found for user: {username}"
    except Exception as exc:
        error = f"Could not load voice profile details: {exc}"
        app.logger.error("[AdminVoiceUserDetail] Error loading details for %s: %s", username, exc)

    return render_template(
        "admin_voice_user_detail.html",
        username=username,
        detail=detail,
        error=error,
        notice=notice,
    )


@app.route("/admin/voice-users/<username>/edit", methods=["POST"])
@admin_required
def admin_voice_user_edit(username):
    """Admin endpoint to update voice user metadata."""
    email = request.form.get("email", "").strip()

    try:
        db = get_db()
        success = update_voice_profile_metadata(db, username, {"email": email})
        if success:
            notice = f"Updated profile for {username}."
        else:
            notice = f"No changes made for {username}."
    except Exception as exc:
        notice = f"Could not update profile: {exc}"
        app.logger.error("[AdminVoiceUserEdit] Error updating %s: %s", username, exc)

    return redirect(url_for("admin_voice_user_detail", username=username, notice=notice))


@app.route("/admin/voice-users/<username>/reset", methods=["POST"])
@admin_required
def admin_voice_user_reset(username):
    """Admin endpoint to reset voice profile for re-registration."""
    try:
        db = get_db()
        result = reset_voice_profile_for_reregistration(db, username)
        if result.get("reset"):
            notice = f"Voice profile reset for {username}. User can now re-register."
        else:
            notice = f"Could not reset profile: {result.get('reason', 'Unknown error')}"
    except Exception as exc:
        notice = f"Could not reset profile: {exc}"
        app.logger.error("[AdminVoiceUserReset] Error resetting %s: %s", username, exc)

    return redirect(url_for("admin_voice_users", notice=notice))


@app.route("/admin/voice-users/<username>/delete", methods=["POST"])
@admin_required
def admin_voice_user_delete(username):
    """Admin endpoint to delete voice profile and related logs."""
    try:
        db = get_db()
        result = delete_voice_profile(db, username)
        if result.get("deleted"):
            auth_deleted = result.get("auth_logs_deleted", 0)
            verify_deleted = result.get("verification_logs_deleted", 0)
            notice = f"Deleted voice profile for {username}."
            if auth_deleted or verify_deleted:
                notice += f" ({auth_deleted} auth logs, {verify_deleted} verification logs removed)"
        else:
            notice = f"Could not delete profile: {result.get('reason', 'Unknown error')}"
    except Exception as exc:
        notice = f"Could not delete profile: {exc}"
        app.logger.error("[AdminVoiceUserDelete] Error deleting %s: %s", username, exc)

    return redirect(url_for("admin_voice_users", notice=notice))


# =========================
# ADMIN PERSONALIZED EMAIL
# =========================
@app.route("/admin/email")
@admin_required
def admin_email():
    """Admin page for sending personalized emails."""
    from backend.app.email_service import get_email_history

    error = request.args.get("error", "").strip()
    success = request.args.get("success", "").strip()
    warning = request.args.get("warning", "").strip()

    try:
        email_history = get_email_history(limit=50)
    except Exception as exc:
        email_history = []
        if not error:
            error = f"Could not load email history: {exc}"
        app.logger.error("[AdminEmail] Error loading history: %s", exc)

    return render_template(
        "admin_email.html",
        email_history=email_history,
        error=error,
        success=success,
        warning=warning,
    )


@app.route("/admin/email/send", methods=["POST"])
@admin_required
def admin_email_send():
    """Admin endpoint to send personalized email."""
    from backend.app.email_service import send_personalized_email

    recipients_raw = request.form.get("recipients", "").strip()
    subject = request.form.get("subject", "").strip()
    message = request.form.get("message", "").strip()

    # Parse recipients (comma-separated)
    recipients = [r.strip() for r in recipients_raw.split(",") if r.strip()]

    if not recipients:
        return redirect(url_for("admin_email", error="Please provide at least one recipient email."))

    if not subject:
        return redirect(url_for("admin_email", error="Please provide an email subject."))

    if not message:
        return redirect(url_for("admin_email", error="Please provide an email message."))

    # Get admin identifier
    admin_user = session.get("admin_user", "Admin")

    try:
        result = send_personalized_email(
            recipients=recipients,
            subject=subject,
            message=message,
            sent_by=admin_user
        )

        if result.get("success"):
            recipient_count = len(result.get("recipients", []))
            if recipient_count == 1:
                success_msg = f"Email sent successfully to {result['recipients'][0]}."
            else:
                success_msg = f"Email sent successfully to {recipient_count} recipients."
            return redirect(url_for("admin_email", success=success_msg))
        else:
            error_msg = result.get("error", "Failed to send email")
            return redirect(url_for("admin_email", error=f"Email send failed: {error_msg}"))

    except Exception as exc:
        app.logger.error("[AdminEmailSend] Error sending email: %s", exc)
        return redirect(url_for("admin_email", error=f"Error sending email: {exc}"))


# =========================
# MAIN
# =========================
init_db()

if __name__ == "__main__":

    app.run(debug=os.getenv("FLASK_DEBUG", "false").lower() == "true")
