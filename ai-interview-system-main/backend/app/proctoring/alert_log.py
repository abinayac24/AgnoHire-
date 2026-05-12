from __future__ import annotations

from collections import defaultdict, deque
from datetime import datetime
import json
from pathlib import Path
from threading import Lock

from app.proctoring.schemas import ViolationEvent


class AlertLogStore:
    def __init__(self, log_path: str = "backend/logs/proctoring_violations.jsonl", max_items: int = 2000) -> None:
        self._lock = Lock()
        self._max_items = max_items
        self._events_by_session: dict[str, deque[ViolationEvent]] = defaultdict(lambda: deque(maxlen=max_items))
        self._log_file = Path(log_path)
        self._log_file.parent.mkdir(parents=True, exist_ok=True)
        # Warning counter per session per rule
        self._warning_counters: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        # Last warning timestamp per session per rule (for debounce)
        self._last_warning_time: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))

    def add(self, event: ViolationEvent) -> None:
        with self._lock:
            self._events_by_session[event.session_id].append(event)
            with self._log_file.open("a", encoding="utf-8") as f:
                f.write(json.dumps(event.model_dump(mode="json"), ensure_ascii=True) + "\n")

    def list_session(self, session_id: str, limit: int = 200) -> list[ViolationEvent]:
        with self._lock:
            events = list(self._events_by_session.get(session_id, []))
            return events[-limit:]

    def health(self) -> dict:
        with self._lock:
            total = sum(len(v) for v in self._events_by_session.values())
            return {
                "sessions": len(self._events_by_session),
                "in_memory_events": total,
                "log_path": str(self._log_file),
                "updated_at": datetime.utcnow().isoformat(),
            }

    def get_warning_count(self, session_id: str, rule: str) -> int:
        """Get current warning count for a session and rule."""
        with self._lock:
            return self._warning_counters.get(session_id, {}).get(rule, 0)

    def increment_warning(self, session_id: str, rule: str, cooldown_seconds: float = 5.0) -> tuple[int, bool]:
        """
        Increment warning count for a session and rule.
        Returns (new_count, was_incremented) - was_incremented is False if on cooldown.
        """
        with self._lock:
            now = datetime.utcnow().timestamp()
            last_time = self._last_warning_time.get(session_id, {}).get(rule, 0)

            # Check cooldown to prevent rapid-fire increments
            if now - last_time < cooldown_seconds:
                return self._warning_counters[session_id][rule], False

            self._warning_counters[session_id][rule] += 1
            self._last_warning_time[session_id][rule] = now
            return self._warning_counters[session_id][rule], True

    def reset_warnings(self, session_id: str, rule: str | None = None) -> None:
        """Reset warning count for a session. If rule is None, reset all rules."""
        with self._lock:
            if rule is None:
                self._warning_counters.pop(session_id, None)
                self._last_warning_time.pop(session_id, None)
            else:
                if session_id in self._warning_counters:
                    self._warning_counters[session_id].pop(rule, None)
                if session_id in self._last_warning_time:
                    self._last_warning_time[session_id].pop(rule, None)

    def get_all_warning_counts(self, session_id: str) -> dict[str, int]:
        """Get all warning counts for a session."""
        with self._lock:
            return dict(self._warning_counters.get(session_id, {}))


alert_log_store = AlertLogStore()

