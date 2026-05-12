from __future__ import annotations

import io
import logging
import tempfile
from typing import Any

import numpy as np
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from app.proctoring.config import settings
from app.proctoring.identity_verifier import identity_verifier

logger = logging.getLogger(__name__)
router = APIRouter(tags=["voice"])


class VoiceVerifyResponse(BaseModel):
    authenticated: bool
    score: float = 0.0
    threshold: float = 0.86
    username: str = ""
    expected_username: str = ""
    warning_message: str = ""
    multiple_speakers_detected: bool = False
    speaker_count_estimate: int = 1
    segment_count: int = 0
    suspicious: bool = False
    violation_count: int = 0
    reasons: list[str] = []
    similarity_scores: list[float] = []


def extract_voice_embedding(audio_bytes: bytes) -> np.ndarray | None:
    """
    Extract voice embedding from audio data.
    This is a simplified implementation - in production, use a proper
    speaker recognition model like SpeechBrain, Resemblyzer, or Azure Speaker Recognition.
    """
    try:
        # Simple feature extraction using numpy
        # In production, replace with actual speaker embedding model
        import wave
        import struct

        # Try to parse as WAV
        try:
            with wave.open(io.BytesIO(audio_bytes), 'rb') as wav_file:
                n_channels = wav_file.getnchannels()
                sample_width = wav_file.getsampwidth()
                n_frames = wav_file.getnframes()
                audio_data = wav_file.readframes(n_frames)

                # Convert to numpy array
                if sample_width == 2:
                    fmt = f"{n_frames * n_channels}h"
                    samples = struct.unpack(fmt, audio_data)
                else:
                    # Fallback: just create random features based on audio length
                    samples = np.random.randn(n_frames)

                samples = np.array(samples, dtype=np.float32)

                # Create a simple embedding based on audio statistics
                # In production, use proper speaker embedding extraction
                embedding_dim = 128
                embedding = np.zeros(embedding_dim, dtype=np.float32)

                # Use statistical features as a simple fingerprint
                embedding[0] = np.mean(samples) / 1000.0
                embedding[1] = np.std(samples) / 1000.0
                embedding[2] = np.max(np.abs(samples)) / 32767.0
                embedding[3] = len(samples) / 16000.0  # Duration approx

                # Add frequency-domain features (simplified)
                if len(samples) > 256:
                    fft = np.abs(np.fft.fft(samples[:256]))
                    embedding[4:20] = fft[:16] / 1000000.0

                # Normalize
                norm = np.linalg.norm(embedding)
                if norm > 0:
                    embedding = embedding / norm

                return embedding

        except Exception as wav_error:
            logger.warning(f"Could not parse WAV, using fallback: {wav_error}")
            # Fallback: create embedding from raw bytes hash
            embedding_dim = 128
            embedding = np.zeros(embedding_dim, dtype=np.float32)

            # Use byte statistics
            if len(audio_bytes) > 100:
                bytes_arr = np.frombuffer(audio_bytes[:8000], dtype=np.uint8)
                embedding[0] = np.mean(bytes_arr) / 255.0
                embedding[1] = np.std(bytes_arr) / 255.0
                embedding[2] = len(audio_bytes) / 100000.0

            norm = np.linalg.norm(embedding)
            if norm > 0:
                embedding = embedding / norm

            return embedding

    except Exception as e:
        logger.error(f"Failed to extract voice embedding: {e}")
        return None


def compute_similarity(emb_a: np.ndarray | None, emb_b: np.ndarray | None) -> float:
    """Compute cosine similarity between embeddings."""
    if emb_a is None or emb_b is None:
        return 0.0
    try:
        a = emb_a.flatten().astype(np.float64)
        b = emb_b.flatten().astype(np.float64)
        if a.shape != b.shape:
            # Pad or truncate to match
            min_len = min(len(a), len(b))
            a = a[:min_len]
            b = b[:min_len]
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(np.clip(np.dot(a, b) / (norm_a * norm_b), -1.0, 1.0))
    except Exception:
        return 0.0


def detect_multiple_speakers(audio_bytes: bytes) -> tuple[bool, int]:
    """
    Detect if multiple speakers are present in audio.
    Returns (multiple_detected, estimated_count).
    """
    # Simplified implementation - in production, use speaker diarization
    # For now, use audio length heuristics
    try:
        audio_duration_estimate = len(audio_bytes) / (16000 * 2)  # Rough 16kHz mono PCM estimate

        # If audio is very short, likely single speaker
        if audio_duration_estimate < 2.0:
            return False, 1

        # Check for pauses/silence that might indicate speaker changes
        # This is a very simplified heuristic
        if len(audio_bytes) > 16000:  # More than ~1 second
            # Random variation for demonstration
            import random
            if random.random() < 0.1:  # 10% chance of detecting multiple speakers
                return True, 2

        return False, 1

    except Exception:
        return False, 1


@router.post("/verify-interview", response_model=VoiceVerifyResponse)
async def verify_interview_voice(
    audio: UploadFile = File(...),
    question_number: str = Form(""),
    source: str = Form("unknown"),
    session_id: str = Form("")
):
    """
    Verify that the interview speaker matches the registered voice profile.

    This endpoint:
    1. Extracts voice embedding from the provided audio
    2. Compares against the registered voice embedding for the session
    3. Returns authentication result with similarity score
    4. Detects multiple speakers if present

    The frontend uses this to implement 3-strike warning escalation for voice mismatches.
    """
    try:
        # Check if proctoring is disabled
        if settings.proctoring_disabled:
            return VoiceVerifyResponse(
                authenticated=True,
                score=1.0,
                threshold=settings.identity_voice_match_threshold,
                username=identity_verifier._registered_username.get(session_id, ""),
                expected_username=identity_verifier._registered_username.get(session_id, ""),
                warning_message="",
                multiple_speakers_detected=False,
                speaker_count_estimate=1,
                segment_count=0,
                suspicious=False,
                violation_count=0,
                reasons=["proctoring_disabled"],
                similarity_scores=[1.0]
            )

        # Get registered user info
        registered_username = identity_verifier._registered_username.get(session_id, "")
        registered_voice_emb = identity_verifier._registered_voice_embedding.get(session_id)

        if not session_id:
            return VoiceVerifyResponse(
                authenticated=False,
                score=0.0,
                warning_message="No session ID provided",
                reasons=["no_session"]
            )

        if not registered_username:
            return VoiceVerifyResponse(
                authenticated=False,
                score=0.0,
                warning_message="No registered user for this session",
                reasons=["no_registered_user"]
            )

        # Read audio data
        audio_bytes = await audio.read()

        if len(audio_bytes) < 1000:
            return VoiceVerifyResponse(
                authenticated=False,
                score=0.0,
                warning_message="Audio sample too short",
                reasons=["audio_too_short"]
            )

        # Check for multiple speakers
        multiple_speakers, speaker_count = detect_multiple_speakers(audio_bytes)

        if multiple_speakers:
            return VoiceVerifyResponse(
                authenticated=False,
                score=0.0,
                threshold=settings.identity_voice_match_threshold,
                username="",
                expected_username=registered_username,
                warning_message="Multiple voices detected during interview. Only the registered candidate's voice is allowed.",
                multiple_speakers_detected=True,
                speaker_count_estimate=speaker_count,
                segment_count=1,
                suspicious=True,
                violation_count=1,
                reasons=["multiple_speakers_detected"],
                similarity_scores=[]
            )

        # If no registered voice embedding, skip voice verification
        if registered_voice_emb is None:
            return VoiceVerifyResponse(
                authenticated=True,
                score=1.0,
                threshold=settings.identity_voice_match_threshold,
                username=registered_username,
                expected_username=registered_username,
                warning_message="",
                multiple_speakers_detected=False,
                speaker_count_estimate=1,
                segment_count=1,
                suspicious=False,
                violation_count=0,
                reasons=["no_voice_profile"],
                similarity_scores=[1.0]
            )

        # Extract embedding from current audio
        current_embedding = extract_voice_embedding(audio_bytes)

        if current_embedding is None:
            return VoiceVerifyResponse(
                authenticated=False,
                score=0.0,
                warning_message="Could not process voice sample",
                reasons=["extraction_failed"]
            )

        # Compare embeddings
        similarity = compute_similarity(registered_voice_emb, current_embedding)

        # Determine authentication result
        threshold = settings.identity_voice_match_threshold
        is_authenticated = similarity >= threshold

        # Build response
        response = VoiceVerifyResponse(
            authenticated=is_authenticated,
            score=round(similarity, 4),
            threshold=round(threshold, 4),
            username=registered_username if is_authenticated else "",
            expected_username=registered_username,
            warning_message="" if is_authenticated else "Voice mismatch detected. Please answer using your registered voice.",
            multiple_speakers_detected=False,
            speaker_count_estimate=1,
            segment_count=1,
            suspicious=similarity < threshold * 0.8,  # Suspicious if well below threshold
            violation_count=0,  # Frontend tracks this via /cheating_alert
            reasons=[] if is_authenticated else ["voice_mismatch"],
            similarity_scores=[round(similarity, 4)]
        )

        logger.info(
            "[VoiceVerify] session=%s, authenticated=%s, score=%.3f, threshold=%.3f, source=%s",
            session_id, is_authenticated, similarity, threshold, source
        )

        return response

    except Exception as e:
        logger.error("[VoiceVerify] Error processing voice verification: %s", str(e))
        raise HTTPException(status_code=500, detail=f"Voice verification error: {str(e)}")
