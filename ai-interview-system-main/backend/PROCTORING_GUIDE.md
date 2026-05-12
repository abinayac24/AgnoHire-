# Real-Time AI Proctoring Guide

This backend now includes a strict-sensitivity proctoring service using FastAPI + OpenCV + YOLO + MediaPipe.

## Endpoints

- `GET /api/proctoring/health`
- `POST /api/proctoring/analyze-frame`
- `GET /api/proctoring/alerts/{session_id}`
- `WS /api/proctoring/ws`

## Core Behaviors Implemented

- Multi-person detection (`Multiple person detected`)
- Partial human detection (edge/partial person + low-visibility shoulder/arm pose cues)
- Immediate mobile phone detection, so even a short one-second appearance can warn (`Mobile phone detected`)
- Eye-gaze away for >1s, including left/right side-eye movement (`User looking left/right away from screen`)
- Head-pose deviation (`Suspicious head movement`)
- Overlay annotations + strict alert generation
- JSONL alert logging: `backend/logs/proctoring_violations.jsonl`

## Quick Test (HTTP)

`POST /api/proctoring/analyze-frame` body:

```json
{
  "session_id": "candidate-001",
  "image_base64": "data:image/jpeg;base64,...",
  "include_annotated_image": true
}
```

Response includes:

- `detections` (boxes)
- `alerts` (timestamped violations)
- `metrics` (faces, person_count, phone_count, yaw/pitch, fps_estimate)
- `annotated_image_base64` (optional)

## WebSocket Streaming

Connect to: `ws://127.0.0.1:8000/api/proctoring/ws`

Send per frame:

```json
{
  "session_id": "candidate-001",
  "image_base64": "data:image/jpeg;base64,...",
  "include_annotated_image": true
}
```

Receive per frame:

- Alerts + detections + metrics + optional annotated frame

## Sensitivity Tuning (Env Vars)

- `PROCTOR_STRICT_SENSITIVITY=true`
- `PROCTOR_PERSON_CONF_THRESHOLD=0.20`
- `PROCTOR_PERSON_PARTIAL_CONF_THRESHOLD=0.10`
- `PROCTOR_PHONE_CONF_THRESHOLD=0.04`
- `PROCTOR_PHONE_ALERT_SECONDS=0.0`
- `PROCTOR_PARTIAL_RATIO_THRESHOLD=0.06`
- `PROCTOR_LOOK_AWAY_SECONDS=1.0`
- `PROCTOR_GAZE_HORIZONTAL_THRESHOLD=0.26`
- `PROCTOR_GAZE_VERTICAL_THRESHOLD=0.34`
- `PROCTOR_HEAD_YAW_THRESHOLD=22.0`
- `PROCTOR_HEAD_PITCH_THRESHOLD=18.0`
- `PROCTOR_YOLO_IMAGE_SIZE=960`

## Notes

- This strict mode is intentionally aggressive and may increase false positives.
- For better partial-phone/hair/shoulder sensitivity, plug in a custom fine-tuned YOLO model by setting `PROCTOR_YOLO_MODEL`.
