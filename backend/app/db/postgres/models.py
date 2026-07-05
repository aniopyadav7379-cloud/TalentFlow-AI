"""
ORM models for TalentFlow AI.

Design notes:
- Primary keys are string UUIDs (not Postgres-native UUID type) so the same
  models work against SQLite in tests without a dialect-specific column type.
- JSON columns hold semi-structured AI output (skills lists, bias flags,
  score breakdowns) that doesn't need to be queried relationally.
- `embedding_id` fields store the Qdrant point ID, not the vector itself —
  vectors live in Qdrant; Postgres stores the pointer + relational metadata.
"""
import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.postgres.session import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    """Naive UTC datetime for storage in a plain DateTime column (no utcnow() deprecation warning)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class JobStatus(str, enum.Enum):
    DRAFT = "draft"
    OPEN = "open"
    CLOSED = "closed"
    ARCHIVED = "archived"


class ApplicationStatus(str, enum.Enum):
    SUBMITTED = "submitted"
    SHORTLISTED = "shortlisted"
    INTERVIEWING = "interviewing"
    OFFERED = "offered"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


class InterviewStatus(str, enum.Enum):
    PENDING = "pending"  # questions generated, not yet scheduled with a date/interviewer
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    RECRUITER = "recruiter"
    INTERVIEWER = "interviewer"


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.RECRUITER, nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    jobs: Mapped[list["Job"]] = relationship(back_populates="created_by", cascade="all, delete-orphan")


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    department: Mapped[str | None] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, nullable=False)
    requirements: Mapped[str | None] = mapped_column(Text)
    skills: Mapped[list] = mapped_column(JSON, default=list)  # list[str]
    experience_level: Mapped[str | None] = mapped_column(String(100))
    salary_min: Mapped[int | None] = mapped_column(Integer)
    salary_max: Mapped[int | None] = mapped_column(Integer)
    location: Mapped[str | None] = mapped_column(String(255))
    employment_type: Mapped[str | None] = mapped_column(String(50))
    status: Mapped[JobStatus] = mapped_column(Enum(JobStatus), default=JobStatus.DRAFT, nullable=False)

    # Qdrant point ID for this job's embedded description — used for
    # candidate<->job semantic matching.
    embedding_id: Mapped[str | None] = mapped_column(String(64))

    created_by_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    created_by: Mapped["User"] = relationship(back_populates="jobs")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)

    applications: Mapped[list["Application"]] = relationship(back_populates="job", cascade="all, delete-orphan")


class Candidate(Base):
    __tablename__ = "candidates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    phone: Mapped[str | None] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    resumes: Mapped[list["Resume"]] = relationship(back_populates="candidate", cascade="all, delete-orphan")
    applications: Mapped[list["Application"]] = relationship(back_populates="candidate", cascade="all, delete-orphan")


class Resume(Base):
    __tablename__ = "resumes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    candidate_id: Mapped[str] = mapped_column(String(36), ForeignKey("candidates.id"), nullable=False)
    candidate: Mapped["Candidate"] = relationship(back_populates="resumes")

    file_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    raw_text: Mapped[str | None] = mapped_column(Text)
    parsed_skills: Mapped[list] = mapped_column(JSON, default=list)
    parsed_experience_years: Mapped[float | None] = mapped_column(Float)
    parsed_education: Mapped[list] = mapped_column(JSON, default=list)

    # Pointer into Qdrant's "resumes" collection, not the vector itself.
    embedding_id: Mapped[str | None] = mapped_column(String(64))
    parse_status: Mapped[str] = mapped_column(String(30), default="pending")  # pending|parsed|failed

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class Application(Base):
    """A candidate applying (or being matched) to a specific job."""
    __tablename__ = "applications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    job_id: Mapped[str] = mapped_column(String(36), ForeignKey("jobs.id"), nullable=False)
    candidate_id: Mapped[str] = mapped_column(String(36), ForeignKey("candidates.id"), nullable=False)
    resume_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("resumes.id"))

    status: Mapped[ApplicationStatus] = mapped_column(Enum(ApplicationStatus), default=ApplicationStatus.SUBMITTED)
    match_score: Mapped[float | None] = mapped_column(Float)  # 0-100, from candidate_matching_agent
    match_rationale: Mapped[str | None] = mapped_column(Text)
    ai_summary: Mapped[str | None] = mapped_column(Text)

    job: Mapped["Job"] = relationship(back_populates="applications")
    candidate: Mapped["Candidate"] = relationship(back_populates="applications")
    interviews: Mapped[list["Interview"]] = relationship(back_populates="application", cascade="all, delete-orphan")
    evaluation: Mapped["Evaluation"] = relationship(back_populates="application", uselist=False, cascade="all, delete-orphan")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)


class Interview(Base):
    __tablename__ = "interviews"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    application_id: Mapped[str] = mapped_column(String(36), ForeignKey("applications.id"), nullable=False)
    application: Mapped["Application"] = relationship(back_populates="interviews")

    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime)
    interviewer_name: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[InterviewStatus] = mapped_column(Enum(InterviewStatus), default=InterviewStatus.PENDING)

    # AI-generated, role-specific questions: list[{"id","question","category"}]
    questions: Mapped[list] = mapped_column(JSON, default=list)

    responses: Mapped[list["InterviewResponse"]] = relationship(back_populates="interview", cascade="all, delete-orphan")

    overall_score: Mapped[float | None] = mapped_column(Float)  # 0-100
    score_breakdown: Mapped[dict] = mapped_column(JSON, default=dict)  # {technical, communication, ...}
    ai_recommendation: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class InterviewResponse(Base):
    __tablename__ = "interview_responses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    interview_id: Mapped[str] = mapped_column(String(36), ForeignKey("interviews.id"), nullable=False)
    interview: Mapped["Interview"] = relationship(back_populates="responses")

    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str | None] = mapped_column(Text)
    score: Mapped[float | None] = mapped_column(Float)  # 0-10
    feedback: Mapped[str | None] = mapped_column(Text)


class Evaluation(Base):
    """Enkrypt AI guardrail output for a given application's AI-driven decisions."""
    __tablename__ = "evaluations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    application_id: Mapped[str] = mapped_column(String(36), ForeignKey("applications.id"), unique=True, nullable=False)
    application: Mapped["Application"] = relationship(back_populates="evaluation")

    fairness_score: Mapped[float | None] = mapped_column(Float)  # 0-1
    bias_flags: Mapped[list] = mapped_column(JSON, default=list)  # list[str]
    grounding_score: Mapped[float | None] = mapped_column(Float)  # 0-1, hallucination check
    passed_guardrails: Mapped[bool] = mapped_column(default=True)
    final_recommendation: Mapped[str | None] = mapped_column(Text)
    raw_report: Mapped[dict] = mapped_column(JSON, default=dict)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
