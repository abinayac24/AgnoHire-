"""
Voice Biometric Verification API Router
Handles voice enrollment and verification during interviews
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from app.dependencies import get_repository
from app.proctoring.enhanced_security import voice_comparator

logger = logging.getLogger(__name__)
router = APIRouter(tags=["voice_verification"])


class VoiceEnrollmentRequest(BaseModel):
    """Request model for voice enrollment."""
    session_id: str = Field(min_length=8, max_length=128)
    username: str = Field(min_length=1, max_length=128)
    audio_samples: list[str] = Field(min_length=3, max_length=10)  # Base64 encoded audio
    sample_duration: float = Field(default=5.0, ge=1.0, le=10.0)  # Duration in seconds


class VoiceVerificationRequest(BaseModel):
    """Request model for voice verification."""
    session_id: str = Field(min_length=8, max_length=128)
    audio_data: str = Field(min_length=100)  # Base64 encoded audio
    timestamp: float | None = None


class VoiceEnrollmentResponse(BaseModel):
    """Response model for voice enrollment."""
    success: bool
    session_id: str
    username: str
    samples_processed: int
    embedding_quality: str  # high, medium, low
    message: str


class VoiceVerificationResponse(BaseModel):
    """Response model for voice verification."""
    verified: bool
    similarity_score: float
    confidence: str
    is_different_speaker: bool
    warning_level: str
    should_alert: bool
    details: dict[str, Any]


@router.post("/voice/enroll", response_model=VoiceEnrollmentResponse)
async def enroll_voice(
    request: VoiceEnrollmentRequest,
    repository=Depends(get_repository)
):
    """
    Enroll voice samples for biometric verification.
    
    This endpoint processes multiple voice samples and creates
    a voice embedding for the user's identity verification.
    """
    try:
        logger.info(f"[VoiceEnroll] Starting enrollment for session {request.session_id}")
        
        # Decode audio samples from base64
        audio_samples = []
        for sample_b64 in request.audio_samples:
            # Remove data URL prefix if present
            if sample_b64.startswith('data:'):
                sample_b64 = sample_b64.split(',')[1]
            
            # Decode base64 to bytes
            import base64
            audio_bytes = base64.b64decode(sample_b64)
            audio_samples.append(audio_bytes)
        
        # Enroll voice with comparator
        success = voice_comparator.enroll_voice(
            session_id=request.session_id,
            audio_samples=audio_samples
        )
        
        if not success:
            raise HTTPException(
                status_code=400,
                detail="Failed to process voice samples"
            )
        
        # Store enrollment metadata
        enrollment_data = {
            "session_id": request.session_id,
            "username": request.username,
            "voice_samples_count": len(audio_samples),
            "sample_duration": request.sample_duration,
            "enrollment_method": "voice_biometric",
            "status": "enrolled"
        }
        
        # Store in repository (if supported)
        try:
            repository.create_voice_enrollment(enrollment_data)
        except AttributeError:
            logger.warning("Repository doesn't support voice enrollment storage")
        
        logger.info(f"[VoiceEnroll] Successfully enrolled voice for {request.session_id}")
        
        return VoiceEnrollmentResponse(
            success=True,
            session_id=request.session_id,
            username=request.username,
            samples_processed=len(audio_samples),
            embedding_quality="high",  # Placeholder - would be calculated
            message="Voice enrollment completed successfully"
        )
        
    except Exception as e:
        logger.error(f"[VoiceEnroll] Failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Voice enrollment failed: {str(e)}"
        )


@router.post("/voice/verify", response_model=VoiceVerificationResponse)
async def verify_voice(
    request: VoiceVerificationRequest,
    repository=Depends(get_repository)
):
    """
    Verify voice against enrolled biometric.
    
    This endpoint compares incoming voice with the enrolled
    voice sample to verify the candidate's identity.
    """
    try:
        logger.info(f"[VoiceVerify] Verifying voice for session {request.session_id}")
        
        # Decode audio data
        if request.audio_data.startswith('data:'):
            audio_b64 = request.audio_data.split(',')[1]
        else:
            audio_b64 = request.audio_data
        
        import base64
        audio_bytes = base64.b64decode(audio_b64)
        
        # Perform voice comparison
        result = voice_comparator.compare_voice(
            session_id=request.session_id,
            audio_sample=audio_bytes,
            timestamp=request.timestamp
        )
        
        # Determine if alert should be triggered
        should_alert = result.warning_level in ['alert', 'critical']
        
        # Log verification result
        if should_alert:
            logger.warning(
                f"[VoiceVerify] ALERT: session={request.session_id}, "
                f"similarity={result.similarity_score:.3f}, level={result.warning_level}"
            )
        else:
            logger.info(
                f"[VoiceVerify] OK: session={request.session_id}, "
                f"similarity={result.similarity_score:.3f}"
            )
        
        # Store verification result (if supported)
        try:
            verification_data = {
                "session_id": request.session_id,
                "verified": result.is_match,
                "similarity_score": result.similarity_score,
                "warning_level": result.warning_level,
                "timestamp": request.timestamp or 0
            }
            repository.store_voice_verification(verification_data)
        except AttributeError:
            logger.warning("Repository doesn't support voice verification storage")
        
        return VoiceVerificationResponse(
            verified=result.is_match,
            similarity_score=result.similarity_score,
            confidence=result.confidence,
            is_different_speaker=result.is_different_speaker,
            warning_level=result.warning_level,
            should_alert=should_alert,
            details=result.details
        )
        
    except Exception as e:
        logger.error(f"[VoiceVerify] Failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Voice verification failed: {str(e)}"
        )


@router.get("/voice/status/{session_id}")
async def get_voice_status(
    session_id: str,
    repository=Depends(get_repository)
):
    """
    Get voice enrollment status for a session.
    """
    try:
        # Check if voice is enrolled
        is_enrolled = session_id in voice_comparator._enrolled_embeddings
        
        if not is_enrolled:
            return {
                "session_id": session_id,
                "enrolled": False,
                "message": "No voice enrollment found"
            }
        
        # Get enrollment details
        embedding = voice_comparator._enrolled_embeddings[session_id]
        sample_count = len(voice_comparator._session_samples.get(session_id, []))
        
        return {
            "session_id": session_id,
            "enrolled": True,
            "embedding_dimension": len(embedding) if embedding is not None else 0,
            "verification_samples": sample_count,
            "last_verification": voice_comparator._session_samples.get(session_id, [])[-1]['timestamp'] if sample_count > 0 else None,
            "message": "Voice enrollment active"
        }
        
    except Exception as e:
        logger.error(f"[VoiceStatus] Failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get voice status: {str(e)}"
        )


@router.delete("/voice/clear/{session_id}")
async def clear_voice_enrollment(
    session_id: str,
    repository=Depends(get_repository)
):
    """
    Clear voice enrollment for a session (cleanup).
    """
    try:
        # Remove from comparator
        if session_id in voice_comparator._enrolled_embeddings:
            del voice_comparator._enrolled_embeddings[session_id]
        
        if session_id in voice_comparator._session_samples:
            del voice_comparator._session_samples[session_id]
        
        if session_id in voice_comparator._mismatch_history:
            del voice_comparator._mismatch_history[session_id]
        
        logger.info(f"[VoiceClear] Cleared voice enrollment for {session_id}")
        
        return {
            "session_id": session_id,
            "cleared": True,
            "message": "Voice enrollment cleared successfully"
        }
        
    except Exception as e:
        logger.error(f"[VoiceClear] Failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to clear voice enrollment: {str(e)}"
        )
