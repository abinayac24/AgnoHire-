from __future__ import annotations

import base64
import io
import logging
import time
from dataclasses import dataclass
from typing import Any

try:
    import numpy as np
except Exception:
    np = None

try:
    import cv2
except Exception:
    cv2 = None

from app.proctoring.config import settings

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class IdentityVerificationResult:
    """Result of identity verification check."""
    username: str
    session_id: str
    face_verified: bool
    voice_verified: bool
    face_score: float
    voice_score: float
    face_mismatch: bool
    voice_mismatch: bool
    both_mismatch: bool
    identity_verified: bool
    face_count: int
    warning_count: int
    should_terminate: bool
    termination_reason: str
    details: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "username": self.username,
            "session_id": self.session_id,
            "face_verified": self.face_verified,
            "voice_verified": self.voice_verified,
            "face_score": round(self.face_score, 4),
            "voice_score": round(self.voice_score, 4),
            "face_mismatch": self.face_mismatch,
            "voice_mismatch": self.voice_mismatch,
            "both_mismatch": self.both_mismatch,
            "identity_verified": self.identity_verified,
            "face_count": self.face_count,
            "warning_count": self.warning_count,
            "should_terminate": self.should_terminate,
            "termination_reason": self.termination_reason,
        }


class IdentityVerifier:
    """Continuous identity verification during interview."""

    def __init__(self) -> None:
        # Session state tracking
        self._registered_username: dict[str, str] = {}
        self._registered_face_embedding: dict[str, np.ndarray | None] = {}
        self._registered_voice_embedding: dict[str, np.ndarray | None] = {}

        # Verification state
        self._last_check_time: dict[str, float] = {}
        self._mismatch_since: dict[str, float] = {}
        self._warning_count: dict[str, int] = {}
        self._last_face_box: dict[str, tuple[int, int, int, int] | None] = {}
        self._identity_verified: dict[str, bool] = {}
        # ADDED: Consecutive mismatch frame tracking (Issue #1 fix)
        self._consecutive_mismatch_frames: dict[str, int] = {}

    def register_user(
        self,
        session_id: str,
        username: str,
        face_embedding: np.ndarray | None = None,
        voice_embedding: np.ndarray | None = None,
    ) -> None:
        """Register the authenticated user for the session."""
        self._registered_username[session_id] = username
        self._registered_face_embedding[session_id] = face_embedding
        self._registered_voice_embedding[session_id] = voice_embedding
        self._last_check_time[session_id] = 0.0
        self._mismatch_since[session_id] = 0.0
        self._warning_count[session_id] = 0
        self._last_face_box[session_id] = None
        self._identity_verified[session_id] = True
        self._consecutive_mismatch_frames[session_id] = 0

        logger.info(
            "[IdentityVerifier] User registered for session=%s, username=%s, "
            "has_face=%s, has_voice=%s",
            session_id, username,
            face_embedding is not None, voice_embedding is not None
        )

    def unregister_session(self, session_id: str) -> None:
        """Clean up session state."""
        for store in [
            self._registered_username,
            self._registered_face_embedding,
            self._registered_voice_embedding,
            self._last_check_time,
            self._mismatch_since,
            self._warning_count,
            self._last_face_box,
            self._identity_verified,
            self._consecutive_mismatch_frames,
        ]:
            store.pop(session_id, None)

    def _decode_image(self, image_base64: str) -> np.ndarray | None:
        """Decode base64 image to numpy array."""
        if cv2 is None or np is None:
            return None
        try:
            payload = image_base64.split(",", 1)[1] if "," in image_base64 else image_base64
            raw = base64.b64decode(payload)
            arr = np.frombuffer(raw, dtype=np.uint8)
            frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            return frame
        except Exception as e:
            logger.debug("[IdentityVerifier] Failed to decode image: %s", e)
            return None

    def _extract_face_embedding(self, frame: np.ndarray) -> tuple[np.ndarray | None, tuple[int, int, int, int] | None]:
        """Extract face embedding from frame using face_auth logic."""
        if cv2 is None or np is None:
            return None, None

        try:
            h, w = frame.shape[:2]
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            gray = cv2.equalizeHist(gray)

            # Use OpenCV Haar cascade for face detection
            cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            cascade = cv2.CascadeClassifier(cascade_path)
            if cascade.empty():
                return None, None

            faces = cascade.detectMultiScale(
                gray,
                scaleFactor=1.08,
                minNeighbors=5,
                minSize=(64, 64),
            )

            if len(faces) == 0:
                return None, None

            # Get largest face
            faces = sorted(faces, key=lambda f: f[2] * f[3], reverse=True)
            x, y, bw, bh = faces[0]
            face_box = (int(x), int(y), int(bw), int(bh))

            # Extract and normalize face embedding
            pad_x = int(bw * 0.18)
            pad_y = int(bh * 0.22)
            x1 = max(0, x - pad_x)
            y1 = max(0, y - pad_y)
            x2 = min(w, x + bw + pad_x)
            y2 = min(h, y + bh + pad_y)
            crop = gray[int(y1):int(y2), int(x1):int(x2)]

            if crop.size == 0:
                return None, face_box

            crop = cv2.resize(crop, (80, 80), interpolation=cv2.INTER_AREA)
            crop = cv2.equalizeHist(crop)
            crop = cv2.GaussianBlur(crop, (3, 3), 0)
            features = crop.astype(np.float32).flatten() / 255.0
            features = features - float(np.mean(features))
            norm = np.linalg.norm(features)
            if norm > 0:
                features = features / norm

            return features.astype(np.float32), face_box

        except Exception as e:
            logger.debug("[IdentityVerifier] Face extraction failed: %s", e)
            return None, None

    def _compute_similarity(self, emb_a: np.ndarray | None, emb_b: np.ndarray | None) -> float:
        """Compute cosine similarity between embeddings."""
        if emb_a is None or emb_b is None or np is None:
            return 0.0
        try:
            a = emb_a.flatten().astype(np.float64)
            b = emb_b.flatten().astype(np.float64)
            if a.shape != b.shape:
                return 0.0
            norm_a = np.linalg.norm(a)
            norm_b = np.linalg.norm(b)
            if norm_a == 0 or norm_b == 0:
                return 0.0
            return float(np.clip(np.dot(a, b) / (norm_a * norm_b), -1.0, 1.0))
        except Exception:
            return 0.0

    def verify_identity(
        self,
        session_id: str,
        image_base64: str | None = None,
        audio_data: bytes | None = None,
        force_check: bool = False,
    ) -> IdentityVerificationResult:
        """
        Verify identity of current user against registered profile.

        Args:
            session_id: Current interview session
            image_base64: Current camera frame (optional)
            audio_data: Current audio sample (optional)
            force_check: Force verification even if interval hasn't passed

        Returns:
            IdentityVerificationResult with verification status
        """
        # TESTING: Skip all identity verification when proctoring disabled
        if settings.proctoring_disabled:
            username = self._registered_username.get(session_id, "")
            return IdentityVerificationResult(
                username=username,
                session_id=session_id,
                face_verified=True,
                voice_verified=True,
                face_score=1.0,
                voice_score=1.0,
                face_mismatch=False,
                voice_mismatch=False,
                both_mismatch=False,
                identity_verified=True,
                face_count=1,
                warning_count=0,
                should_terminate=False,
                termination_reason="",
                details={"proctoring_disabled": True, "note": "Identity verification disabled for testing"},
            )

        username = self._registered_username.get(session_id, "")
        registered_face = self._registered_face_embedding.get(session_id)
        registered_voice = self._registered_voice_embedding.get(session_id)

        now = time.time()
        last_check = self._last_check_time.get(session_id, 0.0)

        # Rate limiting - only check periodically unless forced
        if not force_check and (now - last_check) < settings.identity_check_interval_seconds:
            # Return cached result
            verified = self._identity_verified.get(session_id, True)
            return IdentityVerificationResult(
                username=username,
                session_id=session_id,
                face_verified=verified,
                voice_verified=verified,
                face_score=1.0 if verified else 0.0,
                voice_score=1.0 if verified else 0.0,
                face_mismatch=not verified,
                voice_mismatch=not verified,
                both_mismatch=not verified,
                identity_verified=verified,
                face_count=1 if verified else 0,
                warning_count=self._warning_count.get(session_id, 0),
                should_terminate=False,
                termination_reason="",
                details={"cached": True, "seconds_since_check": round(now - last_check, 2)},
            )

        self._last_check_time[session_id] = now

        # DEBUG: Log identity verification attempt with all state
        logger.info(
            "[IdentityVerify] session=%s, has_username=%s, has_face_emb=%s, has_voice_emb=%s, has_image=%s",
            session_id, bool(username), registered_face is not None, registered_voice is not None, bool(image_base64)
        )

        # No registered profile - attempt auto-registration or skip verification
        if not username:
            # Try to auto-register from current frame if face is visible
            if image_base64:
                frame = self._decode_image(image_base64)
                if frame is not None:
                    current_embedding, face_box = self._extract_face_embedding(frame)
                    if current_embedding is not None:
                        # Auto-register this candidate as baseline
                        auto_username = f"candidate_{session_id[:8]}"
                        self.register_user(
                            session_id=session_id,
                            username=auto_username,
                            face_embedding=current_embedding,
                            voice_embedding=None
                        )
                        logger.info(
                            "[IdentityVerify] Auto-registered session=%s with username=%s from first face detection",
                            session_id, auto_username
                        )
                        return IdentityVerificationResult(
                            username=auto_username,
                            session_id=session_id,
                            face_verified=True,
                            voice_verified=True,
                            face_score=1.0,
                            voice_score=1.0,
                            face_mismatch=False,
                            voice_mismatch=False,
                            both_mismatch=False,
                            identity_verified=True,
                            face_count=1,
                            warning_count=0,
                            should_terminate=False,
                            termination_reason="",
                            details={"auto_registered": True, "note": "Candidate auto-registered from first face detection"},
                        )

            # No face visible to auto-register - skip verification for now (don't terminate)
            logger.warning(
                "[IdentityVerify] No registered user and no face visible for auto-registration, session=%s. Skipping verification.",
                session_id
            )
            return IdentityVerificationResult(
                username="",
                session_id=session_id,
                face_verified=True,  # Allow to continue
                voice_verified=True,
                face_score=1.0,
                voice_score=1.0,
                face_mismatch=False,
                voice_mismatch=False,
                both_mismatch=False,
                identity_verified=True,  # Pass through
                face_count=0,
                warning_count=0,
                should_terminate=False,  # CHANGED: Don't terminate, just skip
                termination_reason="",
                details={"skipped": True, "reason": "no_registered_user_and_no_face_visible", "note": "Identity verification skipped - no baseline registered"},
            )

        # Perform face verification
        face_score = 0.0
        face_verified = False
        face_count = 0
        face_box = None

        if image_base64 and registered_face is not None:
            frame = self._decode_image(image_base64)
            if frame is not None:
                current_embedding, face_box = self._extract_face_embedding(frame)
                face_count = 1 if face_box else 0

                if current_embedding is not None:
                    face_score = self._compute_similarity(registered_face, current_embedding)
                    face_verified = face_score >= settings.identity_face_match_threshold

                    # DEBUG: Log detailed face verification results
                    logger.info(
                        "[IdentityVerify] Face comparison session=%s: score=%.3f, threshold=%.3f, verified=%s, face_count=%d",
                        session_id, face_score, settings.identity_face_match_threshold, face_verified, face_count
                    )
                else:
                    logger.warning("[IdentityVerify] No face extracted from frame for session=%s", session_id)

                self._last_face_box[session_id] = face_box
        else:
            if registered_face is not None and not image_base64:
                logger.info("[IdentityVerify] No image provided for face verification, session=%s", session_id)
            elif image_base64 and registered_face is None:
                logger.info("[IdentityVerify] No registered face embedding for comparison, session=%s", session_id)

        # Perform voice verification (if audio provided)
        voice_score = 0.0
        voice_verified = False

        if audio_data and registered_voice is not None:
            # Voice verification would require processing audio
            # For now, mark as verified if we have the data
            # Full implementation would extract embedding and compare
            voice_verified = True  # Placeholder - implement with voice analysis

        # If no embeddings registered, skip verification
        if registered_face is None and registered_voice is None:
            return IdentityVerificationResult(
                username=username,
                session_id=session_id,
                face_verified=True,
                voice_verified=True,
                face_score=1.0,
                voice_score=1.0,
                face_mismatch=False,
                voice_mismatch=False,
                both_mismatch=False,
                identity_verified=True,
                face_count=face_count,
                warning_count=0,
                should_terminate=False,
                termination_reason="",
                details={"note": "No biometric profile registered - skipping verification"},
            )

        # Determine mismatch type
        face_mismatch = registered_face is not None and not face_verified
        voice_mismatch = registered_voice is not None and not voice_verified
        both_mismatch = face_mismatch and voice_mismatch

        # At least one must match if we have registered biometrics
        identity_verified = not (face_mismatch or voice_mismatch)

        # Track persistence of mismatch
        mismatch_since = self._mismatch_since.get(session_id, 0.0)
        mismatch_duration = 0.0
        consecutive_mismatch = self._consecutive_mismatch_frames.get(session_id, 0)

        if not identity_verified:
            if mismatch_since == 0.0:
                mismatch_since = now
                self._mismatch_since[session_id] = mismatch_since
            mismatch_duration = now - mismatch_since
            # Increment consecutive mismatch counter (Issue #1 fix)
            consecutive_mismatch += 1
            self._consecutive_mismatch_frames[session_id] = consecutive_mismatch
        else:
            # Reset mismatch tracking on successful verification (Issue #1 fix)
            self._mismatch_since[session_id] = 0.0
            mismatch_since = 0.0
            self._consecutive_mismatch_frames[session_id] = 0
            consecutive_mismatch = 0

        # Count warnings for persistent mismatches
        # Require BOTH temporal persistence AND consecutive frames (Issue #1 fix)
        warning_count = self._warning_count.get(session_id, 0)
        should_terminate = False
        termination_reason = ""

        temporal_threshold_met = mismatch_duration >= settings.identity_mismatch_persistence_seconds
        consecutive_threshold_met = consecutive_mismatch >= settings.identity_mismatch_consecutive_frames

        if not identity_verified and temporal_threshold_met and consecutive_threshold_met:
            warning_count += 1
            self._warning_count[session_id] = warning_count

            if warning_count >= settings.max_identity_warnings:
                should_terminate = True
                if both_mismatch:
                    termination_reason = "both_mismatch"
                elif face_mismatch:
                    termination_reason = "face_mismatch"
                elif voice_mismatch:
                    termination_reason = "voice_mismatch"

        self._identity_verified[session_id] = identity_verified

        result = IdentityVerificationResult(
            username=username,
            session_id=session_id,
            face_verified=face_verified,
            voice_verified=voice_verified,
            face_score=face_score,
            voice_score=voice_score,
            face_mismatch=face_mismatch,
            voice_mismatch=voice_mismatch,
            both_mismatch=both_mismatch,
            identity_verified=identity_verified,
            face_count=face_count,
            warning_count=warning_count,
            should_terminate=should_terminate,
            termination_reason=termination_reason,
            details={
                "face_box": face_box,
                "mismatch_duration": round(mismatch_duration, 2),
                "consecutive_mismatch_frames": consecutive_mismatch,
                "temporal_threshold_met": temporal_threshold_met,
                "consecutive_threshold_met": consecutive_threshold_met,
                "face_threshold": settings.identity_face_match_threshold,
                "voice_threshold": settings.identity_voice_match_threshold,
                "mismatch_persistence_required": settings.identity_mismatch_persistence_seconds,
                "consecutive_frames_required": settings.identity_mismatch_consecutive_frames,
                "registered_face": registered_face is not None,
                "registered_voice": registered_voice is not None,
            },
        )

        # Log verification attempt with detailed thresholds (Issue #1 fix)
        if not identity_verified:
            logger.warning(
                "[IdentityVerifier] MISMATCH: session=%s, user=%s, face_score=%.3f (threshold=%.2f), "
                "duration=%.2fs (required=%.1fs), consecutive_frames=%d (required=%d), "
                "temporal_ok=%s, consecutive_ok=%s, warnings=%d, terminate=%s, reason=%s",
                session_id, username, face_score, settings.identity_face_match_threshold,
                mismatch_duration, settings.identity_mismatch_persistence_seconds,
                consecutive_mismatch, settings.identity_mismatch_consecutive_frames,
                temporal_threshold_met, consecutive_threshold_met,
                warning_count, should_terminate, termination_reason or "n/a"
            )
        else:
            logger.debug(
                "[IdentityVerifier] VERIFIED: session=%s, user=%s, face_score=%.3f (threshold=%.2f), "
                "consecutive_frames=%d",
                session_id, username, face_score, settings.identity_face_match_threshold,
                consecutive_mismatch
            )

        return result

    def get_face_box(self, session_id: str) -> tuple[int, int, int, int] | None:
        """Get the last detected face bounding box for overlay."""
        return self._last_face_box.get(session_id)

    def is_identity_verified(self, session_id: str) -> bool:
        """Check if current identity is verified."""
        return self._identity_verified.get(session_id, True)


# Global identity verifier instance
identity_verifier = IdentityVerifier()
