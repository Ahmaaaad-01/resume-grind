"""Pydantic models for the FastAPI endpoints."""

from __future__ import annotations

from pydantic import BaseModel


# -- Job models ---------------------------------------------------------------

class ScoreBreakdown(BaseModel):
    title: int = 0
    yoe: int = 0
    location: int = 0
    company: int = 0
    recency: int = 0
    keywords: int = 0
    keyword_match_count: int = 0
    keyword_matched_skills: list[str] = []
    keyword_missing_skills: list[str] = []
    pass1_total: int = 0
    final_score: int = 0


class JobResponse(BaseModel):
    dedup_key: str
    title_raw: str
    company: str
    location: str
    url: str
    date_posted: str | None = None
    first_seen_run: str
    last_seen_run: str
    times_seen: int = 1
    pass1_score: float | None = None
    final_score: float | None = None
    status: str = "new"
    resume_path: str | None = None
    jd_source: str | None = None
    jd_word_count: int | None = None
    title_experimental: bool = False
    query_source: str | None = None
    score_breakdown: ScoreBreakdown | None = None
    source: str = "serpapi"
    resume_status: str = "not_processed"
    resume_status_label: str = "Not yet processed"


class JobListResponse(BaseModel):
    jobs: list[JobResponse]
    total: int
    date_groups: list[str]  # distinct run dates, newest first


# -- Pipeline run models ------------------------------------------------------

class GenerateResumesRequest(BaseModel):
    dedup_keys: list[str]


class EligibleJob(BaseModel):
    dedup_key: str
    title_raw: str
    company: str
    location: str
    final_score: float | None = None


class EligibleJobsResponse(BaseModel):
    jobs: list[EligibleJob]
    total: int
    threshold: int


class PipelineEvent(BaseModel):
    """SSE event sent during pipeline execution."""
    stage: str  # discovery, filtering, scoring, awaiting_approval, tailoring, docx, done, error
    message: str
    progress: float = 0.0  # 0.0 to 1.0
    data: dict | None = None  # optional payload (e.g., newly discovered job keys)


class ThresholdsResponse(BaseModel):
    generate_resume: int
    include_in_digest: int


# -- Manual job models -------------------------------------------------------

class ManualJobRequest(BaseModel):
    jd_text: str
    url: str | None = None
    company: str | None = None
    title: str | None = None


class ManualJobResponse(BaseModel):
    dedup_key: str
    title_raw: str
    company: str
    url: str
    jd_word_count: int | None = None
    created_at: str | None = None
    resume_status: str = "not_processed"
    resume_status_label: str = "Not yet processed"
    resume_path: str | None = None
    source: str = "manual"


class ManualJobListResponse(BaseModel):
    jobs: list[ManualJobResponse]
    total: int


# -- Auth models ------------------------------------------------------------

class GoogleAuthRequest(BaseModel):
    """Frontend sends the Google ID token after sign-in."""
    token: str


class AuthResponse(BaseModel):
    """Returned after successful Google sign-in."""
    jwt: str
    user: "UserResponse"


class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    picture: str | None = None


# -- Settings models --------------------------------------------------------

class UpdateKeysRequest(BaseModel):
    """Update one or more API keys. Only non-null fields are updated."""
    serpapi_key: str | None = None
    anthropic_api_key: str | None = None
    gemini_api_key: str | None = None
    tailoring_provider: str | None = None  # "claude" or "gemini"


class SettingsStatusResponse(BaseModel):
    """Boolean flags for which keys / data are configured."""
    has_serpapi_key: bool = False
    has_anthropic_key: bool = False
    has_gemini_key: bool = False
    has_resume_bank: bool = False
    tailoring_provider: str = "gemini"


class ResumeBankUploadRequest(BaseModel):
    """Upload resume bank as JSON."""
    resume_bank: dict


class ClientConfigResponse(BaseModel):
    """Public config sent to the frontend (no secrets)."""
    google_client_id: str
