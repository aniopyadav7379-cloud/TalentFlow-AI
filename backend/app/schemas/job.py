from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.db.postgres.models import JobStatus


class JobBase(BaseModel):
    title: str = Field(..., min_length=2, max_length=255)
    department: str | None = None
    description: str = Field(..., min_length=10)
    requirements: str | None = None
    skills: list[str] = Field(default_factory=list)
    experience_level: str | None = None
    salary_min: int | None = Field(default=None, ge=0)
    salary_max: int | None = Field(default=None, ge=0)
    location: str | None = None
    employment_type: str | None = None


class JobCreate(JobBase):
    pass


class JobUpdate(BaseModel):
    title: str | None = None
    department: str | None = None
    description: str | None = None
    requirements: str | None = None
    skills: list[str] | None = None
    experience_level: str | None = None
    salary_min: int | None = None
    salary_max: int | None = None
    location: str | None = None
    employment_type: str | None = None
    status: JobStatus | None = None


class JobOut(JobBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    status: JobStatus
    created_by_id: str
    created_at: datetime
    updated_at: datetime
