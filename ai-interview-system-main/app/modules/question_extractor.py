from __future__ import annotations

from io import BytesIO
import csv
import re
from uuid import uuid4

import pandas as pd
import pdfplumber


class QuestionExtractor:
    def extract_company_questions(self, content: bytes, filename: str, evaluation_mode: str) -> list[dict]:
        extension = filename.lower().rsplit(".", 1)[-1]
        if extension == "pdf":
            text = self._read_pdf(content)
            return self._parse_text_questions(text, evaluation_mode)
        if extension in {"txt", "csv"}:
            text = content.decode("utf-8", errors="ignore")
            if extension == "csv":
                return self._parse_csv(text, evaluation_mode)
            return self._parse_text_questions(text, evaluation_mode)
        if extension in {"xlsx", "xls"}:
            return self._parse_excel(content, evaluation_mode)
        raise ValueError("Unsupported file format. Use PDF, Excel, CSV, or TXT.")

    def _read_pdf(self, content: bytes) -> str:
        with pdfplumber.open(BytesIO(content)) as pdf:
            return "\n".join((page.extract_text() or "") for page in pdf.pages)

    def _parse_csv(self, text: str, evaluation_mode: str) -> list[dict]:
        rows = list(csv.DictReader(text.splitlines()))
        questions = []
        for row in rows:
            question_text = row.get("question") or row.get("Question") or ""
            keywords = row.get("keywords") or row.get("Keywords") or ""
            questions.append(
                {
                    "id": uuid4().hex,
                    "question": question_text.strip(),
                    "expected_keywords": self._split_keywords(keywords) if evaluation_mode == "keyword" else [],
                    "source": "company-upload",
                }
            )
        return [item for item in questions if item["question"]][:5]

    def _parse_excel(self, content: bytes, evaluation_mode: str) -> list[dict]:
        dataframe = pd.read_excel(BytesIO(content))
        questions = []
        for _, row in dataframe.fillna("").iterrows():
            question_text = row.get("question") or row.get("Question") or ""
            keywords = row.get("keywords") or row.get("Keywords") or ""
            questions.append(
                {
                    "id": uuid4().hex,
                    "question": str(question_text).strip(),
                    "expected_keywords": self._split_keywords(str(keywords)) if evaluation_mode == "keyword" else [],
                    "source": "company-upload",
                }
            )
        return [item for item in questions if item["question"]][:5]

    def _parse_text_questions(self, text: str, evaluation_mode: str) -> list[dict]:
        if evaluation_mode == "keyword":
            return self._parse_keyword_blocks(text)

        questions = []
        for line in text.splitlines():
            cleaned = self._normalize_question_line(line)
            if self._looks_like_question(cleaned):
                questions.append(
                    {
                        "id": uuid4().hex,
                        "question": cleaned,
                        "expected_keywords": [],
                        "source": "company-upload",
                    }
                )
        return questions[:5]

    def _parse_keyword_blocks(self, text: str) -> list[dict]:
        blocks = re.split(r"\n\s*\n", text)
        questions = []
        for block in blocks:
            question_match = re.search(r"Question\s*:\s*(.+)", block, re.IGNORECASE)
            keywords_match = re.search(r"Keywords?\s*:\s*(.+)", block, re.IGNORECASE | re.DOTALL)
            if not question_match:
                continue
            keywords_text = keywords_match.group(1) if keywords_match else ""
            questions.append(
                {
                    "id": uuid4().hex,
                    "question": self._normalize_question_line(question_match.group(1)),
                    "expected_keywords": self._split_keywords(keywords_text),
                    "source": "company-upload",
                }
            )
        if questions:
            return questions[:5]
        return self._parse_inline_keyword_pairs(text)

    def _split_keywords(self, raw: str) -> list[str]:
        parts = re.split(r"[\n,;]+", raw)
        cleaned = []
        for part in parts:
            item = re.sub(r"^[\-\d.)\s]+", "", part.strip())
            if item:
                cleaned.append(item)
        return cleaned

    def _parse_inline_keyword_pairs(self, text: str) -> list[dict]:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        questions = []
        pending_question = None
        pending_keywords = []

        for line in lines:
            normalized = self._normalize_question_line(line)
            if re.match(r"^question\s*:", line, re.IGNORECASE):
                if pending_question:
                    questions.append(
                        {
                            "id": uuid4().hex,
                            "question": pending_question,
                            "expected_keywords": pending_keywords,
                            "source": "company-upload",
                        }
                    )
                pending_question = self._normalize_question_line(re.sub(r"^question\s*:\s*", "", line, flags=re.IGNORECASE))
                pending_keywords = []
                continue

            if re.match(r"^keywords?\s*:", line, re.IGNORECASE):
                keyword_text = re.sub(r"^keywords?\s*:\s*", "", line, flags=re.IGNORECASE)
                pending_keywords.extend(self._split_keywords(keyword_text))
                continue

            if pending_question and not self._looks_like_question(normalized):
                pending_keywords.extend(self._split_keywords(line))
                continue

            if self._looks_like_question(normalized):
                if pending_question:
                    questions.append(
                        {
                            "id": uuid4().hex,
                            "question": pending_question,
                            "expected_keywords": pending_keywords,
                            "source": "company-upload",
                        }
                    )
                pending_question = normalized
                pending_keywords = []

        if pending_question:
            questions.append(
                {
                    "id": uuid4().hex,
                    "question": pending_question,
                    "expected_keywords": pending_keywords,
                    "source": "company-upload",
                }
            )
        return questions[:5]

    def _normalize_question_line(self, line: str) -> str:
        cleaned = line.strip()
        cleaned = re.sub(r"^[\-\d.)\s]+", "", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned)
        return cleaned

    def _looks_like_question(self, line: str) -> bool:
        lowered = line.lower()
        if len(line) < 12:
            return False
        if lowered.startswith("question:"):
            return True
        if line.endswith("?"):
            return True
        starters = (
            "explain ",
            "describe ",
            "what ",
            "how ",
            "why ",
            "tell ",
            "define ",
            "differentiate ",
            "compare ",
            "write ",
            "implement ",
        )
        return lowered.startswith(starters)


question_extractor = QuestionExtractor()
