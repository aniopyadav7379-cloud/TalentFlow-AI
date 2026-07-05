"""
Resume parsing: raw PDF -> plain text -> structured signal.

This module is deliberately rule-based and has zero LLM dependency, so it's
fast, free, and fully deterministic/testable. The `resume_analysis_agent`
(step 3) layers an LLM on top of this for nuanced extraction (seniority
inference, project relevance, etc.) — this module is the reliable baseline
it falls back to if the LLM call fails or is disabled.
"""
from __future__ import annotations

import io
import re
from dataclasses import dataclass, field

from pdfminer.high_level import extract_text
from pdfminer.pdfparser import PDFSyntaxError

# A deliberately broad, lowercase skill vocabulary. Matched as whole words/phrases
# against the resume text. Extend this list as new domains are onboarded — it's
# intentionally a flat list, not a taxonomy, to keep matching simple and fast.
SKILL_VOCABULARY: tuple[str, ...] = (
    "python", "java", "javascript", "typescript", "c++", "c#", "go", "rust", "ruby", "php", "kotlin", "swift",
    "react", "next.js", "vue", "angular", "node.js", "express", "django", "flask", "fastapi", "spring boot",
    "postgresql", "mysql", "mongodb", "redis", "elasticsearch", "qdrant", "pinecone",
    "aws", "gcp", "azure", "docker", "kubernetes", "terraform", "ci/cd", "jenkins", "github actions",
    "machine learning", "deep learning", "nlp", "computer vision", "pytorch", "tensorflow", "scikit-learn",
    "langchain", "langgraph", "rag", "llm", "openai", "huggingface",
    "sql", "graphql", "rest api", "microservices", "kafka", "rabbitmq", "grpc",
    "html", "css", "tailwind css", "figma", "agile", "scrum", "git",
    "data analysis", "pandas", "numpy", "spark", "airflow", "etl",
)

_EXPERIENCE_PATTERNS = (
    re.compile(r"(\d+(?:\.\d+)?)\+?\s*years?\s+(?:of\s+)?experience", re.IGNORECASE),
    re.compile(r"experience\s*:?\s*(\d+(?:\.\d+)?)\+?\s*years?", re.IGNORECASE),
)

_EDUCATION_KEYWORDS = (
    "bachelor", "b.tech", "b.sc", "bsc", "master", "m.tech", "m.sc", "msc", "phd", "ph.d",
    "university", "college", "institute of technology",
)

_EMAIL_PATTERN = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE_PATTERN = re.compile(r"\+?\d[\d\-.\t ()]{7,}\d")


class ResumeParseError(Exception):
    """Raised when a file cannot be parsed as a readable PDF."""


@dataclass
class ParsedResume:
    raw_text: str
    skills: list[str] = field(default_factory=list)
    experience_years: float | None = None
    education: list[dict] = field(default_factory=list)
    email: str | None = None
    phone: str | None = None


def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extract plain text from PDF bytes. Raises ResumeParseError on invalid/corrupt PDFs."""
    if not file_bytes:
        raise ResumeParseError("Empty file")
    try:
        text = extract_text(io.BytesIO(file_bytes))
    except (PDFSyntaxError, Exception) as exc:  # pdfminer raises assorted low-level errors on bad input
        raise ResumeParseError(f"Could not parse PDF: {exc}") from exc
    text = text.strip()
    if not text:
        raise ResumeParseError("PDF contained no extractable text (likely a scanned image without OCR)")
    return text


def extract_skills(text: str) -> list[str]:
    lowered = text.lower()
    found = []
    for skill in SKILL_VOCABULARY:
        # Word-boundary match; skills containing symbols (c++, ci/cd) use substring match instead.
        if re.search(r"[a-z]", skill) and skill.replace(" ", "").isalnum():
            pattern = r"\b" + re.escape(skill) + r"\b"
            if re.search(pattern, lowered):
                found.append(skill)
        elif skill in lowered:
            found.append(skill)
    return sorted(set(found))


def extract_experience_years(text: str) -> float | None:
    for pattern in _EXPERIENCE_PATTERNS:
        match = pattern.search(text)
        if match:
            return float(match.group(1))
    return None


def extract_education(text: str) -> list[dict]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    education = []
    for line in lines:
        lowered = line.lower()
        if any(keyword in lowered for keyword in _EDUCATION_KEYWORDS):
            education.append({"raw_line": line})
    return education


def extract_contact_info(text: str) -> tuple[str | None, str | None]:
    email_match = _EMAIL_PATTERN.search(text)
    phone_match = _PHONE_PATTERN.search(text)
    return (
        email_match.group(0) if email_match else None,
        phone_match.group(0) if phone_match else None,
    )


def parse_resume_text(text: str) -> ParsedResume:
    """Pure text -> structured info. Split from PDF extraction so it's testable without binary fixtures."""
    email, phone = extract_contact_info(text)
    return ParsedResume(
        raw_text=text,
        skills=extract_skills(text),
        experience_years=extract_experience_years(text),
        education=extract_education(text),
        email=email,
        phone=phone,
    )


def parse_resume_pdf(file_bytes: bytes) -> ParsedResume:
    """End-to-end: PDF bytes -> ParsedResume. Raises ResumeParseError on bad input."""
    text = extract_text_from_pdf(file_bytes)
    return parse_resume_text(text)
