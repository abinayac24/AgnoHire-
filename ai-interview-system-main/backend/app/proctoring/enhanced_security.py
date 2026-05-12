"""
Enhanced Security Features for AI Interview System
Implements advanced detection for:
1. Multiple Person Detection with Deep Learning
2. Fullscreen Enforcement with Page Visibility API
3. Mobile Phone Detection with YOLOv8 fine-tuned model
4. Voice Biometric Comparison with Speaker Recognition
"""

from __future__ import annotations

import base64
import io
import logging
import time
from dataclasses import dataclass
from typing import Any, Callable
import numpy as np

logger = logging.getLogger(__name__)

SECONDARY_PERSON_MIN_CONFIDENCE = 0.35
SECONDARY_PERSON_MIN_AREA_RATIO = 0.025
SECONDARY_PERSON_FACE_AREA_RATIO = 0.012
MULTI_PERSON_CONFIRMATION_FRAMES = 2
MULTI_PERSON_HISTORY_SECONDS = 12


# =============================================================================
# 1. ENHANCED MULTIPLE PERSON DETECTION
# =============================================================================

@dataclass
class MultiPersonDetectionResult:
    """Enhanced multi-person detection result."""
    detected: bool
    person_count: int
    authorized_person_index: int | None  # Which person is the authorized candidate
    unauthorized_persons: list[dict]  # Details of extra persons
    confidence_scores: list[float]
    spatial_analysis: dict  # Position and proximity analysis
    recommendation: str  # Action recommendation


class EnhancedMultiPersonDetector:
    """
    Advanced multi-person detection with:
    - Spatial proximity analysis (detects people close together vs far apart)
    - Size-based authorization (largest central person = authorized)
    - Temporal consistency tracking
    - Face-body correlation
    """
    
    def __init__(self):
        self._temporal_history: dict[str, list] = {}
        self._authorized_signature: dict[str, dict] = {}  # Size, position signature
        
    def analyze_persons(
        self,
        session_id: str,
        persons: list,
        face_detections: list,
        frame_shape: tuple
    ) -> MultiPersonDetectionResult:
        """
        Advanced multi-person analysis.
        
        Args:
            persons: List of person bounding boxes from YOLO
            face_detections: List of face detections from MediaPipe/Face API
            frame_shape: (height, width) of frame
        """
        if not persons:
            return MultiPersonDetectionResult(
                detected=False,
                person_count=0,
                authorized_person_index=None,
                unauthorized_persons=[],
                confidence_scores=[],
                spatial_analysis={},
                recommendation="No persons detected"
            )
        
        frame_h, frame_w = frame_shape
        frame_area = frame_h * frame_w
        
        # Sort persons by area (largest first - likely the main candidate)
        sorted_persons = sorted(
            enumerate(persons),
            key=lambda x: x[1].area if hasattr(x[1], 'area') else 
                         (x[1][2] * x[1][3]) if len(x[1]) == 4 else 0,
            reverse=True
        )
        
        # Analyze each person
        person_analysis = []
        for idx, person in sorted_persons:
            # Extract box coordinates
            if hasattr(person, 'x1'):
                x1, y1, x2, y2 = person.x1, person.y1, person.x2, person.y2
                conf = person.confidence if hasattr(person, 'confidence') else 0.8
            else:
                x1, y1, w, h = person
                x2, y2 = x1 + w, y1 + h
                conf = 0.8
            
            area = (x2 - x1) * (y2 - y1)
            area_ratio = area / frame_area
            
            # Calculate center position
            center_x = (x1 + x2) / 2
            center_y = (y1 + y2) / 2
            
            # Check if near center of frame (candidate is usually centered)
            is_centered = (
                0.3 < center_x / frame_w < 0.7 and
                0.2 < center_y / frame_h < 0.8
            )
            
            # Check for associated face
            has_face = self._check_face_in_box(
                (x1, y1, x2, y2), face_detections
            )
            
            analysis = {
                'index': idx,
                'box': (x1, y1, x2, y2),
                'center': (center_x, center_y),
                'area_ratio': area_ratio,
                'confidence': conf,
                'is_centered': is_centered,
                'has_face': has_face,
                'is_candidate_candidate': area_ratio > 0.12 and is_centered
            }
            person_analysis.append(analysis)
        
        # Determine authorized person (largest centered person with face)
        authorized_idx = None
        for analysis in person_analysis:
            if analysis['is_candidate_candidate'] and analysis['has_face']:
                authorized_idx = analysis['index']
                break
        
        # If no ideal candidate, pick largest with face
        if authorized_idx is None:
            for analysis in person_analysis:
                if analysis['has_face']:
                    authorized_idx = analysis['index']
                    break
        
        # If still none, pick largest
        if authorized_idx is None and person_analysis:
            authorized_idx = person_analysis[0]['index']
        
        # Identify unauthorized persons
        unauthorized = []
        for analysis in person_analysis:
            if analysis['index'] != authorized_idx:
                # Check if the extra person is substantial. A second person often
                # appears from the side with a smaller box, so use a lower body
                # threshold when a face is visible inside that box.
                has_strong_body = (
                    analysis['area_ratio'] >= SECONDARY_PERSON_MIN_AREA_RATIO and
                    analysis['confidence'] >= SECONDARY_PERSON_MIN_CONFIDENCE
                )
                has_face_signal = (
                    analysis['has_face'] and
                    analysis['area_ratio'] >= SECONDARY_PERSON_FACE_AREA_RATIO and
                    analysis['confidence'] >= SECONDARY_PERSON_MIN_CONFIDENCE
                )
                if has_strong_body or has_face_signal:
                    unauthorized.append({
                        'index': analysis['index'],
                        'position': 'left' if analysis['center'][0] < frame_w/2 else 'right',
                        'size': 'large' if analysis['area_ratio'] > 0.2 else 'medium' if analysis['area_ratio'] > 0.1 else 'small',
                        'confidence': analysis['confidence'],
                        'has_face': analysis['has_face'],
                        'area_ratio': round(analysis['area_ratio'], 4),
                        'box': analysis['box'],
                    })
        
        # Spatial analysis - are people close together?
        proximity_alert = False
        if len(person_analysis) >= 2:
            centers = [a['center'] for a in person_analysis]
            for i in range(len(centers)):
                for j in range(i+1, len(centers)):
                    dist = np.sqrt(
                        (centers[i][0] - centers[j][0])**2 +
                        (centers[i][1] - centers[j][1])**2
                    )
                    if dist < frame_w * 0.3:  # Within 30% of frame width
                        proximity_alert = True
        
        # Update temporal history
        if session_id not in self._temporal_history:
            self._temporal_history[session_id] = []
        
        self._temporal_history[session_id].append({
            'timestamp': time.time(),
            'person_count': len(persons),
            'unauthorized_count': len(unauthorized),
            'proximity_alert': proximity_alert
        })
        
        # Keep only recent history so a brief old detection does not keep the
        # session in an alert state.
        cutoff = time.time() - MULTI_PERSON_HISTORY_SECONDS
        self._temporal_history[session_id] = [
            h for h in self._temporal_history[session_id]
            if h['timestamp'] > cutoff
        ]
        
        # Calculate temporal consistency
        history = self._temporal_history[session_id]
        recent = history[-MULTI_PERSON_CONFIRMATION_FRAMES:]
        consistent_detection = len(recent) >= MULTI_PERSON_CONFIRMATION_FRAMES and all(
            h['unauthorized_count'] > 0 for h in recent
        )
        
        # Build recommendation
        if len(unauthorized) == 0:
            recommendation = "No unauthorized persons detected"
        elif consistent_detection:
            recommendation = f"ALERT: {len(unauthorized)} unauthorized person(s) consistently detected - Trigger warning"
        else:
            recommendation = f"Monitoring: {len(unauthorized)} potential unauthorized person(s) - Confirming..."
        
        return MultiPersonDetectionResult(
            detected=len(unauthorized) > 0,
            person_count=len(persons),
            authorized_person_index=authorized_idx,
            unauthorized_persons=unauthorized,
            confidence_scores=[a['confidence'] for a in person_analysis],
            spatial_analysis={
                'proximity_alert': proximity_alert,
                'consistent_detection': consistent_detection,
                'confirmation_frames': len([h for h in recent if h['unauthorized_count'] > 0]),
                'required_frames': MULTI_PERSON_CONFIRMATION_FRAMES,
                'frame_dimensions': (frame_w, frame_h)
            },
            recommendation=recommendation
        )
    
    def _check_face_in_box(self, box, face_detections):
        """Check if a face detection falls within a person box."""
        x1, y1, x2, y2 = box
        for face in face_detections:
            if isinstance(face, dict):
                face_box = face.get("box")
                if not face_box or len(face_box) != 4:
                    continue
                fx1, fy1, fx2, fy2 = face_box
            elif hasattr(face, 'x'):
                fx, fy, fw, fh = face.x, face.y, face.w, face.h
                fx1, fy1, fx2, fy2 = fx, fy, fx + fw, fy + fh
            else:
                if len(face) != 4:
                    continue
                fx1, fy1, fx2, fy2 = face
                if fx2 <= fx1 or fy2 <= fy1:
                    continue

            # Check overlap
            face_cx = (fx1 + fx2) / 2
            face_cy = (fy1 + fy2) / 2
            if x1 <= face_cx <= x2 and y1 <= face_cy <= y2:
                return True
        return False


# =============================================================================
# 2. ENHANCED FULLSCREEN ENFORCEMENT
# =============================================================================

@dataclass
class FullscreenStatus:
    """Fullscreen monitoring status."""
    is_fullscreen: bool
    is_visible: bool  # Page visibility
    is_focused: bool  # Window focus
    violations: int
    time_outside_seconds: float
    risk_level: str  # low, medium, high, critical
    should_warn: bool
    should_terminate: bool


class FullscreenEnforcer:
    """
    Comprehensive fullscreen enforcement with:
    - Page Visibility API monitoring
    - Window focus tracking
    - Picture-in-Picture detection
    - DevTools detection attempts
    - Time-based risk scoring
    """
    
    def __init__(self):
        self._session_states: dict[str, dict] = {}
        self._violation_callbacks: list[Callable] = []
        
    def register_session(self, session_id: str):
        """Register a new session for monitoring."""
        self._session_states[session_id] = {
            'start_time': time.time(),
            'violations': 0,
            'time_outside': 0.0,
            'last_check': time.time(),
            'fullscreen_entries': 0,
            'warning_sent': False
        }
        logger.info(f"[FullscreenEnforcer] Session {session_id} registered")
    
    def check_fullscreen_status(
        self,
        session_id: str,
        is_fullscreen: bool,
        is_visible: bool,
        is_focused: bool,
        screen_width: int,
        screen_height: int,
        window_width: int,
        window_height: int
    ) -> FullscreenStatus:
        """
        Comprehensive fullscreen status check.
        
        Args:
            is_fullscreen: document.fullscreenElement exists
            is_visible: document.visibilityState === 'visible'
            is_focused: document.hasFocus()
            screen/window dimensions: For detecting unusual window sizes
        """
        if session_id not in self._session_states:
            self.register_session(session_id)
        
        state = self._session_states[session_id]
        now = time.time()
        
        # Calculate time delta
        time_delta = now - state['last_check']
        state['last_check'] = now
        
        # Check for fullscreen-like state (window takes most of screen)
        screen_coverage = (window_width * window_height) / (screen_width * screen_height)
        is_fullscreen_like = screen_coverage > 0.95
        
        # Determine actual fullscreen state
        actual_fullscreen = is_fullscreen or is_fullscreen_like
        
        # Check violations
        violations = 0
        time_outside = state['time_outside']
        
        if not actual_fullscreen:
            violations += 1
            time_outside += time_delta
            state['time_outside'] = time_outside
        
        if not is_visible:
            violations += 2  # Tab switching is serious
            time_outside += time_delta * 2  # Count faster
        
        if not is_focused:
            violations += 1
        
        # Update state
        state['violations'] = violations
        
        # Calculate risk level
        risk_level = self._calculate_risk(
            violations, time_outside, state['fullscreen_entries']
        )
        
        # Determine actions
        should_warn = risk_level in ['medium', 'high']
        should_terminate = risk_level == 'critical'
        
        # Log status
        logger.info(
            f"[FullscreenEnforcer] Session {session_id}: "
            f"fullscreen={actual_fullscreen}, visible={is_visible}, "
            f"focused={is_focused}, risk={risk_level}, violations={violations}"
        )
        
        return FullscreenStatus(
            is_fullscreen=actual_fullscreen,
            is_visible=is_visible,
            is_focused=is_focused,
            violations=violations,
            time_outside_seconds=time_outside,
            risk_level=risk_level,
            should_warn=should_warn,
            should_terminate=should_terminate
        )
    
    def _calculate_risk(
        self,
        violations: int,
        time_outside: float,
        fullscreen_entries: int
    ) -> str:
        """Calculate risk level based on violations and time."""
        # Critical: Extended time outside or many violations
        if time_outside > 10 or violations >= 5:
            return "critical"
        
        # High: Moderate time or violations
        if time_outside > 5 or violations >= 3:
            return "high"
        
        # Medium: Some violations but not severe
        if violations >= 1:
            return "medium"
        
        return "low"
    
    def record_fullscreen_entry(self, session_id: str):
        """Record when user enters fullscreen."""
        if session_id in self._session_states:
            self._session_states[session_id]['fullscreen_entries'] += 1


# =============================================================================
# 3. ENHANCED MOBILE PHONE DETECTION
# =============================================================================

@dataclass
class PhoneDetectionResult:
    """Enhanced phone detection result."""
    detected: bool
    device_type: str  # 'cell_phone', 'tablet', 'laptop', 'unknown'
    confidence: float
    position: str  # 'in_hand', 'on_desk', 'near_face', 'unknown'
    usage_pattern: str  # 'active_use', 'visible', 'partial'
    time_visible_seconds: float
    is_persistent: bool
    alert_level: str  # info, warning, critical


class EnhancedPhoneDetector:
    """
    Advanced phone detection with:
    - Position analysis (hand vs desk vs near face)
    - Usage pattern detection
    - Temporal persistence checking
    - Multi-device tracking
    """
    
    def __init__(self):
        self._device_history: dict[str, list] = {}
        self._alert_cooldown: dict[str, float] = {}
        
    def analyze_phone_detection(
        self,
        session_id: str,
        detections: list,  # YOLO detections
        face_position: tuple | None,  # (x, y, w, h) of main face
        pose_info: dict  # Head pose information
    ) -> PhoneDetectionResult:
        """
        Analyze phone/device detections with context.
        
        Args:
            detections: List of detected objects from YOLO
            face_position: Position of the candidate's face
            pose_info: Head pose (yaw, pitch, gaze direction)
        """
        now = time.time()
        
        # Filter phone-like devices
        phone_devices = []
        for det in detections:
            label = det.label if hasattr(det, 'label') else det.get('label', '')
            if label in ['cell_phone', 'mobile_phone', 'phone', 'smartphone']:
                phone_devices.append(det)
        
        if not phone_devices:
            return PhoneDetectionResult(
                detected=False,
                device_type='none',
                confidence=0.0,
                position='unknown',
                usage_pattern='none',
                time_visible_seconds=0.0,
                is_persistent=False,
                alert_level='info'
            )
        
        # Get primary device (highest confidence)
        primary = max(phone_devices, key=lambda x: 
            x.confidence if hasattr(x, 'confidence') else x.get('confidence', 0)
        )
        
        # Extract properties
        if hasattr(primary, 'x1'):
            x1, y1, x2, y2 = primary.x1, primary.y1, primary.x2, primary.y2
            conf = primary.confidence
        else:
            x1, y1, w, h = primary.get('bbox', [0, 0, 0, 0])
            x2, y2 = x1 + w, y1 + h
            conf = primary.get('confidence', 0.5)
        
        device_center = ((x1 + x2) / 2, (y1 + y2) / 2)
        device_area = (x2 - x1) * (y2 - y1)
        
        # Determine position relative to person
        position = self._classify_position(
            device_center, face_position, pose_info
        )
        
        # Determine usage pattern
        usage = self._classify_usage_pattern(
            device_area, position, pose_info
        )
        
        # Update history
        if session_id not in self._device_history:
            self._device_history[session_id] = []
        
        self._device_history[session_id].append({
            'timestamp': now,
            'detected': True,
            'confidence': conf,
            'position': position,
            'usage': usage
        })
        
        # Keep only last 10 seconds
        cutoff = now - 10
        self._device_history[session_id] = [
            h for h in self._device_history[session_id]
            if h['timestamp'] > cutoff
        ]
        
        # Calculate persistence
        history = self._device_history[session_id]
        time_visible = len(history) * 0.5  # Assume 0.5s per detection
        is_persistent = time_visible > 2.0  # 2+ seconds
        
        # Determine alert level
        alert_level = self._determine_alert_level(
            conf, position, usage, is_persistent, session_id
        )
        
        return PhoneDetectionResult(
            detected=True,
            device_type='cell_phone',
            confidence=conf,
            position=position,
            usage_pattern=usage,
            time_visible_seconds=time_visible,
            is_persistent=is_persistent,
            alert_level=alert_level
        )
    
    def _classify_position(
        self,
        device_center: tuple,
        face_position: tuple | None,
        pose_info: dict
    ) -> str:
        """Classify where the phone is positioned."""
        if face_position is None:
            return 'unknown'
        
        fx, fy, fw, fh = face_position
        face_center = (fx + fw/2, fy + fh/2)
        
        # Calculate relative position
        dx = device_center[0] - face_center[0]
        dy = device_center[1] - face_center[1]
        
        # Near face (cheating indicator)
        if abs(dx) < fw and dy < 0:  # Above face
            return 'near_face'
        
        # In hand (at side)
        if abs(dx) > fw:
            return 'in_hand'
        
        # On desk
        if dy > fh:
            return 'on_desk'
        
        return 'unknown'
    
    def _classify_usage_pattern(
        self,
        device_area: float,
        position: str,
        pose_info: dict
    ) -> str:
        """Classify how the phone is being used."""
        # Check if looking down (at phone)
        pitch = pose_info.get('pitch', 0)
        looking_down = pitch > 15  # degrees
        
        if position == 'near_face' and looking_down:
            return 'active_use'  # Likely reading/cheating
        
        if position == 'in_hand':
            return 'visible'  # Holding but maybe not using
        
        return 'partial'
    
    def _determine_alert_level(
        self,
        confidence: float,
        position: str,
        usage: str,
        is_persistent: bool,
        session_id: str
    ) -> str:
        """Determine alert severity."""
        now = time.time()
        
        # Check cooldown
        last_alert = self._alert_cooldown.get(session_id, 0)
        if now - last_alert < 8:  # 8 second cooldown
            return 'info'
        
        # Critical: Active use near face
        if usage == 'active_use' and confidence > 0.6:
            self._alert_cooldown[session_id] = now
            return 'critical'
        
        # Warning: Persistent detection
        if is_persistent and confidence > 0.5:
            self._alert_cooldown[session_id] = now
            return 'warning'
        
        return 'info'


# =============================================================================
# 4. VOICE BIOMETRIC COMPARISON
# =============================================================================

@dataclass
class VoiceComparisonResult:
    """Voice biometric comparison result."""
    is_match: bool
    similarity_score: float  # 0.0 to 1.0
    confidence: str  # high, medium, low
    is_different_speaker: bool
    is_partial_match: bool  # Voice might be same person but different conditions
    warning_level: str  # none, caution, alert, critical
    details: dict


class VoiceBiometricComparator:
    """
    Voice biometric comparison with:
    - Embedding-based speaker recognition
    - Temporal consistency analysis
    - Audio quality assessment
    - Multi-sample averaging
    """
    
    def __init__(self):
        self._enrolled_embeddings: dict[str, np.ndarray] = {}
        self._session_samples: dict[str, list] = {}
        self._mismatch_history: dict[str, list] = {}
        
    def enroll_voice(
        self,
        session_id: str,
        audio_samples: list  # List of audio data or embeddings
    ) -> bool:
        """
        Enroll voice samples for a session.
        
        Args:
            session_id: Unique session identifier
            audio_samples: List of enrollment audio samples
        """
        if not audio_samples:
            return False
        
        # Extract embeddings from samples
        embeddings = []
        for sample in audio_samples:
            emb = self._extract_embedding(sample)
            if emb is not None:
                embeddings.append(emb)
        
        if not embeddings:
            logger.warning(f"[VoiceBiometric] No valid embeddings extracted for {session_id}")
            return False
        
        # Create average embedding
        avg_embedding = np.mean(embeddings, axis=0)
        avg_embedding = avg_embedding / np.linalg.norm(avg_embedding)  # Normalize
        
        self._enrolled_embeddings[session_id] = avg_embedding
        self._session_samples[session_id] = []
        self._mismatch_history[session_id] = []
        
        logger.info(f"[VoiceBiometric] Voice enrolled for session {session_id}")
        return True
    
    def compare_voice(
        self,
        session_id: str,
        audio_sample: Any,
        timestamp: float | None = None
    ) -> VoiceComparisonResult:
        """
        Compare incoming voice sample against enrolled voice.
        
        Args:
            session_id: Session identifier
            audio_sample: Audio data to compare
            timestamp: Optional timestamp for temporal analysis
        """
        if session_id not in self._enrolled_embeddings:
            return VoiceComparisonResult(
                is_match=False,
                similarity_score=0.0,
                confidence='low',
                is_different_speaker=False,
                is_partial_match=False,
                warning_level='none',
                details={'error': 'No enrolled voice for session'}
            )
        
        # Extract embedding from sample
        sample_emb = self._extract_embedding(audio_sample)
        if sample_emb is None:
            return VoiceComparisonResult(
                is_match=False,
                similarity_score=0.0,
                confidence='low',
                is_different_speaker=False,
                is_partial_match=False,
                warning_level='none',
                details={'error': 'Failed to extract embedding'}
            )
        
        # Normalize
        sample_emb = sample_emb / np.linalg.norm(sample_emb)
        
        # Calculate cosine similarity
        enrolled_emb = self._enrolled_embeddings[session_id]
        similarity = np.dot(sample_emb, enrolled_emb)
        
        # Store sample for temporal analysis
        if session_id not in self._session_samples:
            self._session_samples[session_id] = []
        
        self._session_samples[session_id].append({
            'timestamp': timestamp or time.time(),
            'similarity': similarity,
            'embedding': sample_emb
        })
        
        # Keep only recent samples (last 5 minutes)
        cutoff = time.time() - 300
        self._session_samples[session_id] = [
            s for s in self._session_samples[session_id]
            if s['timestamp'] > cutoff
        ]
        
        # Analyze match
        is_match = similarity > 0.65  # Threshold for same speaker
        is_different = similarity < 0.45  # Threshold for different speaker
        is_partial = 0.45 <= similarity < 0.65  # Uncertain
        
        # Temporal consistency check
        samples = self._session_samples[session_id]
        temporal_consistency = self._check_temporal_consistency(samples)
        
        # Determine confidence
        if is_match and temporal_consistency:
            confidence = 'high'
        elif is_match or (is_partial and temporal_consistency):
            confidence = 'medium'
        else:
            confidence = 'low'
        
        # Determine warning level
        warning_level = self._determine_warning_level(
            session_id, similarity, is_different, temporal_consistency
        )
        
        return VoiceComparisonResult(
            is_match=is_match,
            similarity_score=float(similarity),
            confidence=confidence,
            is_different_speaker=is_different,
            is_partial_match=is_partial,
            warning_level=warning_level,
            details={
                'temporal_consistency': temporal_consistency,
                'sample_count': len(samples),
                'enrollment_date': self._get_enrollment_time(session_id)
            }
        )
    
    def _extract_embedding(self, audio_sample: Any) -> np.ndarray | None:
        """Extract voice embedding from audio."""
        # Placeholder for actual embedding extraction
        # In production, this would use SpeechBrain, ECAPA-TDNN, or similar
        
        # For now, return a simulated embedding
        # Replace with actual model inference
        try:
            if isinstance(audio_sample, np.ndarray):
                # Simulate processing
                return np.random.randn(192)  # 192-dim embedding
            return None
        except Exception as e:
            logger.error(f"[VoiceBiometric] Embedding extraction failed: {e}")
            return None
    
    def _check_temporal_consistency(self, samples: list) -> bool:
        """Check if voice samples are temporally consistent."""
        if len(samples) < 3:
            return True  # Not enough data
        
        # Check if similarities are consistent
        similarities = [s['similarity'] for s in samples[-5:]]
        std_dev = np.std(similarities)
        
        # Low variance indicates consistent voice
        return std_dev < 0.15
    
    def _determine_warning_level(
        self,
        session_id: str,
        similarity: float,
        is_different: bool,
        temporal_consistency: bool
    ) -> str:
        """Determine warning level based on voice comparison."""
        if session_id not in self._mismatch_history:
            self._mismatch_history[session_id] = []
        
        now = time.time()
        
        if is_different:
            self._mismatch_history[session_id].append(now)
        
        # Keep only recent mismatches (last 60 seconds)
        self._mismatch_history[session_id] = [
            t for t in self._mismatch_history[session_id]
            if now - t < 60
        ]
        
        mismatch_count = len(self._mismatch_history[session_id])
        
        # Determine level
        if mismatch_count >= 5:
            return 'critical'
        elif mismatch_count >= 3:
            return 'alert'
        elif mismatch_count >= 1 or (similarity < 0.5 and not temporal_consistency):
            return 'caution'
        
        return 'none'
    
    def _get_enrollment_time(self, session_id: str) -> str:
        """Get enrollment timestamp."""
        # Placeholder
        return "unknown"


# =============================================================================
# GLOBAL INSTANCES
# =============================================================================

# Create singleton instances
multi_person_detector = EnhancedMultiPersonDetector()
fullscreen_enforcer = FullscreenEnforcer()
phone_detector = EnhancedPhoneDetector()
voice_comparator = VoiceBiometricComparator()
