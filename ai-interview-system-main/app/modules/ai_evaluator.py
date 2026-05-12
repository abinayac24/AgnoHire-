from __future__ import annotations

import re
from collections import Counter

import requests

from app.config import settings


DOMAIN_BANK = {
    "Java": [
        "Explain how encapsulation improves maintainability in a Java application.",
        "What is the difference between an interface and an abstract class in Java?",
        "How does exception handling work in Java, and why is it useful?",
        "Describe method overriding with a simple example from a real project.",
        "How would you optimize a Java API that is responding slowly?",
    ],
    "Python": [
        "What makes Python dictionaries useful in backend development?",
        "Explain list comprehension and where you would use it in a real project.",
        "How do Python exceptions help you build reliable applications?",
        "Describe the difference between a list and a tuple in Python.",
        "How would you structure a Python project for maintainability?",
    ],
    "Web Development": [
        "How does the browser render an HTML page after the first request?",
        "What is the difference between client-side and server-side rendering?",
        "Why is responsive design important in a production web application?",
        "How would you improve the performance of a slow web page?",
        "Explain how REST APIs are used in modern web applications.",
    ],
    "AI / Machine Learning": [
        "What is the difference between supervised and unsupervised learning?",
        "How do you measure whether a machine learning model is performing well?",
        "Describe a machine learning project and the biggest challenge in it.",
        "Why is data preprocessing important before model training?",
        "What trade-offs would you consider when choosing a model for production?",
    ],
    "Spring Boot": [
        "Why is dependency injection useful in a Spring Boot application?",
        "How do controllers, services, and repositories work together in Spring Boot?",
        "What is the role of application properties in a Spring Boot project?",
        "How would you secure a Spring Boot REST API?",
        "What steps would you take to debug a failing Spring Boot service?",
    ],
    "React": [
        "How does state management affect the behavior of a React component?",
        "What is the difference between props and state in React?",
        "Why are reusable components important in frontend architecture?",
        "How would you debug unnecessary re-renders in React?",
        "Describe how React talks to a backend API in a real application.",
    ],
}


class AIEvaluator:
    def generate_domain_questions(self, domain: str, count: int = 5) -> list[dict]:
        bank = DOMAIN_BANK.get(domain, DOMAIN_BANK["Python"])
        return [{"question": question, "source": "domain-bank"} for question in bank[:count]]

    def generate_resume_questions(self, parsed_resume: dict, count: int = 5) -> list[dict]:
        skills = parsed_resume.get("skills", [])[:3]
        projects = parsed_resume.get("projects", [])[:2]
        technologies = parsed_resume.get("technologies", [])[:3]

        generated = []
        for skill in skills:
            generated.append({"question": f"Explain your practical experience with {skill}.", "source": "resume"})
        for project in projects:
            generated.append({"question": f"Describe the architecture and challenges of {project}.", "source": "resume"})
        for technology in technologies:
            generated.append({"question": f"Why did you use {technology} and what problem did it solve?", "source": "resume"})

        if not generated:
            generated = [
                {"question": "Describe the most impactful project on your resume.", "source": "resume"},
                {"question": "Which technology on your resume are you strongest in, and why?", "source": "resume"},
                {"question": "Tell me about a difficult bug you solved in one of your projects.", "source": "resume"},
                {"question": "How did you validate the quality of your work before delivery?", "source": "resume"},
                {"question": "What would you improve if you rebuilt your strongest project today?", "source": "resume"},
            ]
        return generated[:count]

    def evaluate_answer(self, question: str, answer: str, context: dict) -> dict:
        normalized_answer = (answer or "").strip()
        if normalized_answer and normalized_answer.upper() not in {"NO_ANSWER", "SKIPPED"} and settings.gemini_api_key:
            ai_result = self._evaluate_with_gemini(question, answer, context)
            if ai_result:
                return ai_result
        return self._heuristic_evaluation(question, answer)

    def summarize_report(self, results: list[dict]) -> dict:
        strengths = []
        weaknesses = []
        suggestions = []
        for item in results:
            if item["score"] >= 75:
                strengths.append(f"Strong answer quality on: {item['question']}")
            else:
                weaknesses.append(f"Needs more depth on: {item['question']}")
            suggestions.append(item["improvement_suggestion"])

        if not strengths:
            strengths.append("You attempted all questions and kept the interview moving.")
        if not weaknesses:
            weaknesses.append("Focus on keeping the same level of depth across all questions.")

        deduped_suggestions = list(dict.fromkeys(suggestions))
        return {
            "strengths": strengths[:3],
            "weaknesses": weaknesses[:3],
            "improvement_suggestions": deduped_suggestions[:5],
        }

    def _evaluate_with_gemini(self, question: str, answer: str, context: dict) -> dict | None:
        prompt = f"""
You are evaluating an interview answer.
Mode: {context.get('mode')}
Question: {question}
Candidate answer: {answer}

Return exactly:
Score: <0-100>
Feedback: <short feedback>
Improvement: <one improvement suggestion>
""".strip()
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{settings.gemini_model}:generateContent?key={settings.gemini_api_key}"
        )
        try:
            response = requests.post(
                url,
                json={"contents": [{"parts": [{"text": prompt}]}]},
                timeout=settings.gemini_timeout_seconds,
            )
            response.raise_for_status()
            text = response.json()["candidates"][0]["content"]["parts"][0]["text"]
            return self._parse_model_response(text)
        except (requests.RequestException, KeyError, IndexError, ValueError):
            return None

    def _parse_model_response(self, text: str) -> dict:
        score_match = re.search(r"Score\s*:\s*(\d+)", text)
        feedback_match = re.search(r"Feedback\s*:\s*(.+)", text)
        improvement_match = re.search(r"Improvement\s*:\s*(.+)", text)
        score = int(score_match.group(1)) if score_match else 60
        return {
            "score": max(0, min(score, 100)),
            "feedback": feedback_match.group(1).strip() if feedback_match else "The answer was evaluated successfully.",
            "improvement_suggestion": improvement_match.group(1).strip() if improvement_match else "Add more specific technical examples.",
        }

    def _heuristic_evaluation(self, question: str, answer: str) -> dict:
        words = re.findall(r"\b\w+\b", answer.lower())
        question_words = re.findall(r"\b\w+\b", question.lower())
        word_count = len(words)
        overlap = len(set(words) & set(question_words))
        repeated_ratio = 0
        if words:
            counts = Counter(words)
            repeated_ratio = max(counts.values()) / len(words)

        score = 35
        if word_count > 20:
            score += 20
        if word_count > 45:
            score += 15
        if overlap > 2:
            score += 10
        if any(token in words for token in ["because", "example", "used", "built", "design", "performance"]):
            score += 10
        if repeated_ratio > 0.3:
            score -= 10
        score = max(10, min(score, 95))

        if score >= 75:
            feedback = "Strong answer with relevant technical detail and reasonable clarity."
            suggestion = "Add one more concrete project example to make the answer even stronger."
        elif score >= 55:
            feedback = "The answer is relevant, but it needs more depth and structure."
            suggestion = "Explain your reasoning step by step and connect it to a real implementation."
        else:
            feedback = "The answer is brief or generic, so the technical depth is limited."
            suggestion = "Define the core concept, then add one example and one practical trade-off."

        return {
            "score": score,
            "feedback": feedback,
            "improvement_suggestion": suggestion,
        }


evaluator = AIEvaluator()
