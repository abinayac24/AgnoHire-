from __future__ import annotations

from dataclasses import dataclass
import time


@dataclass(slots=True)
class AssistanceSignal:
    should_alert: bool
    reason: str
    details: dict


class AssistanceDetector:
    """
    Lightweight sidecar detector for suspicious hint/assistance behavior.

    It does not replace existing gaze/head-pose proctoring. It aggregates repeated
    off-screen gaze, horizontal scanning, and attention instability into a separate
    admin-review alert.
    """

    def __init__(
        self,
        sample_window: int = 36,
        min_alert_gap_seconds: float = 12.0,
        offscreen_threshold: float = 0.24,
        scan_threshold: float = 0.05,
    ) -> None:
        self.sample_window = sample_window
        self.min_alert_gap_seconds = min_alert_gap_seconds
        self.offscreen_threshold = offscreen_threshold
        self.scan_threshold = scan_threshold
        self._history: dict[str, list[dict]] = {}
        self._last_alert_at: dict[str, float] = {}

    def analyze(self, session_id: str, pose_info: dict, now: float | None = None) -> AssistanceSignal:
        current_time = now if now is not None else time.time()
        gaze_horizontal = float(pose_info.get("gaze_horizontal", 0.0) or 0.0)
        gaze_vertical = float(pose_info.get("gaze_vertical", 0.0) or 0.0)
        looking_away = bool(pose_info.get("looking_away", False))
        gaze_direction = (pose_info.get("gaze_direction") or "center").lower()

        history = self._history.setdefault(session_id, [])
        history.append(
            {
                "timestamp": current_time,
                "gaze_horizontal": gaze_horizontal,
                "gaze_vertical": gaze_vertical,
                "looking_away": looking_away,
                "gaze_direction": gaze_direction,
            }
        )
        if len(history) > self.sample_window:
            del history[: len(history) - self.sample_window]

        if len(history) < max(12, self.sample_window // 3):
            return AssistanceSignal(False, "warming_up", {"sample_count": len(history)})

        offscreen_samples = [
            item
            for item in history
            if item["looking_away"] or abs(item["gaze_horizontal"]) >= self.offscreen_threshold
        ]
        offscreen_ratio = len(offscreen_samples) / max(1, len(history))
        left_count = sum(1 for item in history if item["gaze_horizontal"] <= -self.offscreen_threshold)
        right_count = sum(1 for item in history if item["gaze_horizontal"] >= self.offscreen_threshold)
        direction_changes = self._direction_changes([item["gaze_horizontal"] for item in history])
        scan_score = direction_changes / max(1, len(history) - 1)

        suspected = (
            offscreen_ratio >= 0.45 and left_count and right_count
        ) or direction_changes >= 6 or (
            offscreen_ratio >= 0.6 and abs(gaze_horizontal) >= self.offscreen_threshold
        )

        last_alert_at = self._last_alert_at.get(session_id, 0.0)
        cooldown_remaining = max(0.0, self.min_alert_gap_seconds - (current_time - last_alert_at))
        should_alert = bool(suspected and cooldown_remaining <= 0)
        reason = "attention_scan_pattern" if direction_changes >= 6 else "repeated_offscreen_attention"

        details = {
            "reason": reason if suspected else "below_threshold",
            "sample_count": len(history),
            "offscreen_ratio": round(offscreen_ratio, 3),
            "direction_changes": direction_changes,
            "scan_score": round(scan_score, 3),
            "left_samples": left_count,
            "right_samples": right_count,
            "latest_gaze_horizontal": round(gaze_horizontal, 3),
            "latest_gaze_vertical": round(gaze_vertical, 3),
            "latest_gaze_direction": gaze_direction,
            "cooldown_remaining": round(cooldown_remaining, 2),
        }

        if should_alert:
            self._last_alert_at[session_id] = current_time
            history.clear()

        return AssistanceSignal(should_alert, reason if suspected else "below_threshold", details)

    def reset(self, session_id: str) -> None:
        self._history.pop(session_id, None)
        self._last_alert_at.pop(session_id, None)

    def _direction_changes(self, values: list[float]) -> int:
        directions: list[int] = []
        for value in values:
            if value >= self.scan_threshold:
                directions.append(1)
            elif value <= -self.scan_threshold:
                directions.append(-1)
            else:
                directions.append(0)

        compact: list[int] = []
        for direction in directions:
            if direction == 0:
                continue
            if not compact or compact[-1] != direction:
                compact.append(direction)
        return max(0, len(compact) - 1)
