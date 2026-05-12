from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Callable
from uuid import uuid4

from pymongo import MongoClient
from pymongo.errors import PyMongoError

from app.config import settings


class DatabaseManager:
    def __init__(self) -> None:
        self.mode = "memory"
        self._memory = {
            "Users": [],
            "Questions": [],
            "CompanyQuestions": [],
            "InterviewResults": [],
            "InterviewSessions": [],
        }
        self.client = None
        self.db = None
        if not settings.use_in_memory_db:
            self._connect_mongo()

    def _connect_mongo(self) -> None:
        try:
            self.client = MongoClient(settings.mongodb_url, serverSelectionTimeoutMS=2000)
            self.client.admin.command("ping")
            self.db = self.client[settings.mongodb_db_name]
            self.mode = "mongo"
        except PyMongoError:
            self.client = None
            self.db = None
            self.mode = "memory"

    def _collection(self, name: str):
        return self.db[name]

    def create_session(
        self,
        candidate_name: str,
        mode: str,
        metadata: dict,
        questions: list[dict],
        candidate_email: str = "",
    ):
        session_id = uuid4().hex
        user_id = uuid4().hex
        now = datetime.utcnow()
        user_doc = {
            "user_id": user_id,
            "candidate_name": candidate_name,
            "candidate_email": candidate_email,
            "created_at": now,
        }
        session_doc = {
            "session_id": session_id,
            "user_id": user_id,
            "candidate_name": candidate_name,
            "candidate_email": candidate_email,
            "mode": mode,
            "metadata": metadata,
            "questions": [
                {
                    "id": question.get("id", uuid4().hex),
                    "question": question["question"],
                    "expected_keywords": question.get("expected_keywords", []),
                    "source": question.get("source", "generated"),
                }
                for question in questions[:5]
            ],
            "current_index": 0,
            "status": "in_progress",
            "greeting": "",
            "report_email_sent": False,
            "created_at": now,
        }

        if self.mode == "mongo":
            self._collection("Users").insert_one(user_doc)
            self._collection("Questions").insert_many(
                [
                    {
                        "session_id": session_id,
                        "candidate_name": candidate_name,
                        "candidate_email": candidate_email,
                        **question,
                        "created_at": now,
                    }
                    for question in session_doc["questions"]
                ]
            )
            self._collection("InterviewSessions").insert_one(session_doc)
        else:
            self._memory["Users"].append(user_doc)
            self._memory["Questions"].extend(
                [
                    {
                        "session_id": session_id,
                        "candidate_name": candidate_name,
                        "candidate_email": candidate_email,
                        **question,
                        "created_at": now,
                    }
                    for question in session_doc["questions"]
                ]
            )
            self._memory["InterviewSessions"].append(session_doc)
        return deepcopy(session_doc)

    def store_company_questions(self, session_id: str, questions: list[dict]) -> None:
        docs = [
            {
                "session_id": session_id,
                "question_id": question["id"],
                "question": question["question"],
                "expected_keywords": question.get("expected_keywords", []),
                "created_at": datetime.utcnow(),
            }
            for question in questions[:5]
        ]
        if self.mode == "mongo":
            self._collection("CompanyQuestions").insert_many(docs)
        else:
            self._memory["CompanyQuestions"].extend(docs)

    def update_session_greeting(self, session_id: str, greeting: str) -> None:
        session = self.get_session(session_id)
        if not session:
            return
        if self.mode == "mongo":
            self._collection("InterviewSessions").update_one(
                {"session_id": session_id},
                {"$set": {"greeting": greeting}},
            )
        else:
            session["greeting"] = greeting

    def get_session(self, session_id: str):
        if self.mode == "mongo":
            return self._collection("InterviewSessions").find_one({"session_id": session_id}, {"_id": 0})
        for session in self._memory["InterviewSessions"]:
            if session["session_id"] == session_id:
                return session
        return None

    def get_current_question(self, session_id: str):
        session = self.get_session(session_id)
        if not session:
            return None
        questions = session.get("questions", [])
        index = session.get("current_index", 0)
        if index >= len(questions):
            return None
        return deepcopy(questions[index])

    def build_session_view(self, session_id: str):
        session = self.get_session(session_id)
        if not session:
            return None
        question = self.get_current_question(session_id)
        return {
            "session_id": session["session_id"],
            "candidate_name": session["candidate_name"],
            "candidate_email": session.get("candidate_email", ""),
            "mode": session["mode"],
            "current_index": session["current_index"],
            "total_questions": len(session.get("questions", [])),
            "status": session["status"],
            "greeting": session.get("greeting", ""),
            "question": question,
            "transcript_hint": "Use the Whisper recorder to capture the answer.",
        }

    def record_answer(self, session_id: str, question: dict, answer: str, evaluation: dict) -> None:
        session = self.get_session(session_id)
        if not session:
            return
        doc = {
            "session_id": session_id,
            "candidate_name": session["candidate_name"],
            "candidate_email": session.get("candidate_email", ""),
            "mode": session["mode"],
            "question_id": question["id"],
            "question": question["question"],
            "user_answer": answer,
            "score": evaluation["score"],
            "feedback": evaluation["feedback"],
            "improvement_suggestion": evaluation["improvement_suggestion"],
            "matched_keywords": evaluation.get("matched_keywords", []),
            "missing_keywords": evaluation.get("missing_keywords", []),
            "timestamp": datetime.utcnow(),
        }
        if self.mode == "mongo":
            self._collection("InterviewResults").insert_one(doc)
        else:
            self._memory["InterviewResults"].append(doc)

    def advance_session(self, session_id: str) -> None:
        session = self.get_session(session_id)
        if not session:
            return
        next_index = session["current_index"] + 1
        status = "completed" if next_index >= len(session.get("questions", [])) else "in_progress"
        if self.mode == "mongo":
            self._collection("InterviewSessions").update_one(
                {"session_id": session_id},
                {"$set": {"current_index": next_index, "status": status}},
            )
        else:
            session["current_index"] = next_index
            session["status"] = status

    def mark_report_email_sent(self, session_id: str, sent: bool = True) -> None:
        if self.mode == "mongo":
            self._collection("InterviewSessions").update_one(
                {"session_id": session_id},
                {"$set": {"report_email_sent": sent}},
            )
            return

        session = self.get_session(session_id)
        if session:
            session["report_email_sent"] = sent

    def report_email_sent(self, session_id: str) -> bool:
        session = self.get_session(session_id)
        if not session:
            return False
        return bool(session.get("report_email_sent"))

    def _results_for_session(self, session_id: str) -> list[dict]:
        if self.mode == "mongo":
            return list(self._collection("InterviewResults").find({"session_id": session_id}, {"_id": 0}))
        return [item for item in self._memory["InterviewResults"] if item["session_id"] == session_id]

    def build_report(self, session_id: str, summary_builder: Callable[[list[dict]], dict]):
        session = self.get_session(session_id)
        if not session:
            return None
        results = self._results_for_session(session_id)
        if not results:
            return None

        overall_score = round(sum(item["score"] for item in results) / len(results))
        summary = summary_builder(results)
        return {
            "session_id": session_id,
            "candidate_name": session["candidate_name"],
            "candidate_email": session.get("candidate_email", ""),
            "mode": session["mode"],
            "total_questions": len(results),
            "overall_score": overall_score,
            "strengths": summary["strengths"],
            "weaknesses": summary["weaknesses"],
            "improvement_suggestions": summary["improvement_suggestions"],
            "items": [
                {
                    "question": item["question"],
                    "answer": item["user_answer"],
                    "score": item["score"],
                    "feedback": item["feedback"],
                    "improvement_suggestion": item["improvement_suggestion"],
                    "matched_keywords": item.get("matched_keywords", []),
                    "missing_keywords": item.get("missing_keywords", []),
                }
                for item in results
            ],
            "generated_at": datetime.utcnow(),
        }


db_manager = DatabaseManager()
