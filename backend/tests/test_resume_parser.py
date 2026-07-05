import pytest

from app.services.resume_parser import (
    ResumeParseError,
    extract_contact_info,
    extract_education,
    extract_experience_years,
    extract_skills,
    extract_text_from_pdf,
    parse_resume_pdf,
    parse_resume_text,
)
from tests.pdf_helpers import make_pdf_bytes

SAMPLE_RESUME_TEXT = """Asha Kumar
asha.kumar@example.com
+91 98765 43210

Summary
Backend engineer with 4 years of experience building distributed systems.

Skills
Python, FastAPI, PostgreSQL, Docker, AWS, React

Education
B.Tech in Computer Science, Central University of Andhra Pradesh
"""


def test_extract_text_from_pdf_returns_readable_text():
    pdf_bytes = make_pdf_bytes(SAMPLE_RESUME_TEXT)
    text = extract_text_from_pdf(pdf_bytes)
    assert "Asha Kumar" in text
    assert "Python" in text


def test_extract_text_from_pdf_rejects_empty_bytes():
    with pytest.raises(ResumeParseError):
        extract_text_from_pdf(b"")


def test_extract_text_from_pdf_rejects_garbage_bytes():
    with pytest.raises(ResumeParseError):
        extract_text_from_pdf(b"this is not a pdf at all, just text bytes")


def test_extract_skills_finds_known_vocabulary():
    skills = extract_skills(SAMPLE_RESUME_TEXT)
    assert "python" in skills
    assert "fastapi" in skills
    assert "postgresql" in skills
    assert "docker" in skills
    assert "aws" in skills
    assert "react" in skills


def test_extract_skills_does_not_false_positive_on_substrings():
    # "java" must not match inside "javascript" incorrectly counted twice,
    # and unrelated words shouldn't trigger skill matches.
    text = "I write javascript for a living."
    skills = extract_skills(text)
    assert "javascript" in skills
    assert "java" not in skills  # word-boundary match prevents "java" matching inside "javascript"


def test_extract_experience_years_various_phrasings():
    assert extract_experience_years("4 years of experience in backend development") == 4.0
    assert extract_experience_years("Experience: 6 years") == 6.0
    assert extract_experience_years("2.5+ years experience") == 2.5
    assert extract_experience_years("no mention of tenure here") is None


def test_extract_education_finds_degree_lines():
    education = extract_education(SAMPLE_RESUME_TEXT)
    assert len(education) >= 1
    assert any("B.Tech" in e["raw_line"] for e in education)


def test_extract_contact_info():
    email, phone = extract_contact_info(SAMPLE_RESUME_TEXT)
    assert email == "asha.kumar@example.com"
    assert phone is not None


def test_parse_resume_text_end_to_end():
    parsed = parse_resume_text(SAMPLE_RESUME_TEXT)
    assert parsed.email == "asha.kumar@example.com"
    assert "python" in parsed.skills
    assert parsed.experience_years == 4.0
    assert len(parsed.education) >= 1


def test_parse_resume_pdf_end_to_end():
    pdf_bytes = make_pdf_bytes(SAMPLE_RESUME_TEXT)
    parsed = parse_resume_pdf(pdf_bytes)
    assert "python" in parsed.skills
    assert parsed.email == "asha.kumar@example.com"


def test_parse_resume_pdf_with_no_extractable_text_raises():
    pdf_bytes = make_pdf_bytes("")
    with pytest.raises(ResumeParseError):
        parse_resume_pdf(pdf_bytes)
