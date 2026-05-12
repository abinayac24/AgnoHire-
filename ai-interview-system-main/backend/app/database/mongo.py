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
            "InterviewFinalReports": [],
            "InterviewEvents": [],
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

    @staticmethod
    def _performance_label(total_score: int) -> str:
        if total_score >= 40:
            return "Excellent"
        if total_score >= 30:
            return "Good"
        if total_score >= 20:
            return "Average"
        return "Needs Improvement"

    @staticmethod
    def _result_status(total_score: int) -> str:
        return "PASS" if total_score >= 25 else "FAIL"

    @staticmethod
    def _normalize_question_score(value) -> int:
        try:
            numeric = float(value or 0)
        except (TypeError, ValueError):
            numeric = 0.0
        if numeric > 10:
            numeric = numeric / 10.0
        return max(0, min(10, int(round(numeric))))

    def _normalize_final_report(self, record: dict | None) -> dict | None:
        if not record:
            return None

        normalized = deepcopy(record)
        items = normalized.get("items") or normalized.get("report", {}).get("items") or []
        safe_items = []
        for index, item in enumerate(items[:5], start=1):
            safe_items.append(
                {
                    "question_id": item.get("question_id", ""),
                    "question_number": item.get("question_number", index),
                    "question": item.get("question", ""),
                    "answer": item.get("answer", item.get("user_answer", "")),
                    "score": self._normalize_question_score(item.get("score", 0)),
                    "max_score": int(item.get("max_score", 10) or 10),
                    "feedback": item.get("feedback", ""),
                    "improvement_suggestion": item.get("improvement_suggestion", ""),
                    "matched_keywords": item.get("matched_keywords", []),
                    "missing_keywords": item.get("missing_keywords", []),
                }
            )
        normalized["items"] = safe_items

        question_scores = normalized.get("question_scores") or [
            {
                "question_id": item.get("question_id", ""),
                "question_number": item.get("question_number", index),
                "score": self._normalize_question_score(item.get("score", 0)),
                "max_score": int(item.get("max_score", 10) or 10),
            }
            for index, item in enumerate(safe_items, start=1)
        ]
        normalized["question_scores"] = question_scores

        total_score = normalized.get("total_score")
        if total_score is None:
            total_score = sum(int(item.get("score", 0) or 0) for item in safe_items)
        total_score = max(0, min(int(total_score), 50))
        normalized["total_score"] = total_score
        normalized["overall_score"] = int(normalized.get("overall_score", round((total_score / 50) * 100)) or 0)
        normalized["performance_label"] = normalized.get("performance_label") or self._performance_label(total_score)
        normalized["result_status"] = normalized.get("result_status") or self._result_status(total_score)
        normalized["scores"] = normalized.get("scores") or {}
        normalized["strengths"] = normalized.get("strengths") or []
        normalized["weaknesses"] = normalized.get("weaknesses") or []
        normalized["alerts"] = normalized.get("alerts") or []
        normalized["final_feedback"] = normalized.get("final_feedback", "")
        normalized["ai_feedback_report"] = normalized.get("ai_feedback_report") or (normalized.get("report") or {}).get("ai_feedback_report") or {}
        return normalized

    def _ensure_question_ids(self, session: dict | None) -> dict | None:
        if not session:
            return None
        questions = session.get("questions", [])
        if not questions:
            return session

        changed = False
        for question in questions:
            if not question.get("id"):
                question["id"] = uuid4().hex
                changed = True

        if not changed:
            return session

        session_id = session.get("session_id")
        if self.mode == "mongo" and session_id:
            self._collection("InterviewSessions").update_one(
                {"session_id": session_id},
                {"$set": {"questions": questions}},
            )
            for question in questions:
                self._collection("Questions").update_many(
                    {
                        "session_id": session_id,
                        "question": question.get("question", ""),
                        "$or": [{"id": {"$exists": False}}, {"id": None}, {"id": ""}],
                    },
                    {"$set": {"id": question["id"]}},
                )
        return session

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
            "role": "user",
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
                    "id": question.get("id") or uuid4().hex,
                    "question": question["question"],
                    "expected_keywords": question.get("expected_keywords", []),
                    "source": question.get("source", "generated"),
                }
                for question in questions[:5]
            ],
            "current_index": 0,
            "status": "in_progress",
            "termination_reason": "",
            "terminated_at": None,
            "ended_by": "",
            "greeting": "",
            "report_email_sent": False,
            "report_email_scheduled": False,
            "report_email_status": "pending",
            "report_email_error": "",
            "report_email_updated_at": now,
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
            session = self._collection("InterviewSessions").find_one({"session_id": session_id}, {"_id": 0})
            return self._ensure_question_ids(session)
        for session in self._memory["InterviewSessions"]:
            if session["session_id"] == session_id:
                return self._ensure_question_ids(session)
        return None

    def get_current_question(self, session_id: str):
        session = self.get_session(session_id)
        if not session:
            return None
        questions = session.get("questions", [])
        max_questions = min(5, len(questions))
        index = session.get("current_index", 0)
        if index >= max_questions:
            return None
        return deepcopy(questions[index])

    def get_next_question_preview(self, session_id: str):
        session = self.get_session(session_id)
        if not session:
            return None
        questions = session.get("questions", [])
        max_questions = min(5, len(questions))
        next_index = session.get("current_index", 0) + 1
        if next_index >= max_questions:
            return None
        return deepcopy(questions[next_index])

    def build_session_view(self, session_id: str):
        session = self.get_session(session_id)
        if not session:
            return None
        total_questions = min(5, len(session.get("questions", [])))
        question = self.get_current_question(session_id)
        return {
            "session_id": session["session_id"],
            "candidate_name": session["candidate_name"],
            "candidate_email": session.get("candidate_email", ""),
            "mode": session["mode"],
            "current_index": session["current_index"],
            "total_questions": total_questions,
            "status": session["status"],
            "greeting": session.get("greeting", ""),
            "question": question,
            "transcript_hint": "Use the Whisper recorder to capture the answer.",
            "termination_reason": session.get("termination_reason", ""),
            "terminated_at": session.get("terminated_at"),
            "ended_by": session.get("ended_by", ""),
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
            "score": evaluation["score"] if evaluation else 0,
            "feedback": evaluation["feedback"] if evaluation else "Evaluation pending...",
            "improvement_suggestion": evaluation["improvement_suggestion"] if evaluation else "Evaluation pending...",
            "matched_keywords": evaluation.get("matched_keywords", []) if evaluation else [],
            "missing_keywords": evaluation.get("missing_keywords", []) if evaluation else [],
            "timestamp": datetime.utcnow(),
        }
        if self.mode == "mongo":
            self._collection("InterviewResults").insert_one(doc)
        else:
            self._memory["InterviewResults"].append(doc)

    def update_evaluation(self, session_id: str, question_id: str, evaluation: dict) -> None:
        payload = {
            "score": evaluation.get("score", 0),
            "feedback": evaluation.get("feedback", ""),
            "improvement_suggestion": evaluation.get("improvement_suggestion", ""),
            "matched_keywords": evaluation.get("matched_keywords", []),
            "missing_keywords": evaluation.get("missing_keywords", []),
        }
        if self.mode == "mongo":
            self._collection("InterviewResults").update_one(
                {"session_id": session_id, "question_id": question_id},
                {"$set": payload},
            )
        else:
            for row in self._memory["InterviewResults"]:
                if row["session_id"] == session_id and row["question_id"] == question_id:
                    row.update(payload)
                    break

    def advance_session(self, session_id: str) -> None:
        session = self.get_session(session_id)
        if not session:
            return
        max_questions = min(5, len(session.get("questions", [])))
        next_index = min(session["current_index"] + 1, max_questions)
        status = "completed" if next_index >= max_questions else "in_progress"
        if self.mode == "mongo":
            self._collection("InterviewSessions").update_one(
                {"session_id": session_id},
                {"$set": {"current_index": next_index, "status": status}},
            )
        else:
            session["current_index"] = next_index
            session["status"] = status

    def terminate_session(self, session_id: str, reason: str, ended_by: str = "system") -> None:
        session = self.get_session(session_id)
        if not session:
            return
        now = datetime.utcnow()
        payload = {
            "status": "terminated",
            "termination_reason": (reason or "Interview terminated").strip()[:300],
            "terminated_at": now,
            "ended_by": (ended_by or "system").strip()[:50],
        }
        if self.mode == "mongo":
            self._collection("InterviewSessions").update_one({"session_id": session_id}, {"$set": payload})
            return
        session.update(payload)

    def set_completion_reason(self, session_id: str, reason: str = "Interview completed successfully") -> None:
        session = self.get_session(session_id)
        if not session:
            return
        payload = {
            "status": "completed",
            "termination_reason": (reason or "Interview completed successfully").strip()[:300],
            "terminated_at": datetime.utcnow(),
            "ended_by": "system",
        }
        if self.mode == "mongo":
            self._collection("InterviewSessions").update_one({"session_id": session_id}, {"$set": payload})
            return
        session.update(payload)

    def append_session_event(self, session_id: str, event_type: str, message: str, level: str = "info", payload: dict | None = None) -> None:
        row = {
            "session_id": session_id,
            "type": (event_type or "event").strip()[:80],
            "message": (message or "").strip()[:600],
            "level": (level or "info").strip()[:20],
            "payload": payload or {},
            "timestamp": datetime.utcnow(),
        }
        if self.mode == "mongo":
            self._collection("InterviewEvents").insert_one(row)
            return
        self._memory["InterviewEvents"].append(row)

    def list_session_events(self, session_id: str, limit: int = 200) -> list[dict]:
        max_items = max(1, min(limit, 1000))
        if self.mode == "mongo":
            return list(
                self._collection("InterviewEvents")
                .find({"session_id": session_id}, {"_id": 0})
                .sort("timestamp", -1)
                .limit(max_items)
            )
        items = [item for item in self._memory["InterviewEvents"] if item["session_id"] == session_id]
        items.sort(key=lambda item: item.get("timestamp", datetime.min), reverse=True)
        return deepcopy(items[:max_items])

    def mark_report_email_sent(self, session_id: str, sent: bool = True) -> None:
        status = "sent" if sent else "failed"
        if self.mode == "mongo":
            self._collection("InterviewSessions").update_one(
                {"session_id": session_id},
                {
                    "$set": {
                        "report_email_sent": sent,
                        "report_email_scheduled": False,
                        "report_email_status": status,
                        "report_email_updated_at": datetime.utcnow(),
                    }
                },
            )
            return

        session = self.get_session(session_id)
        if session:
            session["report_email_sent"] = sent
            session["report_email_scheduled"] = False
            session["report_email_status"] = status
            session["report_email_updated_at"] = datetime.utcnow()

    def mark_report_email_scheduled(self, session_id: str, scheduled: bool = True) -> None:
        status = "scheduled" if scheduled else "pending"
        now = datetime.utcnow()
        if self.mode == "mongo":
            self._collection("InterviewSessions").update_one(
                {"session_id": session_id},
                {
                    "$set": {
                        "report_email_scheduled": scheduled,
                        "report_email_status": status,
                        "report_email_updated_at": now,
                    }
                },
            )
            return

        session = self.get_session(session_id)
        if session:
            session["report_email_scheduled"] = scheduled
            session["report_email_status"] = status
            session["report_email_updated_at"] = now

    def report_email_scheduled(self, session_id: str) -> bool:
        session = self.get_session(session_id)
        if not session:
            return False
        return bool(session.get("report_email_scheduled", False))

    def report_email_sent(self, session_id: str) -> bool:
        session = self.get_session(session_id)
        if not session:
            return False
        return bool(session.get("report_email_sent"))

    def update_report_email_status(self, session_id: str, status: str, error: str = "") -> None:
        allowed = {"pending", "scheduled", "sent", "failed", "skipped"}
        normalized = status if status in allowed else "pending"
        now = datetime.utcnow()
        if self.mode == "mongo":
            self._collection("InterviewSessions").update_one(
                {"session_id": session_id},
                {
                    "$set": {
                        "report_email_status": normalized,
                        "report_email_error": (error or "")[:500],
                        "report_email_updated_at": now,
                    }
                },
            )
            return

        session = self.get_session(session_id)
        if session:
            session["report_email_status"] = normalized
            session["report_email_error"] = (error or "")[:500]
            session["report_email_updated_at"] = now

    def get_report_email_status(self, session_id: str) -> dict | None:
        session = self.get_session(session_id)
        if not session:
            return None
        return {
            "status": session.get("report_email_status", "pending"),
            "scheduled": bool(session.get("report_email_scheduled", False)),
            "sent": bool(session.get("report_email_sent", False)),
            "error": session.get("report_email_error", ""),
            "updated_at": session.get("report_email_updated_at"),
            "candidate_email": session.get("candidate_email", ""),
        }

    def save_final_report(self, session_id: str, report: dict) -> None:
        session = self.get_session(session_id)
        if not session:
            return

        timestamp = datetime.utcnow()
        doc = {
            "session_id": session_id,
            "candidate_name": report.get("candidate_name", session.get("candidate_name", "")),
            "candidate_email": report.get("candidate_email", session.get("candidate_email", "")),
            "scores": report.get("scores", {}),
            "strengths": report.get("strengths", []),
            "weaknesses": report.get("weaknesses", []),
            "alerts": report.get("alerts", []),
            "final_feedback": report.get("final_feedback", ""),
            "ai_feedback_report": report.get("ai_feedback_report", {}),
            "items": report.get("items", []),
            "question_scores": report.get("question_scores", []),
            "mode": report.get("mode", session.get("mode", "")),
            "status": session.get("status", ""),
            "termination_reason": session.get("termination_reason", ""),
            "terminated_at": session.get("terminated_at"),
            "ended_by": session.get("ended_by", ""),
            "total_score": report.get("total_score", 0),
            "overall_score": report.get("overall_score", 0),
            "performance_label": report.get("performance_label", ""),
            "result_status": report.get("result_status", self._result_status(int(report.get("total_score", 0) or 0))),
            "total_questions": report.get("total_questions", 0),
            "timestamp": timestamp,
            "report": report,
        }

        if self.mode == "mongo":
            self._collection("InterviewFinalReports").update_one(
                {"session_id": session_id},
                {"$set": doc},
                upsert=True,
            )
            return

        existing_index = next(
            (index for index, item in enumerate(self._memory["InterviewFinalReports"]) if item["session_id"] == session_id),
            None,
        )
        if existing_index is None:
            self._memory["InterviewFinalReports"].append(doc)
        else:
            self._memory["InterviewFinalReports"][existing_index] = doc

    def list_final_reports(self, search: str = "", limit: int = 100, status: str = "") -> list[dict]:
        search_text = (search or "").strip().lower()
        status_text = (status or "").strip().upper()
        max_items = max(1, min(limit, 500))

        if self.mode == "mongo":
            query = {}
            if search_text:
                query = {
                    "$or": [
                        {"candidate_name": {"$regex": search_text, "$options": "i"}},
                        {"candidate_email": {"$regex": search_text, "$options": "i"}},
                    ]
                }
            docs = list(
                self._collection("InterviewFinalReports")
                .find(query, {"_id": 0, "report": 0})
                .sort("timestamp", -1)
                .limit(max_items)
            )
            normalized_docs = [self._normalize_final_report(doc) for doc in docs]
            if status_text in {"PASS", "FAIL"}:
                normalized_docs = [doc for doc in normalized_docs if (doc or {}).get("result_status") == status_text]
            return [doc for doc in normalized_docs if doc]

        rows = sorted(self._memory["InterviewFinalReports"], key=lambda item: item.get("timestamp", datetime.min), reverse=True)
        if search_text:
            rows = [
                row
                for row in rows
                if search_text in (row.get("candidate_name", "").lower()) or search_text in (row.get("candidate_email", "").lower())
            ]
        normalized_rows = [self._normalize_final_report({k: v for k, v in row.items() if k != "report"}) for row in rows]
        if status_text in {"PASS", "FAIL"}:
            normalized_rows = [row for row in normalized_rows if (row or {}).get("result_status") == status_text]
        return [row for row in normalized_rows[:max_items] if row]

    def get_final_report(self, session_id: str) -> dict | None:
        if self.mode == "mongo":
            record = self._collection("InterviewFinalReports").find_one({"session_id": session_id}, {"_id": 0})
            return self._normalize_final_report(record)

        for item in self._memory["InterviewFinalReports"]:
            if item["session_id"] == session_id:
                return self._normalize_final_report(item)
        return None

    def list_sessions(self, search: str = "", limit: int = 200) -> list[dict]:
        search_text = (search or "").strip().lower()
        max_items = max(1, min(limit, 1000))
        projection = {
            "_id": 0,
            "session_id": 1,
            "candidate_name": 1,
            "candidate_email": 1,
            "mode": 1,
            "status": 1,
            "current_index": 1,
            "termination_reason": 1,
            "terminated_at": 1,
            "ended_by": 1,
            "created_at": 1,
        }
        if self.mode == "mongo":
            query = {}
            if search_text:
                query = {
                    "$or": [
                        {"candidate_name": {"$regex": search_text, "$options": "i"}},
                        {"candidate_email": {"$regex": search_text, "$options": "i"}},
                        {"session_id": {"$regex": search_text, "$options": "i"}},
                    ]
                }
            return list(self._collection("InterviewSessions").find(query, projection).sort("created_at", -1).limit(max_items))

        rows = sorted(self._memory["InterviewSessions"], key=lambda item: item.get("created_at", datetime.min), reverse=True)
        if search_text:
            rows = [
                row
                for row in rows
                if search_text in (row.get("candidate_name", "").lower())
                or search_text in (row.get("candidate_email", "").lower())
                or search_text in (row.get("session_id", "").lower())
            ]
        return [
            deepcopy(
                {
                    "session_id": row.get("session_id", ""),
                    "user_id": row.get("user_id", ""),
                    "candidate_name": row.get("candidate_name", ""),
                    "candidate_email": row.get("candidate_email", ""),
                    "role": "user",
                    "mode": row.get("mode", ""),
                    "status": row.get("status", ""),
                    "current_index": row.get("current_index", 0),
                    "termination_reason": row.get("termination_reason", ""),
                    "terminated_at": row.get("terminated_at"),
                    "ended_by": row.get("ended_by", ""),
                    "created_at": row.get("created_at"),
                }
            )
            for row in rows[:max_items]
        ]

    def list_users(self, search: str = "", limit: int = 200) -> list[dict]:
        search_text = (search or "").strip().lower()
        max_items = max(1, min(limit, 1000))

        if self.mode == "mongo":
            query = {}
            if search_text:
                query = {
                    "$or": [
                        {"candidate_name": {"$regex": search_text, "$options": "i"}},
                        {"candidate_email": {"$regex": search_text, "$options": "i"}},
                        {"role": {"$regex": search_text, "$options": "i"}},
                    ]
                }
            docs = list(
                self._collection("Users")
                .find(query, {"_id": 0})
                .sort("created_at", -1)
                .limit(max_items)
            )
            return docs

        rows = sorted(self._memory["Users"], key=lambda item: item.get("created_at", datetime.min), reverse=True)
        if search_text:
            rows = [
                row
                for row in rows
                if search_text in (row.get("candidate_name", "").lower())
                or search_text in (row.get("candidate_email", "").lower())
                or search_text in (row.get("role", "user").lower())
            ]
        return [deepcopy(row) for row in rows[:max_items]]

    def admin_session_detail(self, session_id: str) -> dict | None:
        session = self.get_session(session_id)
        if not session:
            return None
        results = self._results_for_session(session_id)[:5]
        events = self.list_session_events(session_id, limit=300)
        report = self.get_final_report(session_id)
        return {
            "session": deepcopy(session),
            "answers": deepcopy(results),
            "events": deepcopy(events),
            "final_report": deepcopy(report) if report else None,
        }

    def delete_session_data(self, session_id: str) -> dict:
        session = self.get_session(session_id)
        if not session:
            return {"deleted": False, "reason": "session_not_found"}

        user_id = session.get("user_id", "")
        deleted_counts = {
            "sessions": 0,
            "results": 0,
            "reports": 0,
            "events": 0,
            "questions": 0,
            "company_questions": 0,
            "users": 0,
        }

        if self.mode == "mongo":
            deleted_counts["sessions"] = self._collection("InterviewSessions").delete_one({"session_id": session_id}).deleted_count
            deleted_counts["results"] = self._collection("InterviewResults").delete_many({"session_id": session_id}).deleted_count
            deleted_counts["reports"] = self._collection("InterviewFinalReports").delete_many({"session_id": session_id}).deleted_count
            deleted_counts["events"] = self._collection("InterviewEvents").delete_many({"session_id": session_id}).deleted_count
            deleted_counts["questions"] = self._collection("Questions").delete_many({"session_id": session_id}).deleted_count
            deleted_counts["company_questions"] = self._collection("CompanyQuestions").delete_many({"session_id": session_id}).deleted_count
            if user_id:
                deleted_counts["users"] = self._collection("Users").delete_many({"user_id": user_id}).deleted_count
        else:
            before_sessions = len(self._memory["InterviewSessions"])
            self._memory["InterviewSessions"] = [row for row in self._memory["InterviewSessions"] if row.get("session_id") != session_id]
            deleted_counts["sessions"] = before_sessions - len(self._memory["InterviewSessions"])

            before_results = len(self._memory["InterviewResults"])
            self._memory["InterviewResults"] = [row for row in self._memory["InterviewResults"] if row.get("session_id") != session_id]
            deleted_counts["results"] = before_results - len(self._memory["InterviewResults"])

            before_reports = len(self._memory["InterviewFinalReports"])
            self._memory["InterviewFinalReports"] = [row for row in self._memory["InterviewFinalReports"] if row.get("session_id") != session_id]
            deleted_counts["reports"] = before_reports - len(self._memory["InterviewFinalReports"])

            before_events = len(self._memory["InterviewEvents"])
            self._memory["InterviewEvents"] = [row for row in self._memory["InterviewEvents"] if row.get("session_id") != session_id]
            deleted_counts["events"] = before_events - len(self._memory["InterviewEvents"])

            before_questions = len(self._memory["Questions"])
            self._memory["Questions"] = [row for row in self._memory["Questions"] if row.get("session_id") != session_id]
            deleted_counts["questions"] = before_questions - len(self._memory["Questions"])

            before_company = len(self._memory["CompanyQuestions"])
            self._memory["CompanyQuestions"] = [row for row in self._memory["CompanyQuestions"] if row.get("session_id") != session_id]
            deleted_counts["company_questions"] = before_company - len(self._memory["CompanyQuestions"])

            if user_id:
                before_users = len(self._memory["Users"])
                self._memory["Users"] = [row for row in self._memory["Users"] if row.get("user_id") != user_id]
                deleted_counts["users"] = before_users - len(self._memory["Users"])

        return {
            "deleted": True,
            "session_id": session_id,
            "candidate_name": session.get("candidate_name", ""),
            "counts": deleted_counts,
        }

    def reset_interview_data(self) -> dict:
        counts = {
            "sessions": 0,
            "results": 0,
            "reports": 0,
            "events": 0,
            "questions": 0,
            "company_questions": 0,
            "users": 0,
        }
        if self.mode == "mongo":
            counts["sessions"] = self._collection("InterviewSessions").delete_many({}).deleted_count
            counts["results"] = self._collection("InterviewResults").delete_many({}).deleted_count
            counts["reports"] = self._collection("InterviewFinalReports").delete_many({}).deleted_count
            counts["events"] = self._collection("InterviewEvents").delete_many({}).deleted_count
            counts["questions"] = self._collection("Questions").delete_many({}).deleted_count
            counts["company_questions"] = self._collection("CompanyQuestions").delete_many({}).deleted_count
            counts["users"] = self._collection("Users").delete_many({"role": {"$ne": "admin"}}).deleted_count
        else:
            counts["sessions"] = len(self._memory["InterviewSessions"])
            counts["results"] = len(self._memory["InterviewResults"])
            counts["reports"] = len(self._memory["InterviewFinalReports"])
            counts["events"] = len(self._memory["InterviewEvents"])
            counts["questions"] = len(self._memory["Questions"])
            counts["company_questions"] = len(self._memory["CompanyQuestions"])
            counts["users"] = len([row for row in self._memory["Users"] if row.get("role") != "admin"])
            self._memory["InterviewSessions"] = []
            self._memory["InterviewResults"] = []
            self._memory["InterviewFinalReports"] = []
            self._memory["InterviewEvents"] = []
            self._memory["Questions"] = []
            self._memory["CompanyQuestions"] = []
            self._memory["Users"] = [row for row in self._memory["Users"] if row.get("role") == "admin"]
        return {"reset": True, "counts": counts}

    def event_diagnostics(self) -> dict:
        if self.mode == "mongo":
            events = list(self._collection("InterviewEvents").find({}, {"_id": 0, "type": 1, "level": 1, "payload": 1}))
        else:
            events = deepcopy(self._memory["InterviewEvents"])

        total = len(events)
        counts_by_type: dict[str, int] = {}
        counts_by_level: dict[str, int] = {}
        render_latencies: list[float] = []
        stt_latencies: list[float] = []
        for event in events:
            et = event.get("type", "unknown")
            lv = event.get("level", "info")
            counts_by_type[et] = counts_by_type.get(et, 0) + 1
            counts_by_level[lv] = counts_by_level.get(lv, 0) + 1
            payload = event.get("payload") or {}
            if isinstance(payload, dict):
                if "render_ms" in payload:
                    try:
                        render_latencies.append(float(payload["render_ms"]))
                    except Exception:
                        pass
                if "stt_ms" in payload:
                    try:
                        stt_latencies.append(float(payload["stt_ms"]))
                    except Exception:
                        pass

        def avg(items: list[float]) -> float:
            return round(sum(items) / len(items), 2) if items else 0.0

        return {
            "total_events": total,
            "counts_by_type": counts_by_type,
            "counts_by_level": counts_by_level,
            "render_avg_ms": avg(render_latencies),
            "stt_avg_ms": avg(stt_latencies),
            "render_samples": len(render_latencies),
            "stt_samples": len(stt_latencies),
        }

    def admin_reports(self) -> dict:
        sessions = self.list_sessions(limit=1000)
        users = self.list_users(limit=1000)
        final_reports = self.list_final_reports(limit=1000)
        total_interviews = len(sessions)
        total_users = len([row for row in users if (row.get("role") or "user") == "user"])
        completed_interviews = len([row for row in sessions if row.get("status") == "completed"])
        pending_interviews = len([row for row in sessions if row.get("status") == "in_progress"])
        active_sessions = pending_interviews

        communication_scores: list[float] = []
        confidence_scores: list[float] = []
        technical_scores: list[float] = []
        overall_scores: list[float] = []
        weakness_counts: dict[str, int] = {}
        alert_counts: dict[str, int] = {}

        for report in final_reports:
            scores = report.get("scores") or {}
            for key, bucket in (
                ("communication", communication_scores),
                ("confidence", confidence_scores),
                ("technical", technical_scores),
            ):
                value = scores.get(key)
                if isinstance(value, (int, float)):
                    bucket.append(float(value))
            overall = report.get("overall_score")
            if isinstance(overall, (int, float)):
                overall_scores.append(float(overall))
            for weakness in report.get("weaknesses") or []:
                clean = (weakness or "").strip()
                if clean:
                    weakness_counts[clean] = weakness_counts.get(clean, 0) + 1
            for alert in report.get("alerts") or []:
                clean_alert = (alert or "").strip()
                if clean_alert:
                    alert_counts[clean_alert] = alert_counts.get(clean_alert, 0) + 1

        def avg(items: list[float]) -> float:
            return round(sum(items) / len(items), 2) if items else 0.0

        top_candidates = sorted(
            [
                {
                    "candidate_name": item.get("candidate_name", ""),
                    "candidate_email": item.get("candidate_email", ""),
                    "session_id": item.get("session_id", ""),
                    "overall_score": item.get("overall_score", 0),
                    "timestamp": item.get("timestamp"),
                }
                for item in final_reports
            ],
            key=lambda row: row.get("overall_score", 0),
            reverse=True,
        )[:5]

        weak_areas = [
            {"label": key, "count": value}
            for key, value in sorted(weakness_counts.items(), key=lambda item: item[1], reverse=True)[:8]
        ]

        return {
            "total_users": total_users,
            "total_interviews": total_interviews,
            "completed_interviews": completed_interviews,
            "pending_interviews": pending_interviews,
            "active_sessions": active_sessions,
            "average_scores": {
                "communication": avg(communication_scores),
                "confidence": avg(confidence_scores),
                "technical": avg(technical_scores),
                "overall": avg(overall_scores),
            },
            "top_candidates": top_candidates,
            "weak_areas": weak_areas,
            "alert_summary": [
                {"label": key, "count": value}
                for key, value in sorted(alert_counts.items(), key=lambda item: item[1], reverse=True)[:8]
            ],
            "recent_results": final_reports[:10],
        }

    def _results_for_session(self, session_id: str) -> list[dict]:
        if self.mode == "mongo":
            return list(self._collection("InterviewResults").find({"session_id": session_id}, {"_id": 0}))
        return [item for item in self._memory["InterviewResults"] if item["session_id"] == session_id]

    def build_report(self, session_id: str, summary_builder: Callable[[list[dict]], dict]):
        session = self.get_session(session_id)
        if not session:
            return None
        results = self._results_for_session(session_id)[:5]
        if not results:
            return None

        total_questions = len(results)
        total_score = max(0, min(sum(int(item.get("score", 0)) for item in results), total_questions * 10))
        overall_score = round((total_score / max(1, total_questions * 10)) * 100)
        performance_label = self._performance_label(total_score)
        summary = summary_builder(results)
        question_scores = [
            {
                "question_id": item.get("question_id", ""),
                "question_number": index,
                "score": int(item.get("score", 0)),
                "max_score": 10,
            }
            for index, item in enumerate(results, start=1)
        ]
        return {
            "session_id": session_id,
            "candidate_name": session["candidate_name"],
            "candidate_email": session.get("candidate_email", ""),
            "mode": session["mode"],
            "status": session.get("status", ""),
            "termination_reason": session.get("termination_reason", ""),
            "terminated_at": session.get("terminated_at"),
            "ended_by": session.get("ended_by", ""),
            "total_questions": total_questions,
            "total_score": total_score,
            "overall_score": overall_score,
            "performance_label": performance_label,
            "result_status": self._result_status(total_score),
            "question_scores": question_scores,
            "strengths": summary["strengths"],
            "weaknesses": summary["weaknesses"],
            "improvement_suggestions": summary["improvement_suggestions"],
            "items": [
                {
                    "question_id": item.get("question_id", ""),
                    "question_number": index,
                    "question": item["question"],
                    "answer": item["user_answer"],
                    "score": int(item.get("score", 0)),
                    "max_score": 10,
                    "feedback": item["feedback"],
                    "improvement_suggestion": item["improvement_suggestion"],
                    "matched_keywords": item.get("matched_keywords", []),
                    "missing_keywords": item.get("missing_keywords", []),
                }
                for index, item in enumerate(results, start=1)
            ],
            "generated_at": datetime.utcnow(),
        }


db_manager = DatabaseManager()
