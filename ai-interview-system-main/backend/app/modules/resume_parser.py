from __future__ import annotations

from io import BytesIO
import re

from PyPDF2 import PdfReader


KNOWN_SKILLS = [
    "python",
    "java",
    "react",
    "spring boot",
    "flask",
    "fastapi",
    "machine learning",
    "deep learning",
    "sql",
    "mongodb",
    "docker",
    "aws",
    "azure",
    "javascript",
    "typescript",
]


class ResumeParser:
    def parse_resume(self, file_bytes: bytes, filename: str) -> dict:
        text = self._extract_text(file_bytes)
        lowered = text.lower()
        skills = [skill.title() for skill in KNOWN_SKILLS if skill in lowered]
        projects = self._extract_projects(text)
        technologies = self._extract_technologies(text)
        return {
            "filename": filename,
            "raw_text": text,
            "skills": skills[:12],
            "technologies": technologies[:12],
            "projects": projects[:5],
        }

    def _extract_text(self, file_bytes: bytes) -> str:
        reader = PdfReader(BytesIO(file_bytes))
        text_parts = []
        for page in reader.pages:
            text_parts.append(page.extract_text() or "")
        return "\n".join(text_parts).strip()

    def _extract_projects(self, text: str) -> list[str]:
        project_lines = []
        for line in text.splitlines():
            cleaned = line.strip(" -\t")
            if len(cleaned) < 12:
                continue
            if "project" in cleaned.lower() or cleaned.istitle():
                project_lines.append(cleaned)
        return project_lines[:5]

    def _extract_technologies(self, text: str) -> list[str]:
        candidates = re.findall(r"\b[A-Za-z][A-Za-z0-9.+#-]{1,20}\b", text)
        unique = []
        seen = set()
        for token in candidates:
            normalized = token.lower()
            if normalized in seen:
                continue
            if normalized in {"and", "with", "from", "using", "project", "experience"}:
                continue
            if len(token) <= 2:
                continue
            seen.add(normalized)
            unique.append(token)
        return unique[:20]


resume_parser = ResumeParser()
