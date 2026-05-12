from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse

logger = logging.getLogger(__name__)

from app.proctoring.alert_log import alert_log_store
from app.proctoring.config import settings
from app.proctoring.engine import proctoring_engine
from app.proctoring.identity_verifier import identity_verifier
from app.proctoring.schemas import FrameAnalyzeRequest
from app.proctoring.config import settings as proctoring_settings
from pydantic import BaseModel


router = APIRouter(tags=["proctoring"])
_executor = ThreadPoolExecutor(max_workers=4)
_demo_file = Path(__file__).resolve().parents[1] / "proctoring" / "demo_client.html"


class ReentryVerifyRequest(BaseModel):
    session_id: str
    image: str
    expected_username: str = ""


class ReentryVerifyResponse(BaseModel):
    verified: bool
    replacement_detected: bool = False
    match_score: float = 0.0
    face_count: int = 0
    message: str = ""


@router.post("/proctoring/verify-reentry", response_model=ReentryVerifyResponse)
def verify_reentry(payload: ReentryVerifyRequest):
    """
    Verify candidate identity on re-entry after absence.
    Detects potential replacement by comparing face against registered embedding.
    """
    try:
        # Check if we have a registered user for this session
        registered_username = identity_verifier._registered_username.get(payload.session_id)
        registered_embedding = identity_verifier._registered_face_embedding.get(payload.session_id)

        # Decode the image
        frame = identity_verifier._decode_image(payload.image)
        if frame is None:
            return ReentryVerifyResponse(
                verified=False,
                message="Failed to decode image"
            )

        # Extract face from current frame
        current_embedding, face_box = identity_verifier._extract_face_embedding(frame)

        if current_embedding is None:
            return ReentryVerifyResponse(
                verified=False,
                face_count=0,
                message="No face detected in frame"
            )

        # If no registered embedding yet, register this as the baseline
        if registered_embedding is None:
            identity_verifier.register_user(
                session_id=payload.session_id,
                username=payload.expected_username or "candidate",
                face_embedding=current_embedding,
                voice_embedding=None
            )
            return ReentryVerifyResponse(
                verified=True,
                replacement_detected=False,
                match_score=1.0,
                face_count=1,
                message="Candidate registered and verified"
            )

        # Compare embeddings to detect replacement
        similarity = identity_verifier._compute_similarity(registered_embedding, current_embedding)

        # Determine if this is a replacement
        is_replacement = similarity < settings.replacement_detection_threshold
        is_verified = similarity >= settings.identity_face_match_threshold

        if is_replacement:
            # Log replacement attempt
            alert_log_store.append(
                session_id=payload.session_id,
                rule="replacement_detected",
                message=f"Different person detected on re-entry (score: {similarity:.2f})",
                details={
                    "match_score": similarity,
                    "threshold": settings.replacement_detection_threshold,
                    "expected_username": registered_username,
                },
            )
            return ReentryVerifyResponse(
                verified=False,
                replacement_detected=True,
                match_score=similarity,
                face_count=1,
                message="Different person detected - possible candidate replacement"
            )

        if is_verified:
            return ReentryVerifyResponse(
                verified=True,
                replacement_detected=False,
                match_score=similarity,
                face_count=1,
                message="Candidate identity verified"
            )
        else:
            # Low score but not quite replacement - ask for better view
            return ReentryVerifyResponse(
                verified=False,
                replacement_detected=False,
                match_score=similarity,
                face_count=1,
                message="Unable to verify - please ensure proper lighting and face the camera"
            )

    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Reentry verification failed: {exc}") from exc


@router.get("/proctoring/health")
def proctoring_health():
    store_health = alert_log_store.health()
    return {
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat(),
        "models": {
            "yolo_available": proctoring_engine.yolo.available,
            "face_pose_available": proctoring_engine.face_pose.available,
        },
        "alerts": store_health,
    }


@router.post("/proctoring/analyze-frame")
def analyze_frame(payload: FrameAnalyzeRequest):
    try:
        return proctoring_engine.analyze_base64(
            session_id=payload.session_id,
            image_base64=payload.image_base64,
            include_annotated_image=payload.include_annotated_image,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Proctoring failure: {exc}") from exc


@router.get("/proctoring/alerts/{session_id}")
def list_alerts(session_id: str, limit: int = Query(default=200, ge=1, le=2000)):
    events = alert_log_store.list_session(session_id, limit=limit)
    return {"session_id": session_id, "count": len(events), "events": events}


@router.get("/proctoring/demo")
def proctoring_demo_page():
    if not _demo_file.exists():
        raise HTTPException(status_code=404, detail="Demo page not found")
    return FileResponse(_demo_file)


class CheatingAlertRequest(BaseModel):
    message: str
    rule: str = "proctoring"
    details: dict = {}
    session_id: str = ""


class CheatingAlertResponse(BaseModel):
    status: str  # "warning" or "terminated"
    warning_count: int
    total_warnings: int
    max_warnings: int
    message: str
    termination_reason: str = ""
    rule: str


# Rules that count toward the 3-strike termination system
STRIKE_RULES = {
    "mobile_phone", "multiple_people", "voice_identity", "voice_multi_speaker"
}


@router.post("/cheating_alert", response_model=CheatingAlertResponse)
def cheating_alert(payload: CheatingAlertRequest):
    """
    Process a proctoring alert/warning from the frontend.
    Implements 3-strike warning escalation system.
    """
    try:
        # DEBUG: Log incoming request
        logger.info(
            "[CheatingAlert] Received: session_id=%s, rule=%s, message=%s, has_details=%s",
            payload.session_id, payload.rule, payload.message, bool(payload.details)
        )

        session_id = payload.session_id.strip() if payload.session_id else ""
        if not session_id:
            logger.error("[CheatingAlert] Missing session_id in request")
            raise HTTPException(status_code=400, detail="session_id is required")

        rule = payload.rule or "proctoring"
        message = payload.message or "Proctoring warning detected."

        # Get current warning count for this rule
        current_count = alert_log_store.get_warning_count(session_id, rule)

        # Check if this rule counts toward strikes
        counts_toward_strikes = rule in STRIKE_RULES

        # Increment warning with debounce cooldown
        new_count, was_incremented = alert_log_store.increment_warning(
            session_id, rule, cooldown_seconds=5.0
        )

        # Log the alert
        from app.proctoring.schemas import ViolationEvent
        event = ViolationEvent(
            session_id=session_id,
            rule=rule,
            message=message,
            details={
                **payload.details,
                "warning_count": new_count,
                "was_incremented": was_incremented,
                "counts_toward_strikes": counts_toward_strikes,
            },
        )
        alert_log_store.add(event)

        # Calculate total warnings across all strike-rules
        all_warnings = alert_log_store.get_all_warning_counts(session_id)
        total_strikes = sum(
            count for r, count in all_warnings.items()
            if r in STRIKE_RULES
        )

        max_warnings = proctoring_settings.max_violation_warnings

        # Determine status
        if total_strikes >= max_warnings:
            termination_reason = f"Maximum warnings exceeded ({total_strikes}/{max_warnings}). Last violation: {rule}"
            return CheatingAlertResponse(
                status="terminated",
                warning_count=new_count,
                total_warnings=total_strikes,
                max_warnings=max_warnings,
                message=message,
                termination_reason=termination_reason,
                rule=rule,
            )

        return CheatingAlertResponse(
            status="warning",
            warning_count=new_count,
            total_warnings=total_strikes,
            max_warnings=max_warnings,
            message=f"Warning {total_strikes}/{max_warnings}: {message}",
            termination_reason="",
            rule=rule,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("[CheatingAlert] Error processing alert: %s", str(e))
        raise HTTPException(status_code=500, detail=f"Internal error processing cheating alert: {str(e)}")


@router.get("/cheating_alert/{session_id}/warnings")
def get_warning_summary(session_id: str):
    """Get current warning counts for a session."""
    all_warnings = alert_log_store.get_all_warning_counts(session_id)
    total_strikes = sum(
        count for r, count in all_warnings.items()
        if r in STRIKE_RULES
    )
    max_warnings = proctoring_settings.max_violation_warnings

    return {
        "session_id": session_id,
        "warning_counts_by_rule": all_warnings,
        "total_strikes": total_strikes,
        "max_warnings": max_warnings,
        "termination_imminent": total_strikes >= max_warnings - 1,
        "can_continue": total_strikes < max_warnings,
    }


@router.post("/cheating_alert/{session_id}/reset")
def reset_warnings(session_id: str, rule: str | None = None):
    """Reset warnings for a session (useful for testing or valid user re-verification)."""
    alert_log_store.reset_warnings(session_id, rule)
    return {
        "session_id": session_id,
        "rule": rule or "all",
        "status": "reset_complete",
    }


# WebSocket connection manager for broadcasting warnings
class WarningConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, list[WebSocket]] = {}
        self.session_warning_counts: dict[str, dict[str, int]] = {}
        
    async def connect(self, session_id: str, websocket: WebSocket):
        if session_id not in self.active_connections:
            self.active_connections[session_id] = []
            self.session_warning_counts[session_id] = {}
        if websocket in self.active_connections[session_id]:
            return
        self.active_connections[session_id].append(websocket)
        logger.info("[WarningManager] WebSocket connected for session %s (total: %d)", 
                   session_id, len(self.active_connections[session_id]))
    
    def disconnect(self, session_id: str, websocket: WebSocket):
        if session_id in self.active_connections:
            if websocket in self.active_connections[session_id]:
                self.active_connections[session_id].remove(websocket)
            if not self.active_connections[session_id]:
                del self.active_connections[session_id]
                if session_id in self.session_warning_counts:
                    del self.session_warning_counts[session_id]
        logger.info("[WarningManager] WebSocket disconnected from session %s", session_id)
    
    async def broadcast_warning(self, session_id: str, warning_data: dict):
        """Broadcast a warning to all connected clients for a session"""
        if session_id not in self.active_connections:
            return

        rule = warning_data.get("rule", "unknown")
        if rule not in STRIKE_RULES:
            logger.info("[WarningManager] Suppressed non-user-facing rule %s", rule)
            return
            
        # Track warning count
        if session_id not in self.session_warning_counts:
            self.session_warning_counts[session_id] = {}
        self.session_warning_counts[session_id][rule] = \
            self.session_warning_counts[session_id].get(rule, 0) + 1
        
        # Add warning count to payload
        warning_data["warning_count"] = self.session_warning_counts[session_id][rule]
        warning_data["total_strikes"] = sum(self.session_warning_counts[session_id].values())
        warning_data["timestamp"] = datetime.utcnow().isoformat()
        
        message = {
            "type": "PROCTORING_WARNING",
            "severity": "warning" if warning_data.get("warning_count", 0) < 3 else "critical",
            "data": warning_data
        }
        
        disconnected = []
        for connection in self.active_connections[session_id]:
            try:
                await connection.send_json(message)
                logger.info("[WarningManager] Warning broadcast to session %s: %s", 
                           session_id, warning_data.get("message", ""))
            except Exception as e:
                logger.error("[WarningManager] Failed to send warning: %s", e)
                disconnected.append(connection)
        
        # Clean up disconnected clients
        for conn in disconnected:
            if conn in self.active_connections[session_id]:
                self.active_connections[session_id].remove(conn)
    
    def get_session_warnings(self, session_id: str) -> dict:
        return self.session_warning_counts.get(session_id, {})


# Global connection manager
warning_manager = WarningConnectionManager()


@router.websocket("/proctoring/ws")
async def proctoring_ws(websocket: WebSocket):
    await websocket.accept()
    loop = asyncio.get_running_loop()
    session_id = None
    
    try:
        while True:
            message = await websocket.receive_json()
            session_id = message.get("session_id", "").strip()
            image_b64 = message.get("image_base64")
            include_annotated = bool(message.get("include_annotated_image", True))
            
            if not session_id or not image_b64:
                await websocket.send_json({"error": "session_id and image_base64 are required"})
                continue
            
            # Register connection for warning broadcasts
            await warning_manager.connect(session_id, websocket)

            try:
                result = await loop.run_in_executor(
                    _executor,
                    lambda: proctoring_engine.analyze_base64(session_id, image_b64, include_annotated),
                )
                
                # Broadcast any alerts as warnings
                for alert in result.alerts:
                    await warning_manager.broadcast_warning(session_id, {
                        "rule": alert.rule,
                        "message": alert.message,
                        "details": alert.details,
                        "session_id": session_id,
                    })
                
                await websocket.send_json(result.model_dump(mode="json"))
                
            except Exception as exc:
                logger.error("[ProctoringWS] Analysis error: %s", exc)
                await websocket.send_json({"error": f"analysis_failed: {exc}"})
                
    except WebSocketDisconnect:
        if session_id:
            warning_manager.disconnect(session_id, websocket)
        logger.info("[ProctoringWS] Client disconnected from session %s", session_id)
    except Exception as e:
        logger.error("[ProctoringWS] WebSocket error: %s", e)
        if session_id:
            warning_manager.disconnect(session_id, websocket)
