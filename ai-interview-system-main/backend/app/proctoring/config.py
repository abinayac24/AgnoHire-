from __future__ import annotations

from dataclasses import dataclass
import os


@dataclass(slots=True)
class ProctoringSettings:
    strict_sensitivity: bool = os.getenv("PROCTOR_STRICT_SENSITIVITY", "true").lower() == "true"
    person_conf_threshold: float = float(os.getenv("PERSON_DETECTION_CONFIDENCE_THRESHOLD", os.getenv("PROCTOR_PERSON_CONF_THRESHOLD", "0.30")))
    person_partial_conf_threshold: float = float(os.getenv("PROCTOR_PERSON_PARTIAL_CONF_THRESHOLD", os.getenv("PERSON_DETECTION_CONFIDENCE_THRESHOLD", "0.30")))
    phone_conf_threshold: float = float(os.getenv("PROCTOR_PHONE_CONF_THRESHOLD", "0.04"))
    phone_alert_seconds: float = float(os.getenv("PROCTOR_PHONE_ALERT_SECONDS", "0.0"))
    partial_ratio_threshold: float = float(os.getenv("PROCTOR_PARTIAL_RATIO_THRESHOLD", "0.06"))
    partial_person_persistence_seconds: float = float(os.getenv("PARTIAL_PERSON_PERSISTENCE_SECONDS", os.getenv("PROCTOR_PARTIAL_PERSON_PERSISTENCE_SECONDS", "2.5")))
    partial_person_alert_cooldown_seconds: float = float(os.getenv("PROCTOR_PARTIAL_PERSON_ALERT_COOLDOWN_SECONDS", "8.0"))
    min_partial_person_box_area: float = float(os.getenv("MIN_PARTIAL_PERSON_BOX_AREA", os.getenv("PROCTOR_MIN_PARTIAL_PERSON_BOX_AREA", "0.035")))
    min_edge_partial_person_box_area: float = float(os.getenv("PROCTOR_MIN_EDGE_PARTIAL_PERSON_BOX_AREA", "0.08"))
    edge_ignore_margin: float = float(os.getenv("EDGE_IGNORE_MARGIN", os.getenv("PROCTOR_EDGE_IGNORE_MARGIN", "0.08")))
    partial_person_face_correlation: bool = os.getenv("PROCTOR_PARTIAL_PERSON_FACE_CORRELATION", "true").lower() == "true"
    look_away_seconds: float = float(os.getenv("PROCTOR_LOOK_AWAY_SECONDS", "1.0"))
    gaze_horizontal_threshold: float = float(os.getenv("PROCTOR_GAZE_HORIZONTAL_THRESHOLD", "0.26"))
    gaze_vertical_threshold: float = float(os.getenv("PROCTOR_GAZE_VERTICAL_THRESHOLD", "0.34"))
    head_pose_yaw_threshold: float = float(os.getenv("PROCTOR_HEAD_YAW_THRESHOLD", "22.0"))
    head_pose_pitch_threshold: float = float(os.getenv("PROCTOR_HEAD_PITCH_THRESHOLD", "18.0"))
    overlay_enabled: bool = os.getenv("PROCTOR_OVERLAY_ENABLED", "true").lower() == "true"
    yolo_model_name: str = os.getenv("PROCTOR_YOLO_MODEL", "yolov8n.pt")
    yolo_image_size: int = int(os.getenv("PROCTOR_YOLO_IMAGE_SIZE", "960"))

    # Identity verification settings
    # REDUCED: 0.65 -> 0.55 for more lenient matching (Issue #1 fix)
    identity_face_match_threshold: float = float(os.getenv("IDENTITY_FACE_MATCH_THRESHOLD", "0.55"))
    identity_voice_match_threshold: float = float(os.getenv("IDENTITY_VOICE_MATCH_THRESHOLD", "0.86"))
    # INCREASED: 3.0 -> 4.0 seconds for temporal tolerance (Issue #1 fix)
    identity_mismatch_persistence_seconds: float = float(os.getenv("IDENTITY_MISMATCH_PERSISTENCE_SECONDS", "4.0"))
    max_identity_warnings: int = int(os.getenv("MAX_IDENTITY_WARNINGS", "3"))
    identity_check_interval_seconds: float = float(os.getenv("IDENTITY_CHECK_INTERVAL_SECONDS", "5.0"))
    # ADDED: Consecutive mismatch frames required before warning (Issue #1 fix)
    identity_mismatch_consecutive_frames: int = int(os.getenv("IDENTITY_MISMATCH_CONSECUTIVE_FRAMES", "3"))

    # Camera presence enforcement settings
    max_no_face_seconds: float = float(os.getenv("MAX_NO_FACE_SECONDS", "5.0"))
    max_absence_warnings: int = int(os.getenv("MAX_ABSENCE_WARNINGS", "2"))
    reentry_verification_required: bool = os.getenv("REENTRY_VERIFICATION_REQUIRED", "true").lower() == "true"
    face_presence_check_interval_ms: int = int(os.getenv("FACE_PRESENCE_CHECK_INTERVAL_MS", "500"))
    no_face_persistence_ms: int = int(os.getenv("NO_FACE_PERSISTENCE_MS", "1500"))
    replacement_detection_threshold: float = float(os.getenv("REPLACEMENT_DETECTION_THRESHOLD", "0.55"))

    # PROCTORING MASTER SWITCH: Set to True to disable all security checks (testing only)
    # Set to False to enable full proctoring (warnings, termination, etc.)
    proctoring_disabled: bool = os.getenv("PROCTORING_DISABLED", "false").lower() == "true"

    # General violation warning settings (3-strike system)
    max_violation_warnings: int = int(os.getenv("MAX_VIOLATION_WARNINGS", "3"))
    violation_warning_cooldown_seconds: float = float(os.getenv("VIOLATION_WARNING_COOLDOWN_SECONDS", "5.0"))


settings = ProctoringSettings()
