from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import datetime
import logging
import math
import time
from typing import Any

try:
    import cv2
except Exception:  # pragma: no cover
    cv2 = None

try:
    import numpy as np
except Exception:  # pragma: no cover
    np = None

from app.proctoring.config import settings


logger = logging.getLogger(__name__)

try:
    from ultralytics import YOLO
except Exception:  # pragma: no cover
    YOLO = None

try:
    import mediapipe as mp
except Exception:  # pragma: no cover
    mp = None


PERSON_CLASS = 0
TV_CLASS = 62    # TV / Monitor
LAPTOP_CLASS = 63
CELL_PHONE_CLASS = 67
# Note: Tablets are often detected as laptops or cell phones in COCO-80


@dataclass(slots=True)
class Box:
    label: str
    confidence: float
    x1: int
    y1: int
    x2: int
    y2: int
    partial: bool = False

    @property
    def area(self) -> int:
        return max(1, self.x2 - self.x1) * max(1, self.y2 - self.y1)

    def to_dict(self) -> dict:
        return {
            "label": self.label,
            "confidence": float(self.confidence),
            "x1": int(self.x1),
            "y1": int(self.y1),
            "x2": int(self.x2),
            "y2": int(self.y2),
            "partial": bool(self.partial),
            "area": int(self.area),
        }


def decode_base64_image(data: str) -> np.ndarray:
    if cv2 is None or np is None:
        raise RuntimeError("OpenCV/Numpy is not installed. Install backend proctoring dependencies first.")
    payload = data.split(",", 1)[1] if "," in data else data
    raw = base64.b64decode(payload)
    arr = np.frombuffer(raw, dtype=np.uint8)
    frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if frame is None:
        raise ValueError("Unable to decode image bytes.")
    return frame


def encode_base64_image(frame: np.ndarray) -> str:
    if cv2 is None:
        return ""
    ok, encoded = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
    if not ok:
        return ""
    return base64.b64encode(encoded.tobytes()).decode("ascii")


class YoloObjectDetector:
    def __init__(self) -> None:
        self.available = False
        self._model = None
        if YOLO is None:
            return
        try:
            self._model = YOLO(settings.yolo_model_name)
            self.available = True
        except Exception:
            self._model = None
            self.available = False

    @staticmethod
    def _compute_iou(box1: Box, box2: Box) -> float:
        """Compute Intersection over Union between two boxes."""
        xi1 = max(box1.x1, box2.x1)
        yi1 = max(box1.y1, box2.y1)
        xi2 = min(box1.x2, box2.x2)
        yi2 = min(box1.y2, box2.y2)
        inter_area = max(0, xi2 - xi1) * max(0, yi2 - yi1)
        box1_area = (box1.x2 - box1.x1) * (box1.y2 - box1.y1)
        box2_area = (box2.x2 - box2.x1) * (box2.y2 - box2.y1)
        union_area = box1_area + box2_area - inter_area
        return inter_area / max(1, union_area)

    @staticmethod
    def _deduplicate_boxes(boxes: list[Box], iou_threshold: float = 0.5) -> list[Box]:
        """Remove overlapping boxes keeping the one with higher confidence."""
        if not boxes:
            return []
        # Sort by confidence descending
        sorted_boxes = sorted(boxes, key=lambda b: b.confidence, reverse=True)
        keep: list[Box] = []
        for box in sorted_boxes:
            is_duplicate = False
            for kept in keep:
                iou = YoloObjectDetector._compute_iou(box, kept)
                if iou > iou_threshold:
                    is_duplicate = True
                    logger.debug(
                        "[Proctoring] Deduplication: removed %s (conf=%.3f) - IOU=%.3f with kept %s (conf=%.3f)",
                        box.label, box.confidence, iou, kept.label, kept.confidence
                    )
                    break
            if not is_duplicate:
                keep.append(box)
        return keep

    def detect(self, frame: np.ndarray) -> tuple[list[Box], list[Box], list[Box]]:
        if np is None:
            return [], [], []
        h, w = frame.shape[:2]
        persons: list[Box] = []
        phones: list[Box] = []
        partial_humans: list[Box] = []
        if not self.available or self._model is None:
            return persons, phones, partial_humans

        conf = min(settings.person_partial_conf_threshold, settings.phone_conf_threshold)
        result = self._model.predict(
            frame,
            conf=conf,
            verbose=False,
            iou=0.45,
            max_det=25,
            imgsz=settings.yolo_image_size,
        )[0]
        boxes = result.boxes
        if boxes is None:
            return persons, phones, partial_humans

        # RAW DETECTION LOGGING - Log ALL YOLO outputs before filtering
        raw_detections = []
        for idx in range(len(boxes)):
            cls = int(boxes.cls[idx].item())
            score = float(boxes.conf[idx].item())
            x1, y1, x2, y2 = [int(v) for v in boxes.xyxy[idx].tolist()]
            raw_detections.append({
                "idx": idx, "cls": cls, "score": score,
                "box": [x1, y1, x2, y2], "area": (x2-x1)*(y2-y1)
            })

        logger.debug("[Proctoring] RAW YOLO DETECTIONS: count=%d, detections=%s", len(raw_detections), raw_detections)

        for idx in range(len(boxes)):
            cls = int(boxes.cls[idx].item())
            score = float(boxes.conf[idx].item())
            x1, y1, x2, y2 = [int(v) for v in boxes.xyxy[idx].tolist()]
            bw = max(1, x2 - x1)
            bh = max(1, y2 - y1)
            area_ratio = (bw * bh) / max(1, w * h)
            edge_x = max(6, int(w * settings.edge_ignore_margin))
            edge_y = max(6, int(h * settings.edge_ignore_margin))
            touches_edge = x1 <= edge_x or y1 <= edge_y or x2 >= (w - edge_x) or y2 >= (h - edge_y)

            if cls == PERSON_CLASS and score >= settings.person_partial_conf_threshold:
                is_partial = area_ratio <= settings.partial_ratio_threshold or touches_edge
                box = Box("person", score, x1, y1, x2, y2, partial=is_partial)
                # Count every YOLO "person" detection that passes the configured
                # person threshold. Multi-person detection depends on the raw
                # count, including partial side/edge people.
                persons.append(box)
                if is_partial:
                    min_area = settings.min_edge_partial_person_box_area if touches_edge else settings.min_partial_person_box_area
                    if area_ratio >= min_area:
                        partial_humans.append(box)
                        logger.debug(
                            "[Proctoring] partial person kept confidence=%.3f area=%.4f edge=%s min_area=%.4f box=%s",
                            score,
                            area_ratio,
                            touches_edge,
                            min_area,
                            box.to_dict(),
                        )
                    else:
                        logger.debug(
                            "[Proctoring] partial person ignored confidence=%.3f area=%.4f edge=%s min_area=%.4f box=%s",
                            score,
                            area_ratio,
                            touches_edge,
                            min_area,
                            box.to_dict(),
                        )
            elif cls == CELL_PHONE_CLASS and score >= settings.phone_conf_threshold:
                is_partial_phone = area_ratio <= 0.02 or touches_edge
                phones.append(Box("cell_phone", score, x1, y1, x2, y2, partial=is_partial_phone))
            elif cls in {LAPTOP_CLASS, TV_CLASS} and score >= settings.phone_conf_threshold:
                # Add laptops/monitors as 'unauthorized_device'
                label = "laptop" if cls == LAPTOP_CLASS else "monitor"
                phones.append(Box(label, score, x1, y1, x2, y2, partial=touches_edge))

        # DEDUPLICATION: Remove overlapping laptop/monitor detections
        laptop_monitor_boxes = [b for b in phones if b.label in ("laptop", "monitor")]
        other_devices = [b for b in phones if b.label not in ("laptop", "monitor")]

        if len(laptop_monitor_boxes) > 1:
            logger.debug(
                "[Proctoring] Pre-deduplication: %d laptop/monitor boxes", len(laptop_monitor_boxes)
            )
            for i, b in enumerate(laptop_monitor_boxes):
                logger.debug(
                    "[Proctoring]   Box %d: %s conf=%.3f area=%d center=(%.1f, %.1f)",
                    i, b.label, b.confidence, b.area, (b.x1+b.x2)/2, (b.y1+b.y2)/2
                )

        deduplicated_laptops = self._deduplicate_boxes(laptop_monitor_boxes, iou_threshold=0.5)

        if len(laptop_monitor_boxes) != len(deduplicated_laptops):
            logger.debug(
                "[Proctoring] Deduplication removed %d overlapping laptop/monitor boxes (%d -> %d)",
                len(laptop_monitor_boxes) - len(deduplicated_laptops),
                len(laptop_monitor_boxes), len(deduplicated_laptops)
            )

        phones = other_devices + deduplicated_laptops

        # POST-PROCESSING LOGGING
        laptop_count = len([b for b in phones if b.label == "laptop"])
        monitor_count = len([b for b in phones if b.label == "monitor"])
        phone_count = len([b for b in phones if b.label == "cell_phone"])
        logger.debug(
            "[Proctoring] DETECTOR OUTPUT: persons=%d, laptops=%d, monitors=%d, phones=%d, partial_humans=%d",
            len(persons), laptop_count, monitor_count, phone_count, len(partial_humans)
        )

        return persons, phones, partial_humans


class FaceGazeHeadPoseDetector:
    def __init__(self) -> None:
        self.available = False
        self._face_mesh = None
        self._pose = None
        self._look_away_since: dict[str, float] = {}
        if mp is None:
            return
        try:
            self._face_mesh = mp.solutions.face_mesh.FaceMesh(
                static_image_mode=False,
                max_num_faces=2,
                refine_landmarks=True,
                min_detection_confidence=0.35,
                min_tracking_confidence=0.3,
            )
            self._pose = mp.solutions.pose.Pose(
                static_image_mode=False,
                model_complexity=1,
                enable_segmentation=False,
                min_detection_confidence=0.2,
                min_tracking_confidence=0.2,
            )
            self.available = True
        except Exception:
            self.available = False

    @staticmethod
    def _landmark_px(lm: Any, w: int, h: int) -> tuple[float, float]:
        return lm.x * w, lm.y * h

    def _estimate_head_pose(self, landmarks: Any, w: int, h: int) -> tuple[float, float]:
        # Nose tip, chin, eye corners, mouth corners (MediaPipe indices).
        idxs = [1, 152, 33, 263, 61, 291]
        image_points = np.array([self._landmark_px(landmarks[i], w, h) for i in idxs], dtype=np.float64)
        model_points = np.array(
            [
                (0.0, 0.0, 0.0),
                (0.0, -63.6, -12.5),
                (-43.3, 32.7, -26.0),
                (43.3, 32.7, -26.0),
                (-28.9, -28.9, -24.1),
                (28.9, -28.9, -24.1),
            ],
            dtype=np.float64,
        )
        focal = w
        camera = np.array([[focal, 0, w / 2], [0, focal, h / 2], [0, 0, 1]], dtype=np.float64)
        dist = np.zeros((4, 1))
        ok, rvec, _ = cv2.solvePnP(model_points, image_points, camera, dist, flags=cv2.SOLVEPNP_ITERATIVE)
        if not ok:
            return 0.0, 0.0
        rot, _ = cv2.Rodrigues(rvec)
        sy = math.sqrt(rot[0, 0] * rot[0, 0] + rot[1, 0] * rot[1, 0])
        yaw = math.degrees(math.atan2(rot[2, 0], sy))
        pitch = math.degrees(math.atan2(-rot[2, 1], rot[2, 2]))
        return yaw, pitch

    @staticmethod
    def _eye_offset(face_landmarks: Any, outer_idx: int, inner_idx: int, top_idx: int, bottom_idx: int, iris_idx: int) -> tuple[float, float]:
        outer = face_landmarks[outer_idx]
        inner = face_landmarks[inner_idx]
        top = face_landmarks[top_idx]
        bottom = face_landmarks[bottom_idx]
        iris = face_landmarks[iris_idx]

        center_x = (outer.x + inner.x) * 0.5
        center_y = (top.y + bottom.y) * 0.5
        width = max(abs(inner.x - outer.x), 1e-6)
        height = max(abs(bottom.y - top.y), 1e-6)
        return (iris.x - center_x) / width, (iris.y - center_y) / height

    def _estimate_gaze(self, face_landmarks: Any) -> dict[str, float | str | bool]:
        # MediaPipe iris landmarks give a stronger side-eye signal than head pose alone.
        try:
            left_x, left_y = self._eye_offset(face_landmarks, 33, 133, 159, 145, 468)
            right_x, right_y = self._eye_offset(face_landmarks, 263, 362, 386, 374, 473)
        except Exception:
            return {"looking_away": False, "direction": "center", "horizontal": 0.0, "vertical": 0.0}

        horizontal = (left_x + right_x) * 0.5
        vertical = (left_y + right_y) * 0.5
        looking_side = abs(horizontal) >= settings.gaze_horizontal_threshold
        looking_vertical = abs(vertical) >= settings.gaze_vertical_threshold

        direction = "center"
        if looking_side and abs(horizontal) >= abs(vertical) * 0.7:
            direction = "right" if horizontal > 0 else "left"
        elif looking_vertical:
            direction = "down" if vertical > 0 else "up"
        elif looking_side:
            direction = "right" if horizontal > 0 else "left"

        return {
            "looking_away": bool(looking_side or looking_vertical),
            "direction": direction,
            "horizontal": float(horizontal),
            "vertical": float(vertical),
        }

    def analyze(self, frame: np.ndarray, session_id: str) -> dict:
        result = {
            "faces": 0,
            "face_detections": [],
            "look_away_alert": False,
            "head_pose_alert": False,
            "partial_human_pose_alert": False,
            "yaw": 0.0,
            "pitch": 0.0,
            "gaze_direction": "center",
            "gaze_horizontal": 0.0,
            "gaze_vertical": 0.0,
            "looking_away": False,
            "pose_points": [],
        }
        if not self.available:
            return result

        if cv2 is None:
            return result
        h, w = frame.shape[:2]
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        face_res = self._face_mesh.process(rgb)
        pose_res = self._pose.process(rgb)

        if face_res.multi_face_landmarks:
            result["faces"] = len(face_res.multi_face_landmarks)
            face_detections = []
            for face_landmarks in face_res.multi_face_landmarks:
                xs = [lm.x * w for lm in face_landmarks.landmark]
                ys = [lm.y * h for lm in face_landmarks.landmark]
                if xs and ys:
                    x1 = max(0, int(min(xs)))
                    y1 = max(0, int(min(ys)))
                    x2 = min(w, int(max(xs)))
                    y2 = min(h, int(max(ys)))
                    face_detections.append({
                        "box": (x1, y1, x2, y2),
                        "confidence": 1.0,
                    })
            result["face_detections"] = face_detections

            # Use first face as primary.
            landmarks = face_res.multi_face_landmarks[0].landmark
            yaw, pitch = self._estimate_head_pose(landmarks, w, h)
            result["yaw"] = yaw
            result["pitch"] = pitch
            if abs(yaw) >= settings.head_pose_yaw_threshold or abs(pitch) >= settings.head_pose_pitch_threshold:
                result["head_pose_alert"] = True

            gaze = self._estimate_gaze(landmarks)
            looking_away = bool(gaze["looking_away"])
            result["looking_away"] = looking_away
            result["gaze_direction"] = gaze["direction"]
            result["gaze_horizontal"] = gaze["horizontal"]
            result["gaze_vertical"] = gaze["vertical"]
            now = time.time()
            if looking_away:
                since = self._look_away_since.setdefault(session_id, now)
                if now - since >= settings.look_away_seconds:
                    result["look_away_alert"] = True
            else:
                self._look_away_since.pop(session_id, None)

        if pose_res.pose_landmarks:
            # Shoulders + elbows + wrists visible with relaxed threshold.
            idxs = [11, 12, 13, 14, 15, 16]
            low_vis = 0
            for idx in idxs:
                lm = pose_res.pose_landmarks.landmark[idx]
                result["pose_points"].append((int(lm.x * w), int(lm.y * h), float(lm.visibility)))
                if lm.visibility < 0.18:
                    low_vis += 1
            # Strict mode: partial shoulder/arm hints raise flags quickly.
            if settings.strict_sensitivity and low_vis >= 2:
                result["partial_human_pose_alert"] = True

        return result


def annotate_frame(frame: np.ndarray, boxes: list[Box], alert_messages: list[str], metrics: dict) -> np.ndarray:
    if cv2 is None:
        return frame
    out = frame.copy()
    for b in boxes:
        # Special handling for identity verification boxes
        if b.label == "VERIFIED":
            color = (0, 255, 0)  # Green for verified identity
            thickness = 3  # Thicker border for identity
        elif b.label == "UNAUTHORIZED":
            color = (0, 0, 255)  # Red for unauthorized person
            thickness = 3  # Thicker border for identity
        else:
            # Standard colors for other detections
            color = (0, 0, 255) if b.partial else (0, 255, 0)
            thickness = 2

        cv2.rectangle(out, (b.x1, b.y1), (b.x2, b.y2), color, thickness)
        caption = f"{b.label} {b.confidence:.2f}"
        if b.partial:
            caption += " partial"

        # Use white background for identity labels for better visibility
        if b.label in ("VERIFIED", "UNAUTHORIZED"):
            # Draw filled rectangle behind text
            (text_w, text_h), _ = cv2.getTextSize(caption, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 2)
            cv2.rectangle(out, (b.x1, max(15, b.y1 - text_h - 4)), (b.x1 + text_w, b.y1), color, -1)
            cv2.putText(out, caption, (b.x1, max(15, b.y1 - 4)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2, cv2.LINE_AA)
        else:
            cv2.putText(out, caption, (b.x1, max(15, b.y1 - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1, cv2.LINE_AA)

    y = 24
    for msg in alert_messages[-6:]:
        cv2.putText(out, msg, (8, y), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 0, 255), 2, cv2.LINE_AA)
        y += 24

    fps = metrics.get("fps_estimate", 0.0)
    cv2.putText(out, f"FPS: {fps:.1f}", (8, out.shape[0] - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 0), 2, cv2.LINE_AA)
    return out
