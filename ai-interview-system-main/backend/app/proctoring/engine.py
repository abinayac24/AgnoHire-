from __future__ import annotations

from datetime import datetime
import logging
import time

from app.proctoring.alert_log import alert_log_store
from app.proctoring.assistance_detector import AssistanceDetector
from app.proctoring.config import settings
from app.proctoring.detectors import (
    Box,
    FaceGazeHeadPoseDetector,
    YoloObjectDetector,
    annotate_frame,
    decode_base64_image,
    encode_base64_image,
)
from app.proctoring.identity_verifier import identity_verifier, IdentityVerificationResult
from app.proctoring.schemas import DetectionBox, FrameAnalyzeResponse, ViolationEvent

# Import enhanced security features
from app.proctoring.enhanced_security import (
    multi_person_detector,
    phone_detector,
    EnhancedMultiPersonDetector,
    EnhancedPhoneDetector,
    FullscreenEnforcer,
    VoiceBiometricComparator
)


logger = logging.getLogger(__name__)

# Tunable Configuration Constants for Multi-Person Detection
PERSON_CONFIDENCE_THRESHOLD = 0.65
MIN_PERSON_BOX_AREA_RATIO = 0.04
MULTI_PERSON_PERSISTENCE_SECONDS = 2.5
EDGE_IGNORE_MARGIN_RATIO = 0.08
MULTI_PERSON_CONFIRMATION_FRAMES = 5
WARNING_COOLDOWN_SECONDS = 5
PHONE_CONFIRMATION_FRAMES = 2
PHONE_MIN_CONFIDENCE = 0.45
PHONE_MIN_AREA_RATIO = 0.0015
PHONE_MIN_HEAD_AREA_RATIO = 0.012
USER_FACING_RULES = {"mobile_phone", "multiple_people", "voice_identity", "voice_multi_speaker"}

# Tunable Configuration Constants for Partial Human Detection
PARTIAL_HUMAN_CONFIDENCE_THRESHOLD = 0.75
MIN_PARTIAL_BOX_AREA_RATIO = 0.05
PARTIAL_HUMAN_PERSISTENCE_SECONDS = 2.5
PARTIAL_EDGE_IGNORE_MARGIN_RATIO = 0.10
PARTIAL_WARNING_COOLDOWN_SECONDS = 5

class ProctoringEngine:
    def __init__(self) -> None:
        self.yolo = YoloObjectDetector()
        self.face_pose = FaceGazeHeadPoseDetector()
        self._last_frame_ts: dict[str, float] = {}
        self._phone_seen_since: dict[str, float] = {}
        self._phone_confirmation_count: dict[str, int] = {}
        self._last_phone_alert_at: dict[str, float] = {}
        self._phone_warnings_count: dict[str, int] = {}
        self._partial_seen_since: dict[str, float] = {}
        self._last_partial_alert_at: dict[str, float] = {}

        # Multi-person detection state
        self._multi_person_seen_since: dict[str, float] = {}
        self._multi_person_confirmation_count: dict[str, int] = {}
        self._last_multi_person_alert_at: dict[str, float] = {}
        self._multi_person_warnings_count: dict[str, int] = {}
        
        # Gaze and Head Pose Monitoring State
        self._gaze_history: dict[str, list[float]] = {}
        self._head_turn_count: dict[str, int] = {}
        self._last_head_turn_at: dict[str, float] = {}
        self._device_seen_since: dict[str, float] = {}
        self.assistance_detector = AssistanceDetector()

    def _fps(self, session_id: str) -> float:
        now = time.time()
        prev = self._last_frame_ts.get(session_id)
        self._last_frame_ts[session_id] = now
        if not prev:
            return 0.0
        delta = max(1e-3, now - prev)
        return 1.0 / delta

    def _multi_person_stability(
        self,
        session_id: str,
        persons: list[Box],
        pose_info: dict,
        now: float,
        frame_width: int,
        frame_height: int,
    ) -> tuple[bool, dict]:
        frame_area = max(1, frame_width * frame_height)
        edge_margin = int(frame_width * EDGE_IGNORE_MARGIN_RATIO)
        
        valid_persons = []
        for i, box in enumerate(persons):
            area_ratio = box.area / frame_area
            is_near_edge = box.x1 <= edge_margin or box.x2 >= (frame_width - edge_margin)
            
            # 2. CONFIDENCE FILTER
            if box.confidence < PERSON_CONFIDENCE_THRESHOLD:
                logger.debug("[Proctoring] Person %d rejected: confidence %.3f < %.2f", i, box.confidence, PERSON_CONFIDENCE_THRESHOLD)
                continue
                
            # 3. MINIMUM SIZE FILTER
            if area_ratio < MIN_PERSON_BOX_AREA_RATIO:
                logger.debug("[Proctoring] Person %d rejected: area_ratio %.4f too small (<%.4f)", i, area_ratio, MIN_PERSON_BOX_AREA_RATIO)
                continue

            # 4. EDGE FILTER: Ignore detections near edges unless substantial (2x min area)
            if is_near_edge and area_ratio < (MIN_PERSON_BOX_AREA_RATIO * 2.0):
                logger.debug("[Proctoring] Person %d rejected: near edge and not substantial (area_ratio=%.4f < %.4f)", i, area_ratio, MIN_PERSON_BOX_AREA_RATIO * 2.0)
                continue

            valid_persons.append(box)

        # 6. FACE CORRELATION
        face_count = int(pose_info.get("faces", 0) or 0)
        has_multi_person = len(valid_persons) > 1
        has_face_correlation = face_count >= 2
        
        # Confirm candidate if:
        # - Multiple faces detected
        # - 3+ solid person boxes
        # - 2 people AND 2nd person is extremely high confidence (>0.92)
        extra_person_solid = any(p.confidence > 0.92 for p in valid_persons[1:])
        candidate = has_multi_person and (has_face_correlation or len(valid_persons) >= 3 or extra_person_solid)
        
        rejection_reason = ""
        if has_multi_person and not candidate:
            rejection_reason = "multi-person detected but failed face correlation and high-confidence check"

        # 5. CONSECUTIVE FRAME CONFIRMATION
        if candidate:
            conf_count = self._multi_person_confirmation_count.get(session_id, 0) + 1
            self._multi_person_confirmation_count[session_id] = conf_count
            
            # Start persistence timer on the first candidate frame
            since = self._multi_person_seen_since.setdefault(session_id, now)
            visible_seconds = now - since
        else:
            self._multi_person_confirmation_count[session_id] = 0
            self._multi_person_seen_since.pop(session_id, None)
            visible_seconds = 0.0

        # 1. TEMPORAL PERSISTENCE
        persistent = visible_seconds >= MULTI_PERSON_PERSISTENCE_SECONDS
        confirmed_frames = self._multi_person_confirmation_count.get(session_id, 0) >= MULTI_PERSON_CONFIRMATION_FRAMES
        
        # 7. WARNING COOLDOWN
        last_alert = self._last_multi_person_alert_at.get(session_id, 0.0)
        cooldown_remaining = max(0.0, WARNING_COOLDOWN_SECONDS - (now - last_alert))
        allowed_by_cooldown = cooldown_remaining <= 0
        
        should_alert = bool(candidate and persistent and confirmed_frames and allowed_by_cooldown)
        
        if should_alert:
            self._last_multi_person_alert_at[session_id] = now
            self._multi_person_warnings_count[session_id] = self._multi_person_warnings_count.get(session_id, 0) + 1

        warnings_count = self._multi_person_warnings_count.get(session_id, 0)
        
        details = {
            "valid_person_count": len(valid_persons),
            "face_count": face_count,
            "face_correlation": has_face_correlation,
            "candidate": candidate,
            "confirmation_frames": self._multi_person_confirmation_count.get(session_id, 0),
            "visible_seconds": round(visible_seconds, 2),
            "cooldown_remaining": round(cooldown_remaining, 2),
            "warnings_count": warnings_count,
            "termination_imminent": warnings_count >= 3,
            "reason": rejection_reason or ("multi_person_confirmed" if should_alert else "stability_check"),
        }

        # DEBUG LOGGING
        logger.debug(
            "[Proctoring] multi-person decision session=%s | valid=%d | faces=%d | candidate=%s | frames=%d | visible=%.2fs | alert=%s | warnings=%d | reason=%s",
            session_id, len(valid_persons), face_count, candidate, 
            details["confirmation_frames"], visible_seconds, should_alert, warnings_count, details["reason"]
        )
        
        return should_alert, details


    @staticmethod
    def _build_event(session_id: str, rule: str, message: str, details: dict) -> ViolationEvent:
        return ViolationEvent(
            timestamp=datetime.utcnow(),
            session_id=session_id,
            rule=rule,
            message=message,
            severity="high",
            details=details,
        )

    def _multiple_people_count_alert(
        self,
        session_id: str,
        persons: list[Box],
        pose_info: dict,
        now: float,
        frame_width: int,
        frame_height: int,
    ) -> tuple[bool, dict]:
        person_count = len(persons)
        has_multiple_people = person_count > 1

        if has_multiple_people:
            conf_count = self._multi_person_confirmation_count.get(session_id, 0) + 1
            self._multi_person_confirmation_count[session_id] = conf_count
            since = self._multi_person_seen_since.setdefault(session_id, now)
            visible_seconds = now - since
        else:
            self._multi_person_confirmation_count[session_id] = 0
            self._multi_person_seen_since.pop(session_id, None)
            visible_seconds = 0.0

        confirmed = self._multi_person_confirmation_count.get(session_id, 0) >= 2
        last_alert = self._last_multi_person_alert_at.get(session_id, 0.0)
        cooldown_remaining = max(0.0, WARNING_COOLDOWN_SECONDS - (now - last_alert))
        allowed_by_cooldown = cooldown_remaining <= 0
        should_alert = bool(has_multiple_people and confirmed and allowed_by_cooldown)

        if should_alert:
            self._last_multi_person_alert_at[session_id] = now
            self._multi_person_warnings_count[session_id] = (
                self._multi_person_warnings_count.get(session_id, 0) + 1
            )

        frame_area = max(1, frame_width * frame_height)
        details = {
            "person_count": person_count,
            "face_count": int(pose_info.get("faces", 0) or 0),
            "candidate": has_multiple_people,
            "confirmation_frames": self._multi_person_confirmation_count.get(session_id, 0),
            "required_frames": 2,
            "visible_seconds": round(visible_seconds, 2),
            "cooldown_remaining": round(cooldown_remaining, 2),
            "warnings_count": self._multi_person_warnings_count.get(session_id, 0),
            "detection_method": "yolo_person_count",
            "persons": [
                {
                    "confidence": round(box.confidence, 3),
                    "area_ratio": round(box.area / frame_area, 4),
                    "box": [box.x1, box.y1, box.x2, box.y2],
                    "partial": box.partial,
                }
                for box in persons
            ],
        }
        return should_alert, details

    def _mobile_phone_count_alert(
        self,
        session_id: str,
        phones: list[Box],
        pose_info: dict,
        now: float,
        frame_area: int,
        frame_width: int,
        frame_height: int,
    ) -> tuple[bool, dict]:
        min_confidence = max(PHONE_MIN_CONFIDENCE, settings.phone_conf_threshold)
        confirmed_phones = []
        ignored_audio_devices = []

        for box in phones:
            area_ratio = box.area / max(1, frame_area)
            if box.label != "cell_phone" or box.confidence < min_confidence or area_ratio < PHONE_MIN_AREA_RATIO:
                continue
            if self._looks_like_wearable_audio(box, pose_info, frame_area, frame_width, frame_height):
                ignored_audio_devices.append(box)
                continue
            confirmed_phones.append(box)

        if confirmed_phones:
            self._phone_confirmation_count[session_id] = (
                self._phone_confirmation_count.get(session_id, 0) + 1
            )
            since = self._phone_seen_since.setdefault(session_id, now)
            visible_seconds = now - since
        else:
            self._phone_confirmation_count[session_id] = 0
            self._phone_seen_since.pop(session_id, None)
            visible_seconds = 0.0

        confirmed = self._phone_confirmation_count.get(session_id, 0) >= PHONE_CONFIRMATION_FRAMES
        last_alert = self._last_phone_alert_at.get(session_id, 0.0)
        cooldown_remaining = max(0.0, WARNING_COOLDOWN_SECONDS - (now - last_alert))
        allowed_by_cooldown = cooldown_remaining <= 0
        should_alert = bool(confirmed_phones and confirmed and allowed_by_cooldown)

        if should_alert:
            self._last_phone_alert_at[session_id] = now
            self._phone_warnings_count[session_id] = (
                self._phone_warnings_count.get(session_id, 0) + 1
            )

        details = {
            "phone_count": len(confirmed_phones),
            "candidate": bool(confirmed_phones),
            "confirmation_frames": self._phone_confirmation_count.get(session_id, 0),
            "required_frames": PHONE_CONFIRMATION_FRAMES,
            "visible_seconds": round(visible_seconds, 2),
            "cooldown_remaining": round(cooldown_remaining, 2),
            "warnings_count": self._phone_warnings_count.get(session_id, 0),
            "min_confidence": min_confidence,
            "ignored_audio_device_count": len(ignored_audio_devices),
            "ignored_audio_devices": [
                {
                    "confidence": round(box.confidence, 3),
                    "area_ratio": round(box.area / max(1, frame_area), 4),
                    "box": [box.x1, box.y1, box.x2, box.y2],
                    "reason": "likely_earbuds_headphones",
                }
                for box in ignored_audio_devices
            ],
            "device_details": [
                {
                    "confidence": round(box.confidence, 3),
                    "area_ratio": round(box.area / max(1, frame_area), 4),
                    "box": [box.x1, box.y1, box.x2, box.y2],
                    "partial": box.partial,
                }
                for box in confirmed_phones
            ],
        }
        return should_alert, details

    @staticmethod
    def _box_overlap_ratio(a: Box, face_box: tuple[int, int, int, int]) -> float:
        fx1, fy1, fx2, fy2 = face_box
        ix1 = max(a.x1, fx1)
        iy1 = max(a.y1, fy1)
        ix2 = min(a.x2, fx2)
        iy2 = min(a.y2, fy2)
        intersection = max(0, ix2 - ix1) * max(0, iy2 - iy1)
        return intersection / max(1, a.area)

    def _looks_like_wearable_audio(
        self,
        box: Box,
        pose_info: dict,
        frame_area: int,
        frame_width: int,
        frame_height: int,
    ) -> bool:
        area_ratio = box.area / max(1, frame_area)
        width = max(1, box.x2 - box.x1)
        height = max(1, box.y2 - box.y1)
        aspect = height / width
        phone_like_aspect = 1.25 <= aspect <= 2.8
        center_x = (box.x1 + box.x2) / 2
        center_y = (box.y1 + box.y2) / 2

        for face in pose_info.get("face_detections", []):
            face_box = face.get("box") if isinstance(face, dict) else None
            if not face_box or len(face_box) != 4:
                continue
            fx1, fy1, fx2, fy2 = face_box
            face_w = max(1, fx2 - fx1)
            face_h = max(1, fy2 - fy1)
            head_x1 = max(0, fx1 - int(face_w * 0.75))
            head_x2 = min(frame_width, fx2 + int(face_w * 0.75))
            head_y1 = max(0, fy1 - int(face_h * 0.45))
            head_y2 = min(frame_height, fy2 + int(face_h * 0.35))
            near_head = head_x1 <= center_x <= head_x2 and head_y1 <= center_y <= head_y2
            overlaps_face = self._box_overlap_ratio(box, (fx1, fy1, fx2, fy2)) > 0.25

            if near_head and area_ratio < PHONE_MIN_HEAD_AREA_RATIO:
                return True
            if near_head and overlaps_face and not phone_like_aspect:
                return True

        return False

    def _partial_human_stability(
        self,
        session_id: str,
        partial_humans: list[Box],
        pose_info: dict,
        now: float,
        frame_width: int,
        frame_height: int,
    ) -> tuple[bool, dict]:
        frame_area = max(1, frame_width * frame_height)
        edge_margin = int(frame_width * PARTIAL_EDGE_IGNORE_MARGIN_RATIO)
        
        valid_partials = []
        for i, box in enumerate(partial_humans):
            area_ratio = box.area / frame_area
            is_near_edge = box.x1 <= edge_margin or box.x2 >= (frame_width - edge_margin)
            
            # 2. CONFIDENCE FILTER
            if box.confidence < PARTIAL_HUMAN_CONFIDENCE_THRESHOLD:
                logger.debug("[Proctoring] Partial human %d rejected: confidence %.3f < %.2f", i, box.confidence, PARTIAL_HUMAN_CONFIDENCE_THRESHOLD)
                continue
                
            # 3. MINIMUM SIZE FILTER
            if area_ratio < MIN_PARTIAL_BOX_AREA_RATIO:
                logger.debug("[Proctoring] Partial human %d rejected: area_ratio %.4f too small (<%.4f)", i, area_ratio, MIN_PARTIAL_BOX_AREA_RATIO)
                continue

            # 4. EDGE TOLERANCE: Ignore detections near edges unless substantial (2x min area)
            # This helps allow candidate's own shoulders/hair near edges.
            if is_near_edge and area_ratio < (MIN_PARTIAL_BOX_AREA_RATIO * 2.0):
                logger.debug("[Proctoring] Partial human %d rejected: near edge and not substantial (area_ratio=%.4f < %.4f)", i, area_ratio, MIN_PARTIAL_BOX_AREA_RATIO * 2.0)
                continue

            valid_partials.append(box)

        # 5. FACE/CENTER CORRELATION
        face_count = int(pose_info.get("faces", 0) or 0)
        pose_alert = bool(pose_info.get("partial_human_pose_alert", False))
        has_face_correlation = face_count >= 2

        is_candidate_centered = (
            abs(pose_info.get("yaw", 0.0)) < 12 and
            abs(pose_info.get("pitch", 0.0)) < 12
        )

        candidate = False

        # Strongest signal: multiple faces detected
        if has_face_correlation:
            candidate = True
        # Candidate not centered + strong partial detection
        elif not is_candidate_centered:
            candidate = any(
                p.confidence > 0.85 and
                (p.area / frame_area) > (MIN_PARTIAL_BOX_AREA_RATIO * 1.8)
                for p in valid_partials
            )
        # Pose alert + very strong partial detection
        elif pose_alert:
            candidate = any(
                p.confidence > 0.90 and
                (p.area / frame_area) > (MIN_PARTIAL_BOX_AREA_RATIO * 2.0)
                for p in valid_partials
            )

        rejection_reason = ""
        if valid_partials and not candidate:
            rejection_reason = (
                "partial detection ignored - likely candidate shoulder/hair/background noise"
            )
        # 1. TEMPORAL PERSISTENCE
        if candidate:
            since = self._partial_seen_since.setdefault(session_id, now)
            visible_seconds = now - since
        else:
            self._partial_seen_since.pop(session_id, None)
            visible_seconds = 0.0

        persistent = visible_seconds >= PARTIAL_HUMAN_PERSISTENCE_SECONDS
        
        # 6. STABILITY / DEBOUNCE (Warning Cooldown)
        last_alert = self._last_partial_alert_at.get(session_id, 0.0)
        cooldown_remaining = max(0.0, PARTIAL_WARNING_COOLDOWN_SECONDS - (now - last_alert))
        allowed_by_cooldown = cooldown_remaining <= 0
        
        should_alert = bool(candidate and persistent and allowed_by_cooldown)

        if should_alert:
            self._last_partial_alert_at[session_id] = now

        # 7. WARNING SAFETY: Count only validated persistent detections
        details = {
            "partial_boxes": len(valid_partials),
            "pose_alert": pose_alert,
            "faces": face_count,
            "face_correlation": has_face_correlation,
            "candidate": candidate,
            "visible_seconds": round(visible_seconds, 2),
            "required_seconds": PARTIAL_HUMAN_PERSISTENCE_SECONDS,
            "cooldown_remaining": round(cooldown_remaining, 2),
            "max_confidence": round(max((p.confidence for p in valid_partials), default=0.0), 3),
            "max_box_area_ratio": round(max((p.area / frame_area for p in valid_partials), default=0.0), 4),
            "reason": rejection_reason or ("persistent_partial_human" if should_alert else "stability_check"),
        }
        
        # DEBUG LOGGING
        logger.debug(
            "[Proctoring] Partial human decision: session=%s | boxes=%d | conf=%.3f | area=%.4f | visible=%.2fs | alert=%s | reason=%s",
            session_id, len(valid_partials), details["max_confidence"], details["max_box_area_ratio"],
            visible_seconds, should_alert, details["reason"]
        )
        return should_alert, details


    def analyze_base64(self, session_id: str, image_base64: str, include_annotated_image: bool = True) -> FrameAnalyzeResponse:
        # TESTING: Skip all proctoring analysis when disabled
        if settings.proctoring_disabled:
            logger.info("[Proctoring] Analysis skipped (TESTING MODE) for session=%s", session_id)
            return FrameAnalyzeResponse(
                session_id=session_id,
                alerts=[],
                metrics={"proctoring_disabled": True},
                annotated_image=image_base64 if include_annotated_image else None,
            )

        frame = decode_base64_image(image_base64)
        persons, phones, partial_humans = self.yolo.detect(frame)
        pose_info = self.face_pose.analyze(frame, session_id=session_id)
        now = time.time()
        frame_area = max(1, int(frame.shape[0]) * int(frame.shape[1]))

        # INITIAL DETECTION SUMMARY
        laptop_count = len([b for b in phones if b.label == "laptop"])
        monitor_count = len([b for b in phones if b.label == "monitor"])
        phone_count = len([b for b in phones if b.label == "cell_phone"])
        logger.info(
            "[Proctoring] FRAME ANALYSIS START: session=%s, persons=%d, laptops=%d, monitors=%d, "
            "phones=%d, partial_humans=%d, frame=%dx%d",
            session_id, len(persons), laptop_count, monitor_count, phone_count,
            len(partial_humans), frame.shape[1], frame.shape[0]
        )

        alerts: list[ViolationEvent] = []
        alert_messages: list[str] = []

        # MULTIPLE PEOPLE DETECTION
        # Count every YOLO "person" box. The enhanced spatial analyzer is useful
        # as context, but the warning itself is driven by person_count > 1.
        multi_alert, multi_details = self._multiple_people_count_alert(
            session_id,
            persons,
            pose_info,
            now,
            frame.shape[1],
            frame.shape[0],
        )
        if multi_alert:
            msg = f"Multiple people detected ({multi_details['person_count']} people in camera view)"
            if self._multi_person_warnings_count.get(session_id, 0) >= 2:
                msg += " - Final Warning: Termination imminent"
            event = self._build_event(session_id, "multiple_people", msg, multi_details)
            alerts.append(event)
            alert_messages.append(msg)

        partial_alert, partial_details = self._partial_human_stability(
            session_id,
            partial_humans,
            pose_info,
            now,
            frame.shape[1],
            frame.shape[0],
        )
        if partial_alert:
            msg = "Partial human presence detected"
            event = self._build_event(
                session_id,
                "partial_human",
                msg,
                partial_details,
            )
            alerts.append(event)
            alert_messages.append(msg)

        valid_unauthorized_devices = []
        laptops_monitors = []

        for b in phones:
            if b.label in ("laptop", "monitor"):
                laptops_monitors.append(b)
            else:
                valid_unauthorized_devices.append(b)

        # PRIMARY DEVICE LOGIC:
        # - Single laptop/monitor = ALWAYS treat as primary interview device (no warning)
        # - Multiple laptops/monitors = Ignore the largest/central one as primary, flag others
        # - Phones/tablets = ALWAYS unauthorized (no primary device assumption)

        if laptops_monitors:
            # Sort by area (largest first) to identify primary device
            laptops_monitors.sort(key=lambda b: b.area, reverse=True)

            if len(laptops_monitors) == 1:
                # SINGLE LAPTOP: Always treat as primary interview device
                primary = laptops_monitors[0]
                logger.info(
                    "[Proctoring] PRIMARY DEVICE FILTER: Single %s detected - treating as PRIMARY "
                    "interview device (NO WARNING). area=%d, center=(%.1f, %.1f), box=%s",
                    primary.label, primary.area,
                    (primary.x1 + primary.x2) / 2, (primary.y1 + primary.y2) / 2,
                    primary.to_dict()
                )
                # Do NOT add to valid_unauthorized_devices - single laptop is always primary
            else:
                # MULTIPLE LAPTOPS/MONITORS: Ignore primary (largest/central), flag others
                logger.info(
                    "[Proctoring] PRIMARY DEVICE FILTER: %d laptop/monitor devices detected - "
                    "will ignore one as primary, flag remaining",
                    len(laptops_monitors)
                )
                primary_ignored = False
                for b in laptops_monitors:
                    area_ratio = b.area / frame_area
                    center_x = (b.x1 + b.x2) / 2
                    center_y = (b.y1 + b.y2) / 2
                    is_central = (frame.shape[1] * 0.2) < center_x < (frame.shape[1] * 0.8)
                    is_bottom = b.y2 > (frame.shape[0] * 0.7)
                    is_large = area_ratio > 0.08

                    is_primary_candidate = is_central and (is_large or is_bottom)

                    if not primary_ignored and is_primary_candidate:
                        # This is the primary device - ignore it
                        primary_ignored = True
                        logger.info(
                            "[Proctoring]   -> IGNORED as PRIMARY %s (central/large). "
                            "area_ratio=%.3f, center=(%.1f, %.1f)",
                            b.label, area_ratio, center_x, center_y
                        )
                    elif not primary_ignored:
                        # Fallback: first (largest) device is primary
                        primary_ignored = True
                        logger.info(
                            "[Proctoring]   -> IGNORED as FALLBACK PRIMARY %s (largest). "
                            "area_ratio=%.3f, area=%d",
                            b.label, area_ratio, b.area
                        )
                    else:
                        # Secondary device - add to unauthorized
                        valid_unauthorized_devices.append(b)
                        logger.info(
                            "[Proctoring]   -> FLAGGED SECONDARY %s. area_ratio=%.3f, center=(%.1f, %.1f)",
                            b.label, area_ratio, center_x, center_y
                        )

        # Log detection summary
        logger.debug(
            "[Proctoring] Device detection summary: laptops/monitors=%d, phones/tablets=%d, "
            "unauthorized_after_filter=%d",
            len(laptops_monitors), len([b for b in phones if b.label not in ("laptop", "monitor")]),
            len(valid_unauthorized_devices)
        )

        phones = valid_unauthorized_devices

        phone_alert, phone_details = self._mobile_phone_count_alert(
            session_id,
            phones,
            pose_info,
            now,
            frame_area,
            frame.shape[1],
            frame.shape[0],
        )
        phone_visible_seconds = phone_details["visible_seconds"]
        if phone_alert:
            msg = "Mobile phone detected"
            if self._phone_warnings_count.get(session_id, 0) >= 2:
                msg += " - Final Warning: Termination imminent"
            event = self._build_event(session_id, "mobile_phone", msg, phone_details)
            alerts.append(event)
            alert_messages.append(msg)

        if pose_info["look_away_alert"]:
            gaze_direction = pose_info.get("gaze_direction", "away")
            msg = f"User looking {gaze_direction} away from screen"
            event = self._build_event(
                session_id,
                "eye_gaze",
                msg,
                {
                    "look_away_seconds": settings.look_away_seconds,
                    "gaze_direction": gaze_direction,
                    "gaze_horizontal": pose_info.get("gaze_horizontal", 0.0),
                    "gaze_vertical": pose_info.get("gaze_vertical", 0.0),
                },
            )
            alerts.append(event)
            alert_messages.append(msg)

        if pose_info["head_pose_alert"]:
            msg = "Suspicious head movement"
            now = time.time()
            last_turn = self._last_head_turn_at.get(session_id, 0.0)
            if now - last_turn < 5.0:
                self._head_turn_count[session_id] = self._head_turn_count.get(session_id, 0) + 1
            else:
                self._head_turn_count[session_id] = 1
            self._last_head_turn_at[session_id] = now

            if self._head_turn_count[session_id] >= 3:
                msg = "Repeated suspicious head movements"
                event = self._build_event(
                    session_id,
                    "head_pose_repeated",
                    msg,
                    {"yaw": pose_info["yaw"], "pitch": pose_info["pitch"], "count": self._head_turn_count[session_id]},
                )
                alerts.append(event)
                alert_messages.append(msg)
            else:
                event = self._build_event(
                    session_id,
                    "head_pose",
                    msg,
                    {"yaw": pose_info["yaw"], "pitch": pose_info["pitch"]},
                )
                alerts.append(event)
                alert_messages.append(msg)

        # Reading Pattern Detection
        gaze_h = pose_info.get("gaze_horizontal", 0.0)
        history = self._gaze_history.setdefault(session_id, [])
        history.append(gaze_h)
        if len(history) > 30: # Keep last ~3-5 seconds of gaze data
            history.pop(0)

        if len(history) >= 20 and not pose_info["look_away_alert"]:
            # Detect left-to-right scanning (reading)
            # Simplistic check: count direction changes in horizontal gaze
            changes = 0
            for i in range(1, len(history)):
                if (history[i] > 0.05 and history[i-1] < -0.05) or (history[i] < -0.05 and history[i-1] > 0.05):
                    changes += 1

            if changes >= 4: # 2 full left-right-left cycles
                msg = "Potential suspicious reading behavior detected"
                event = self._build_event(
                    session_id,
                    "reading_pattern",
                    msg,
                    {"direction_changes": changes, "gaze_history": history[-10:]},
                )
                alerts.append(event)
                alert_messages.append(msg)
                history.clear() # Reset after alert

        assistance_signal = self.assistance_detector.analyze(session_id, pose_info, now)
        if assistance_signal.should_alert:
            msg = "Suspicious assistance behavior detected"
            logger.warning(
                "[AssistanceDetection] session=%s reason=%s details=%s",
                session_id,
                assistance_signal.reason,
                assistance_signal.details,
            )
            event = self._build_event(
                session_id,
                "assistance_suspected",
                msg,
                assistance_signal.details,
            )
            alerts.append(event)
            alert_messages.append(msg)

        # IDENTITY VERIFICATION - Continuous face/voice matching
        identity_result = identity_verifier.verify_identity(
            session_id=session_id,
            image_base64=image_base64,
            audio_data=None,  # Audio verification can be added separately
        )

        if not identity_result.identity_verified:
            # Unauthorized person detected
            face_box = identity_verifier.get_face_box(session_id)
            msg = "Unauthorized person detected"
            details = {
                "face_mismatch": identity_result.face_mismatch,
                "voice_mismatch": identity_result.voice_mismatch,
                "both_mismatch": identity_result.both_mismatch,
                "face_score": identity_result.face_score,
                "voice_score": identity_result.voice_score,
                "warning_count": identity_result.warning_count,
                "face_box": face_box,
            }

            if identity_result.should_terminate:
                msg = f"Unauthorized person detected - Interview terminating: {identity_result.termination_reason}"
                details["termination_reason"] = identity_result.termination_reason
                details["termination_imminent"] = True

            event = self._build_event(
                session_id,
                "identity_mismatch",
                msg,
                details,
            )
            alerts.append(event)
            alert_messages.append(msg)

        alerts = [event for event in alerts if event.rule in USER_FACING_RULES]
        alert_messages = [event.message for event in alerts]

        for event in alerts:
            alert_log_store.add(event)

        metrics = {
            "strict_mode": settings.strict_sensitivity,
            "faces": pose_info["faces"],
            "person_count": len(persons),
            "phone_count": len(phones),
            "phone_visible_seconds": round(phone_visible_seconds, 2),
            "partial_human_count": len(partial_humans),
            "partial_human_visible_seconds": partial_details["visible_seconds"],
            "partial_human_candidate": partial_details["candidate"],
            "partial_human_max_confidence": partial_details["max_confidence"],
            "partial_human_max_box_area_ratio": partial_details["max_box_area_ratio"],
            "yaw": pose_info["yaw"],
            "pitch": pose_info["pitch"],
            "gaze_direction": pose_info.get("gaze_direction", "center"),
            "gaze_horizontal": pose_info.get("gaze_horizontal", 0.0),
            "gaze_vertical": pose_info.get("gaze_vertical", 0.0),
            "looking_away": pose_info.get("looking_away", False),
            "assistance_monitor": assistance_signal.details,
            "identity_verified": identity_result.identity_verified,
            "identity_face_score": identity_result.face_score,
            "identity_voice_score": identity_result.voice_score,
            "identity_warning_count": identity_result.warning_count,
            "identity_should_terminate": identity_result.should_terminate,
        }
        fps = self._fps(session_id)
        metrics["fps_estimate"] = fps

        # Add identity face box overlay with color coding
        identity_face_box = identity_verifier.get_face_box(session_id)
        if identity_face_box:
            x, y, w, h = identity_face_box
            # Green for verified, Red for unauthorized
            box_color = (0, 255, 0) if identity_result.identity_verified else (0, 0, 255)
            label = "VERIFIED" if identity_result.identity_verified else "UNAUTHORIZED"
            identity_box = Box(
                label=label,
                confidence=identity_result.face_score,
                x1=x,
                y1=y,
                x2=x + w,
                y2=y + h,
                partial=False,
            )
            # Add identity box to the list for annotation
            all_boxes: list[Box] = [*persons, *phones, *partial_humans, identity_box]
        else:
            all_boxes = [*persons, *phones, *partial_humans]

        annotated_b64 = None
        if include_annotated_image and settings.overlay_enabled:
            annotated = annotate_frame(frame, all_boxes, alert_messages, metrics)
            encoded = encode_base64_image(annotated)
            annotated_b64 = f"data:image/jpeg;base64,{encoded}" if encoded else None

        return FrameAnalyzeResponse(
            session_id=session_id,
            timestamp=datetime.utcnow(),
            fps_estimate=fps,
            detections=[DetectionBox(**b.to_dict()) for b in all_boxes],
            alerts=alerts,
            metrics=metrics,
            annotated_image_base64=annotated_b64,
        )


    def analyze_multi_person_enhanced(
        self,
        session_id: str,
        persons: list[Box],
        pose_info: dict,
        frame_shape: tuple
    ) -> tuple[bool, dict]:
        """
        Enhanced multi-person detection using advanced spatial analysis.
        
        Returns:
            (should_alert, details_dict)
        """
        face_detections = pose_info.get('face_detections', [])
        
        result = multi_person_detector.analyze_persons(
            session_id=session_id,
            persons=persons,
            face_detections=face_detections,
            frame_shape=frame_shape
        )
        
        now = time.time()
        consistent_detection = bool(result.spatial_analysis.get("consistent_detection", False))
        last_alert = self._last_multi_person_alert_at.get(session_id, 0.0)
        cooldown_remaining = max(0.0, WARNING_COOLDOWN_SECONDS - (now - last_alert))
        allowed_by_cooldown = cooldown_remaining <= 0
        should_alert = bool(
            result.detected
            and len(result.unauthorized_persons) > 0
            and consistent_detection
            and allowed_by_cooldown
        )

        if should_alert:
            self._last_multi_person_alert_at[session_id] = now
            self._multi_person_warnings_count[session_id] = (
                self._multi_person_warnings_count.get(session_id, 0) + 1
            )
        
        details = {
            'person_count': result.person_count,
            'unauthorized_count': len(result.unauthorized_persons),
            'authorized_index': result.authorized_person_index,
            'unauthorized_persons': result.unauthorized_persons,
            'spatial_analysis': result.spatial_analysis,
            'confidence_scores': result.confidence_scores,
            'recommendation': result.recommendation,
            'detection_method': 'enhanced_spatial',
            'candidate': result.detected and len(result.unauthorized_persons) > 0,
            'consistent_detection': consistent_detection,
            'cooldown_remaining': round(cooldown_remaining, 2),
            'warnings_count': self._multi_person_warnings_count.get(session_id, 0),
        }
        
        if should_alert:
            logger.warning(
                "[Proctoring] Enhanced multi-person ALERT: session=%s, "
                "unauthorized=%d, authorized_idx=%s",
                session_id, len(result.unauthorized_persons), result.authorized_person_index
            )
        
        return should_alert, details
    
    def analyze_phone_enhanced(
        self,
        session_id: str,
        phone_detections: list[Box],
        pose_info: dict,
        frame_shape: tuple
    ) -> tuple[bool, dict]:
        """
        Enhanced phone detection with usage pattern analysis.
        
        Returns:
            (should_alert, details_dict)
        """
        # Get face position for context
        face_box = pose_info.get('face_box')  # (x, y, w, h)
        
        result = phone_detector.analyze_phone_detection(
            session_id=session_id,
            detections=phone_detections,
            face_position=face_box,
            pose_info=pose_info
        )
        
        # Alert on persistent detection with high confidence
        should_alert = (
            result.detected and 
            result.is_persistent and 
            result.alert_level in ['warning', 'critical']
        )
        
        details = {
            'device_type': result.device_type,
            'confidence': result.confidence,
            'position': result.position,
            'usage_pattern': result.usage_pattern,
            'time_visible_seconds': result.time_visible_seconds,
            'is_persistent': result.is_persistent,
            'alert_level': result.alert_level,
            'detection_method': 'enhanced_contextual'
        }
        
        if should_alert:
            logger.warning(
                "[Proctoring] Enhanced phone ALERT: session=%s, "
                "position=%s, usage=%s, level=%s",
                session_id, result.position, result.usage_pattern, result.alert_level
            )
        
        return should_alert, details
    
    def verify_voice_biometric(
        self,
        session_id: str,
        audio_data: bytes | None
    ) -> dict:
        """
        Verify voice against enrolled biometric.
        
        Returns:
            Verification result dict
        """
        if audio_data is None:
            return {'verified': False, 'error': 'No audio data'}
        
        # Use voice comparator
        from app.proctoring.enhanced_security import voice_comparator
        
        result = voice_comparator.compare_voice(
            session_id=session_id,
            audio_sample=audio_data
        )
        
        response = {
            'verified': result.is_match,
            'similarity_score': result.similarity_score,
            'confidence': result.confidence,
            'is_different_speaker': result.is_different_speaker,
            'warning_level': result.warning_level,
            'details': result.details
        }
        
        if result.warning_level in ['alert', 'critical']:
            logger.warning(
                "[Proctoring] Voice biometric ALERT: session=%s, "
                "similarity=%.3f, level=%s",
                session_id, result.similarity_score, result.warning_level
            )
        
        return response


proctoring_engine = ProctoringEngine()
