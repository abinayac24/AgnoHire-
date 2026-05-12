from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import tempfile
import time
import threading
import wave
import audioop
from functools import lru_cache
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

try:
    import whisper
except ImportError as exc:  # pragma: no cover - import failure handled at startup
    raise RuntimeError(
        "openai-whisper is not installed. Create the Python 3.10 speech-service environment first."
    ) from exc

try:
    import torch
except Exception:
    torch = None

try:
    import webrtcvad
except Exception:
    webrtcvad = None


WHISPER_MODEL_NAME = os.getenv("WHISPER_MODEL_NAME", "base.en")
WHISPER_LANGUAGE = os.getenv("WHISPER_LANGUAGE", "en")
WHISPER_ENABLE_STRICT_PASS = os.getenv("WHISPER_ENABLE_STRICT_PASS", "true").lower() == "true"
WHISPER_LOW_CONFIDENCE_LOGPROB = float(os.getenv("WHISPER_LOW_CONFIDENCE_LOGPROB", "-0.95"))
WHISPER_DEVICE = os.getenv("WHISPER_DEVICE", "cuda" if torch and torch.cuda.is_available() else "cpu")
WHISPER_COMPUTE_FP16 = os.getenv("WHISPER_COMPUTE_FP16", "true").lower() == "true"
ENABLE_VAD_TRIM = os.getenv("ENABLE_VAD_TRIM", "true").lower() == "true"
ENABLE_AUDIO_DENOISE = os.getenv("ENABLE_AUDIO_DENOISE", "true").lower() == "true"
VAD_AGGRESSIVENESS = max(0, min(3, int(os.getenv("VAD_AGGRESSIVENESS", "2"))))
VAD_PADDING_MS = max(0, int(os.getenv("VAD_PADDING_MS", "300")))
LOW_SIGNAL_RMS_THRESHOLD = float(os.getenv("LOW_SIGNAL_RMS_THRESHOLD", "120"))
MIN_SIGNAL_SECONDS = float(os.getenv("MIN_SIGNAL_SECONDS", "0.35"))
SPEECH_SERVICE_ORIGINS = os.getenv(
    "SPEECH_SERVICE_CORS_ORIGINS",
    "*",
)
TECHNICAL_CORRECTIONS = {
    "encapsulation": [
        "encaps",
        "encapsulasion",
        "encapsolation",
        "encapsulations",
        "in capsule ation",
    ],
    "inheritance": [
        "inheritence",
        "in heritance",
        "inneritance",
    ],
    "polymorphism": [
        "poly morphism",
        "polly morphism",
        "polymorfism",
    ],
    "abstraction": [
        "abstractions",
        "abstrakshan",
        "abstract shun",
    ],
    "REST API": [
        "rest api",
        "rest ap i",
        "rest a p i",
        "restapi",
    ],
    "microservices": [
        "micro service",
        "micro services",
        "micros services",
        "microservice is",
    ],
    "SQL": [
        "structured query language",
        "structure query language",
        "sequel",
        "s q l",
    ],
    "query": [
        "gorila",
        "gorilla",
        "guerilla",
        "qurry",
        "quary",
        "querry",
    ],
    "actually": [
        "actuallly",
        "actualy",
        "actully",
        "akchually",
    ],
    "queries": [
        "quries",
        "queris",
    ],
    "primary key": [
        "primary kee",
        "primary ki",
    ],
    "foreign key": [
        "foreign kee",
        "foren key",
    ],
    "normalization": [
        "normalisation",
        "normalizatione",
    ],
    "WHERE": [
        "wear",
        "wheree",
    ],
    "HAVING": [
        "havinge",
    ],
}


app = FastAPI(title="AI Interview Speech Service")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if SPEECH_SERVICE_ORIGINS.strip() == "*" else [origin.strip() for origin in SPEECH_SERVICE_ORIGINS.split(",") if origin.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _ffmpeg_executable() -> str:
    ffmpeg_binary = shutil.which("ffmpeg")
    if not ffmpeg_binary:
        raise HTTPException(status_code=500, detail="FFmpeg is not installed or not available in PATH.")
    return ffmpeg_binary


@lru_cache(maxsize=1)
def get_whisper_model():
    logger.info(f"Loading Whisper model: {WHISPER_MODEL_NAME}")
    model = whisper.load_model(WHISPER_MODEL_NAME, device=WHISPER_DEVICE)
    logger.info("Whisper model loaded successfully")
    return model


def convert_audio_to_wav(source_path: str | Path, wav_path: str | Path) -> None:
    command = [
        _ffmpeg_executable(),
        "-y",
        "-i",
        str(source_path),
        "-ac",
        "1",
        "-ar",
        "16000",
        "-vn",
    ]
    if ENABLE_AUDIO_DENOISE:
        command.extend([
            "-af",
            "highpass=f=120,lowpass=f=3800,afftdn=nf=-25",
        ])
    command.extend([
        str(wav_path),
    ])
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise HTTPException(
            status_code=500,
            detail=f"Audio conversion failed. {(result.stderr or '').strip()}",
        )


def trim_wav_with_vad(wav_path: str | Path) -> None:
    if not ENABLE_VAD_TRIM:
        return
    try:
        with wave.open(str(wav_path), "rb") as wf:
            channels = wf.getnchannels()
            sampwidth = wf.getsampwidth()
            rate = wf.getframerate()
            raw = wf.readframes(wf.getnframes())

        if channels != 1 or sampwidth != 2 or rate != 16000:
            return

        frame_ms = 30
        frame_size = int(rate * frame_ms / 1000) * sampwidth
        frames = [raw[i:i + frame_size] for i in range(0, len(raw), frame_size) if len(raw[i:i + frame_size]) == frame_size]
        if not frames:
            return

        if webrtcvad:
            vad = webrtcvad.Vad(VAD_AGGRESSIVENESS)
            speech_flags = [vad.is_speech(frame, sample_rate=rate) for frame in frames]
        else:
            speech_flags = [audioop.rms(frame, sampwidth) > 260 for frame in frames]

        speech_indexes = [index for index, keep in enumerate(speech_flags) if keep]
        if len(speech_indexes) < 3:
            return

        padding_frames = max(1, int(VAD_PADDING_MS / frame_ms))
        start_index = max(0, speech_indexes[0] - padding_frames)
        end_index = min(len(frames), speech_indexes[-1] + padding_frames + 1)
        rebuilt = b"".join(frames[start_index:end_index])
        with wave.open(str(wav_path), "wb") as out:
            out.setnchannels(1)
            out.setsampwidth(2)
            out.setframerate(16000)
            out.writeframes(rebuilt)
    except Exception as exc:
        logger.warning("VAD trim skipped due to error: %s", exc)


def inspect_audio_signal(wav_path: str | Path) -> dict[str, float]:
    try:
        with wave.open(str(wav_path), "rb") as wf:
            channels = wf.getnchannels()
            sampwidth = wf.getsampwidth()
            rate = wf.getframerate()
            raw = wf.readframes(wf.getnframes())

        if channels != 1 or sampwidth != 2 or rate != 16000 or not raw:
            return {"rms": 0.0, "seconds": 0.0}

        seconds = len(raw) / float(rate * sampwidth)
        rms = float(audioop.rms(raw, sampwidth))
        peak = float(audioop.max(raw, sampwidth))
        return {"rms": rms, "peak": peak, "seconds": round(seconds, 3)}
    except Exception as exc:
        logger.warning("Audio signal inspection skipped: %s", exc)
        return {"rms": 0.0, "peak": 0.0, "seconds": 0.0}


def apply_technical_corrections(text: str) -> str:
    corrected = re.sub(r"\s+", " ", (text or "").strip())
    for canonical, variants in TECHNICAL_CORRECTIONS.items():
        for variant in variants:
            corrected = re.sub(
                rf"\b{re.escape(variant)}\b",
                canonical,
                corrected,
                flags=re.IGNORECASE,
            )
    return corrected


def polish_transcript(text: str) -> str:
    polished = re.sub(r"\s+", " ", (text or "").strip())
    polished = re.sub(r"\bi\b", "I", polished)
    if polished and polished[0].isalpha():
        polished = polished[0].upper() + polished[1:]
    if polished and polished[-1] not in ".!?":
        polished = f"{polished}."
    return polished


def _build_initial_prompt(context_question: str = "") -> str:
    base = (
        "Technical interview answer. Terms may include encapsulation, inheritance, "
        "polymorphism, abstraction, REST API, microservices, SQL, primary key, foreign key, "
        "normalization, WHERE, HAVING, joins, query, queries, database, API, actually."
    )
    clean_question = re.sub(r"\s+", " ", (context_question or "").strip())
    if not clean_question:
        return base
    return f"{base} Current interview question: {clean_question[:240]}"


def _avg_logprob(result: dict) -> float:
    segments = result.get("segments", []) or []
    if not segments:
        return -2.0
    values = [float(seg.get("avg_logprob", -2.0)) for seg in segments]
    return sum(values) / max(1, len(values))


def _keyword_overlap_score(text: str, context_question: str) -> int:
    stop = {
        "what", "which", "when", "where", "that", "this", "with", "from", "have",
        "your", "about", "into", "does", "between", "difference", "define",
    }
    q_tokens = {
        token for token in re.findall(r"[a-zA-Z]{4,}", (context_question or "").lower())
        if token not in stop
    }
    if not q_tokens:
        return 0
    t_tokens = set(re.findall(r"[a-zA-Z]{3,}", (text or "").lower()))
    return len(q_tokens & t_tokens)


def _transcribe_once(audio_path: str | Path, initial_prompt: str, strict: bool) -> tuple[str, float]:
    result = get_whisper_model().transcribe(
        str(audio_path),
        fp16=bool(WHISPER_COMPUTE_FP16 and WHISPER_DEVICE == "cuda"),
        language=WHISPER_LANGUAGE,
        task="transcribe",
        temperature=0.0 if strict else 0.1,
        best_of=5 if strict else 1,
        beam_size=5 if strict else 1,
        condition_on_previous_text=False,
        compression_ratio_threshold=2.4,
        no_speech_threshold=0.6,
        initial_prompt=initial_prompt,
    )
    text = polish_transcript(apply_technical_corrections(result.get("text", "")))
    confidence = _avg_logprob(result)
    return text, confidence


def transcribe_audio(audio_path: str | Path, context_question: str = "") -> tuple[str, float]:
    prompt = _build_initial_prompt(context_question=context_question)
    fast_text, fast_conf = _transcribe_once(audio_path, prompt, strict=False)

    if not WHISPER_ENABLE_STRICT_PASS:
        if len(fast_text.strip()) < 3:
            raise HTTPException(status_code=422, detail="No usable speech detected. Please repeat the answer.")
        return fast_text, fast_conf

    needs_strict = len(fast_text.strip()) < 3 or fast_conf <= WHISPER_LOW_CONFIDENCE_LOGPROB
    if not needs_strict:
        return fast_text, fast_conf

    strict_text, strict_conf = _transcribe_once(audio_path, prompt, strict=True)
    if len(strict_text.strip()) < 3 and len(fast_text.strip()) < 3:
        raise HTTPException(status_code=422, detail="No usable speech detected. Please repeat the answer.")

    if strict_conf <= WHISPER_LOW_CONFIDENCE_LOGPROB:
        rescue_prompt = (
            f"{prompt} Preserve normal spoken words like actually, exactly, and basically. "
            "Do not interpret commands unless the phrase is explicit."
        )
        rescue_text, rescue_conf = _transcribe_once(audio_path, rescue_prompt, strict=True)
        if len(rescue_text.strip()) >= len(strict_text.strip()) and rescue_conf >= strict_conf - 0.05:
            strict_text, strict_conf = rescue_text, rescue_conf

    fast_overlap = _keyword_overlap_score(fast_text, context_question)
    strict_overlap = _keyword_overlap_score(strict_text, context_question)

    if strict_overlap > fast_overlap:
        return strict_text, strict_conf
    if strict_conf >= fast_conf + 0.08:
        return strict_text, strict_conf
    if len(strict_text) > len(fast_text) and strict_conf >= fast_conf - 0.05:
        return strict_text, strict_conf
    return fast_text, fast_conf


def should_retry_transcript(text: str, confidence: float, signal_info: dict[str, float]) -> bool:
    normalized = re.sub(r"\s+", " ", (text or "").strip())
    if len(normalized) < 3:
        return True
    if signal_info.get("seconds", 0.0) >= 0.8 and confidence <= WHISPER_LOW_CONFIDENCE_LOGPROB:
        return True
    if signal_info.get("peak", 0.0) < 300 and signal_info.get("rms", 0.0) < LOW_SIGNAL_RMS_THRESHOLD * 1.1:
        return True
    return False


@app.get("/health")
def health():
    return {
        "status": "ok",
        "model": WHISPER_MODEL_NAME,
        "device": WHISPER_DEVICE,
        "vad": "webrtcvad" if webrtcvad else ("energy" if ENABLE_VAD_TRIM else "disabled"),
        "service": "speech_service",
    }


@app.post("/transcribe")
async def transcribe(
    audio: UploadFile | None = File(default=None),
    file: UploadFile | None = File(default=None),
    context_question: str = Form(default=""),
):
    start_time = time.time()
    source_path = None
    wav_path = None
    upload = audio or file

    try:
        if upload is None:
            raise HTTPException(status_code=422, detail="Upload an audio file using 'audio' or 'file'.")

        logger.info(f"Received transcription request: {upload.filename}")
        
        suffix = os.path.splitext(upload.filename or "")[1] or ".webm"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as source_file:
            source_path = source_file.name
            source_file.write(await upload.read())

        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as wav_file:
            wav_path = wav_file.name

        convert_audio_to_wav(source_path, wav_path)
        trim_wav_with_vad(wav_path)
        signal_info = inspect_audio_signal(wav_path)
        if signal_info["seconds"] < MIN_SIGNAL_SECONDS:
            raise HTTPException(status_code=422, detail="Voice not detected. Please speak for a bit longer.")
        if signal_info["rms"] < LOW_SIGNAL_RMS_THRESHOLD:
            raise HTTPException(status_code=422, detail="Voice not clear, please speak louder and reduce background noise.")
        text, confidence = transcribe_audio(wav_path, context_question=context_question)
        needs_retry = should_retry_transcript(text, confidence, signal_info)
        
        elapsed = time.time() - start_time
        logger.info(f"Transcription completed in {elapsed:.2f}s (confidence={confidence:.2f}): {text[:50]}...")
        
        return {
            "text": text,
            "processing_time": elapsed,
            "confidence": round(confidence, 3),
            "signal_rms": round(signal_info["rms"], 2),
            "signal_peak": round(signal_info["peak"], 2),
            "signal_seconds": signal_info["seconds"],
            "needs_retry": needs_retry,
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Transcription failed: {exc}")
        raise HTTPException(status_code=500, detail=f"Speech service failed: {exc}") from exc
    finally:
        for path in (source_path, wav_path):
            if path and os.path.exists(path):
                os.remove(path)


@app.on_event("startup")
def preload_model() -> None:
    def _warmup():
        try:
            get_whisper_model()
            logger.info("Speech service warmup completed")
        except Exception as exc:
            logger.warning("Speech model warmup failed: %s", exc)
    threading.Thread(target=_warmup, daemon=True).start()
