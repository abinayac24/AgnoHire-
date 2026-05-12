from __future__ import annotations

from collections import Counter
from datetime import datetime
import re


FILLER_WORDS = {
    "um",
    "umm",
    "uh",
    "uhh",
    "ah",
    "ahh",
    "like",
    "basically",
    "actually",
    "literally",
    "sort",
    "kind",
}


def _clamp(value: float, low: int = 1, high: int = 10) -> int:
    return max(low, min(high, int(round(value))))


def _words(text: str) -> list[str]:
    return re.findall(r"\b[\w']+\b", (text or "").lower())


def _sentences(text: str) -> list[str]:
    chunks = [item.strip() for item in re.split(r"[.!?]+", text or "") if item.strip()]
    return chunks or ([text.strip()] if (text or "").strip() else [])


def _answer_texts(report: dict) -> list[str]:
    return [
        (item.get("answer") or item.get("user_answer") or "").strip()
        for item in report.get("items", [])
    ]


def _event_counts(events: list[dict]) -> Counter:
    counts = Counter()
    for event in events or []:
        event_type = (event.get("type") or event.get("event_type") or "").strip()
        payload = event.get("payload") or {}
        rule = (payload.get("rule") if isinstance(payload, dict) else "") or event_type
        if rule:
            counts[rule] += 1
    return counts


def _normalize_item_score(value) -> int:
    try:
        numeric = float(value or 0)
    except (TypeError, ValueError):
        numeric = 0.0
    if numeric > 10:
        numeric = numeric / 10.0
    return max(0, min(10, int(round(numeric))))


class AdvancedFeedbackGenerator:
    def generate(self, report: dict, events: list[dict] | None = None) -> dict:
        answers = _answer_texts(report)
        all_words = [word for answer in answers for word in _words(answer)]
        filler_count = sum(1 for word in all_words if word in FILLER_WORDS)
        answered = [
            answer
            for answer in answers
            if answer and answer.upper() not in {"NO_ANSWER", "SKIPPED"}
        ]
        word_counts = [len(_words(answer)) for answer in answered]
        sentence_counts = [len(_sentences(answer)) for answer in answered]
        avg_words = sum(word_counts) / max(1, len(word_counts))
        avg_sentences = sum(sentence_counts) / max(1, len(sentence_counts))
        filler_rate = filler_count / max(1, len(all_words))
        event_counts = _event_counts(events or [])

        technical_scores = [_normalize_item_score(item.get("score", 0)) for item in report.get("items", [])]
        avg_technical = sum(technical_scores) / max(1, len(technical_scores))

        communication_score = _clamp(
            4.0
            + min(avg_words, 55) / 12.0
            + min(avg_sentences, 3) * 0.7
            - filler_rate * 18
        )
        confidence_score = _clamp(
            8.5
            - filler_rate * 20
            - event_counts.get("eye_gaze", 0) * 0.4
            - event_counts.get("assistance_suspected", 0) * 0.8
            - event_counts.get("response_warning", 0) * 0.5
            - event_counts.get("no_response_timeout", 0) * 1.0
        )
        technical_score = _clamp(avg_technical)

        communication_summary = self._communication_summary(
            communication_score, avg_words, avg_sentences, filler_count, filler_rate
        )
        confidence_summary = self._confidence_summary(confidence_score, event_counts, filler_count)
        technical_summary = self._technical_summary(report, technical_score)
        suggestions = self._suggestions(
            communication_score=communication_score,
            confidence_score=confidence_score,
            technical_score=technical_score,
            filler_count=filler_count,
            event_counts=event_counts,
        )

        return {
            "generated_at": datetime.utcnow(),
            "communication": {
                "score": communication_score,
                "summary": communication_summary,
                "fluency": self._fluency_label(communication_score),
                "avg_words_per_answer": round(avg_words, 1),
                "avg_sentence_units_per_answer": round(avg_sentences, 1),
                "filler_word_count": filler_count,
                "filler_word_rate": round(filler_rate, 3),
            },
            "confidence": {
                "score": confidence_score,
                "summary": confidence_summary,
                "filler_word_count": filler_count,
                "hesitation_indicators": {
                    "response_warnings": int(event_counts.get("response_warning", 0)),
                    "no_response_timeouts": int(event_counts.get("no_response_timeout", 0)),
                    "assistance_warnings": int(event_counts.get("assistance_suspected", 0)),
                },
            },
            "technical_answer_quality": {
                "score": technical_score,
                "summary": technical_summary,
                "average_question_score": round(avg_technical, 1),
                "strong_answers": [
                    item.get("question", "")
                    for item in report.get("items", [])
                    if _normalize_item_score(item.get("score", 0)) >= 8
                ][:3],
                "needs_depth": [
                    item.get("question", "")
                    for item in report.get("items", [])
                    if _normalize_item_score(item.get("score", 0)) <= 5
                ][:3],
            },
            "improvement_suggestions": suggestions,
        }

    @staticmethod
    def _fluency_label(score: int) -> str:
        if score >= 8:
            return "Clear and structured"
        if score >= 6:
            return "Understandable with room for sharper structure"
        return "Needs clearer articulation and answer structure"

    @staticmethod
    def _communication_summary(score: int, avg_words: float, avg_sentences: float, filler_count: int, filler_rate: float) -> str:
        if score >= 8:
            return "The candidate communicated with good clarity, sufficient answer length, and coherent phrasing."
        if filler_count > 8 or filler_rate > 0.05:
            return "Communication was understandable, but filler-word usage and hesitations reduced clarity."
        if avg_words < 18:
            return "Answers were concise but often too brief to fully demonstrate articulation and clarity."
        if avg_sentences < 2:
            return "Answers would benefit from clearer multi-step structure."
        return "Communication was adequate, with opportunities to improve fluency and structure."

    @staticmethod
    def _confidence_summary(score: int, event_counts: Counter, filler_count: int) -> str:
        if score >= 8:
            return "The candidate appeared steady and confident with limited hesitation indicators."
        indicators = []
        if filler_count:
            indicators.append(f"{filler_count} filler word(s)")
        if event_counts.get("eye_gaze"):
            indicators.append("off-screen gaze events")
        if event_counts.get("assistance_suspected"):
            indicators.append("possible assistance-reading patterns")
        if event_counts.get("response_warning") or event_counts.get("no_response_timeout"):
            indicators.append("delayed response behavior")
        if not indicators:
            indicators.append("some uneven answer delivery")
        return f"Confidence was mixed, with signals including {', '.join(indicators)}."

    @staticmethod
    def _technical_summary(report: dict, technical_score: int) -> str:
        if technical_score >= 8:
            return "Technical responses were generally relevant, complete, and supported by useful details."
        if technical_score >= 6:
            return "Technical responses were relevant but would benefit from deeper examples, trade-offs, and implementation detail."
        return "Technical responses were often brief or incomplete and need stronger concept coverage."

    @staticmethod
    def _suggestions(
        communication_score: int,
        confidence_score: int,
        technical_score: int,
        filler_count: int,
        event_counts: Counter,
    ) -> list[str]:
        suggestions = []
        if communication_score < 8:
            suggestions.append("Use a simple structure for each answer: definition, practical example, and impact.")
        if filler_count > 5:
            suggestions.append("Practice short pauses instead of filler words such as um, uh, like, or basically.")
        if confidence_score < 8:
            suggestions.append("Maintain steady eye contact with the screen and answer without looking away repeatedly.")
        if event_counts.get("assistance_suspected"):
            suggestions.append("Avoid reading from another screen or notes; prepare key concepts before the interview.")
        if technical_score < 8:
            suggestions.append("Add concrete implementation details, trade-offs, and project examples to technical answers.")
        if not suggestions:
            suggestions.append("Continue strengthening answers with one concise real-world example per question.")
        return list(dict.fromkeys(suggestions))[:5]


advanced_feedback_generator = AdvancedFeedbackGenerator()
