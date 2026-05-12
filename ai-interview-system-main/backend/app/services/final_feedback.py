from __future__ import annotations

from collections import Counter
import re

from app.services.advanced_feedback import advanced_feedback_generator

try:
    from app.proctoring.alert_log import alert_log_store
except Exception:  # pragma: no cover
    alert_log_store = None


def _clamp_score_1_10(value: float) -> int:
    return max(1, min(10, int(round(value))))


def _communication_score(report: dict) -> int:
    items = report.get("items", [])
    if not items:
        return 1

    answers = [item.get("answer", "") for item in items]
    words_per_answer = [len(re.findall(r"\b\w+\b", answer or "")) for answer in answers]
    avg_words = sum(words_per_answer) / max(1, len(words_per_answer))
    sentence_count = sum(max(1, len(re.findall(r"[.!?]", answer or ""))) for answer in answers)
    avg_sentences = sentence_count / max(1, len(answers))

    score = 4.5
    if avg_words >= 18:
        score += 1.5
    if avg_words >= 35:
        score += 1.2
    if avg_sentences >= 2:
        score += 1.0
    if avg_sentences >= 3:
        score += 0.8
    return _clamp_score_1_10(score)


def _technical_score(report: dict) -> int:
    total_score = float(report.get("total_score", 0))
    total_questions = max(1, int(report.get("total_questions", 0) or len(report.get("items", [])) or 1))
    return _clamp_score_1_10(total_score / total_questions)


def _behavior_alert_summary(session_id: str) -> tuple[list[str], dict[str, int]]:
    if not alert_log_store:
        return [], {}

    events = alert_log_store.list_session(session_id, limit=500)
    if not events:
        return [], {}

    rule_counts = Counter(event.rule for event in events)
    humanized: list[str] = []
    for rule, count in rule_counts.items():
        if rule == "eye_gaze":
            humanized.append(f"Looked away from screen {count} time(s)")
        elif rule == "mobile_phone":
            humanized.append(f"Mobile phone detected {count} time(s)")
        elif rule in {"multi_person", "multiple_people"}:
            humanized.append(f"Multiple person detected {count} time(s)")
        elif rule == "head_pose":
            humanized.append(f"Suspicious head movement detected {count} time(s)")
        elif rule in {"assistance_suspected", "reading_pattern"}:
            humanized.append(f"Suspicious assistance behavior detected {count} time(s)")
        elif rule == "partial_human":
            humanized.append(f"Partial human presence detected {count} time(s)")
        else:
            humanized.append(f"{rule} detected {count} time(s)")
    return humanized, dict(rule_counts)


def _confidence_score(rule_counts: dict[str, int]) -> int:
    score = 9.0
    score -= rule_counts.get("eye_gaze", 0) * 0.7
    score -= rule_counts.get("head_pose", 0) * 0.5
    score -= rule_counts.get("mobile_phone", 0) * 1.5
    score -= (rule_counts.get("multi_person", 0) + rule_counts.get("multiple_people", 0)) * 1.7
    score -= rule_counts.get("partial_human", 0) * 0.4
    return _clamp_score_1_10(score)


def _final_feedback_text(communication: int, confidence: int, technical: int, alerts: list[str]) -> str:
    strengths = []
    improvements = []

    if communication >= 8:
        strengths.append("good communication clarity")
    elif communication <= 5:
        improvements.append("speaking more clearly and with better structure")

    if confidence >= 8:
        strengths.append("steady interview presence")
    elif confidence <= 5:
        improvements.append("maintaining stronger focus on screen and posture")

    if technical >= 8:
        strengths.append("strong technical depth")
    elif technical <= 5:
        improvements.append("adding deeper technical reasoning and examples")

    if alerts:
        improvements.append("reducing proctoring alerts during the session")

    if not strengths:
        strengths.append("consistent participation across all questions")
    if not improvements:
        improvements.append("adding one more concrete project-level example per answer")

    return (
        f"Strong points: {', '.join(strengths)}. "
        f"Needs improvement in: {', '.join(dict.fromkeys(improvements))}."
    )


def enrich_report_with_final_feedback(report: dict, events: list[dict] | None = None) -> dict:
    session_id = report.get("session_id", "")
    alerts, rule_counts = _behavior_alert_summary(session_id)
    communication = _communication_score(report)
    technical = _technical_score(report)
    confidence = _confidence_score(rule_counts)
    feedback = _final_feedback_text(communication, confidence, technical, alerts)
    ai_feedback_report = advanced_feedback_generator.generate(report, events=events or [])

    report["scores"] = {
        "communication": communication,
        "confidence": confidence,
        "technical": technical,
    }
    report["alerts"] = alerts
    report["final_feedback"] = feedback
    report["ai_feedback_report"] = ai_feedback_report
    return report
