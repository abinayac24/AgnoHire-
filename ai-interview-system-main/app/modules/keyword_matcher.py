from __future__ import annotations


class KeywordMatcher:
    def evaluate_answer(self, answer: str, expected_keywords: list[str], question: str) -> dict:
        lowered_answer = answer.lower()
        normalized_keywords = [keyword.strip() for keyword in expected_keywords if keyword.strip()]
        matched = [keyword for keyword in normalized_keywords if keyword.lower() in lowered_answer]
        missing = [keyword for keyword in normalized_keywords if keyword not in matched]
        total = len(normalized_keywords) or 1
        score = round((len(matched) / total) * 100)

        if matched:
            feedback = f"The answer covered {len(matched)} of {len(normalized_keywords)} expected keywords."
        else:
            feedback = f"The answer did not cover the core keywords expected for: {question}"

        if missing:
            suggestion = f"Include these missing ideas next time: {', '.join(missing[:5])}."
        else:
            suggestion = "Good coverage. Next step is to improve structure and real-world explanation."

        return {
            "score": score,
            "feedback": feedback,
            "improvement_suggestion": suggestion,
            "matched_keywords": matched,
            "missing_keywords": missing,
        }


keyword_matcher = KeywordMatcher()
