"""FastAPI backend for the PM Job Pipeline UI.

Run locally:
    py -m uvicorn src.api:app --reload --port 8000

In cloud mode (CLOUD_MODE=1), auth is required on all endpoints and
each user's API keys / resume bank come from the database.
"""

from __future__ import annotations

import ast
import asyncio
import io
import json
import logging
import os
import threading
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path

import mammoth
from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from sse_starlette.sse import EventSourceResponse

from src.api_models import (
    AuthResponse,
    ClientConfigResponse,
    EligibleJob,
    EligibleJobsResponse,
    GenerateResumesRequest,
    GoogleAuthRequest,
    JobListResponse,
    JobResponse,
    ManualJobListResponse,
    ManualJobRequest,
    ManualJobResponse,
    PipelineEvent,
    ResumeBankUploadRequest,
    ScoreBreakdown,
    SettingsStatusResponse,
    ThresholdsResponse,
    UpdateKeysRequest,
    UserResponse,
)
from src.config import CLOUD_MODE, PROJECT_ROOT, load_config, ensure_directories
from src.db import (
    get_connection, init_db, get_existing_job, update_job,
    insert_manual_job, delete_job,
    find_user_by_google_id, find_user_by_id, create_user,
    get_user_settings, upsert_user_settings,
    store_resume_file, get_resume_file, delete_resume_file,
)

log = logging.getLogger(__name__)

app = FastAPI(title="PM Job Pipeline", version="2.0.0")

# CORS — allow Vite dev server + Railway domain
_allowed_origins = [
    "http://localhost:5173",
    "http://localhost:8000",
]
_railway_url = os.environ.get("RAILWAY_PUBLIC_DOMAIN")
if _railway_url:
    _allowed_origins.append(f"https://{_railway_url}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Simple lock to prevent concurrent pipeline runs
_pipeline_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

def _get_current_user_or_none(request: Request) -> dict | None:
    """Return user dict if a valid JWT is present, else None.

    In CLOUD_MODE, this is always required (use get_current_user instead).
    In local mode, returns None so endpoints work without auth.
    """
    from src.auth import decode_jwt

    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None
    try:
        payload = decode_jwt(auth_header[7:])
        return {"user_id": payload["sub"], "email": payload["email"]}
    except Exception:
        return None


def get_current_user(request: Request) -> dict:
    """FastAPI dependency — require a valid JWT.

    In CLOUD_MODE, all protected endpoints use this.
    In local mode, returns a synthetic local user so the app works without auth.
    Accepts JWT from Authorization header OR ?token= query param (for iframes/downloads).
    """
    user = _get_current_user_or_none(request)
    if user:
        return user

    # Also check query param (for iframe/download URLs that can't send headers)
    from src.auth import decode_jwt
    token = request.query_params.get("token")
    if token:
        try:
            payload = decode_jwt(token)
            return {"user_id": payload["sub"], "email": payload["email"]}
        except Exception:
            pass

    if not CLOUD_MODE:
        return {"user_id": "local", "email": "local@localhost"}

    raise HTTPException(status_code=401, detail="Not authenticated")


def _get_user_api_key(conn, user_id: str, key_name: str) -> str | None:
    """Load and decrypt a user's API key from the database.

    key_name: one of 'serpapi_key_enc', 'anthropic_key_enc', 'gemini_key_enc'
    """
    from src.encryption import decrypt

    settings = get_user_settings(conn, user_id)
    if not settings:
        return None
    enc_value = settings[key_name]
    if not enc_value:
        return None
    return decrypt(enc_value)


def _get_user_resume_bank(conn, user_id: str) -> dict | None:
    """Load a user's resume bank from the database."""
    settings = get_user_settings(conn, user_id)
    if not settings or not settings["resume_bank_json"]:
        return None
    return json.loads(settings["resume_bank_json"])


def _load_resume_bank_for_user(conn, user_id: str) -> dict:
    """Load resume bank — from DB in cloud mode, from filesystem locally."""
    if CLOUD_MODE or user_id != "local":
        bank = _get_user_resume_bank(conn, user_id)
        if not bank:
            raise HTTPException(400, "Resume bank not configured. Upload it in Settings.")
        return bank
    # Local mode fallback
    from src.resume_bank import load_resume_bank
    return load_resume_bank()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_config():
    return load_config(skip_validation=CLOUD_MODE)


def _parse_score_breakdown(raw: str | None, config: dict | None = None) -> ScoreBreakdown | None:
    """Try to parse the score_breakdown string stored in DB."""
    if not raw:
        return None
    try:
        data = ast.literal_eval(raw)
        if not isinstance(data, dict):
            return None
        core_skills = []
        if config:
            core_skills = config.get("scoring", {}).get("core_skills", [])
        matched = data.get("keyword_matched_skills", [])
        missing = [s for s in core_skills if s not in matched] if core_skills else []
        return ScoreBreakdown(
            title=data.get("title", 0),
            yoe=data.get("yoe", 0),
            location=data.get("location", 0),
            company=data.get("company", 0),
            recency=data.get("recency", 0),
            keywords=data.get("keywords", 0),
            keyword_match_count=data.get("keyword_match_count", 0),
            keyword_matched_skills=matched,
            keyword_missing_skills=missing,
            pass1_total=data.get("pass1_total", 0),
            final_score=data.get("final_score", 0),
        )
    except Exception:
        return None


def _compute_resume_status(row: dict, threshold: int, user_id: str | None = None,
                           conn=None) -> tuple[str, str]:
    """Return (resume_status, resume_status_label) for a job row."""
    status = row["status"]
    resume_path = row["resume_path"]
    final_score = row["final_score"]
    jd_source = row["jd_source"]

    source = None
    try:
        source = row["source"]
    except (IndexError, KeyError):
        pass

    # Check if resume exists — BLOB in DB or file on disk
    has_resume = False
    if resume_path:
        if conn and user_id and user_id != "local":
            # Cloud mode: check resume_files table
            rf = get_resume_file(conn, user_id, row["dedup_key"])
            has_resume = rf is not None
        else:
            # Local mode: check filesystem
            has_resume = Path(resume_path).exists()

    if source == "manual":
        if has_resume:
            return "available", "Resume available"
        if resume_path:
            return "file_missing", "Resume file not found"
        return "not_processed", "Resume not yet generated"

    if resume_path:
        if has_resume:
            return "available", "Resume available"
        return "file_missing", "Resume file not found"

    if status == "new":
        return "not_processed", "Not yet processed"

    if status == "rejected":
        try:
            reason = row["reject_reason"] or "Rejected"
        except (IndexError, KeyError):
            reason = "Rejected"
        return "rejected", reason

    if jd_source == "skipped":
        return "no_jd", "JD too short to tailor"

    if final_score is not None and final_score < threshold:
        return "below_threshold", f"Score {int(final_score)} — below {threshold} threshold"

    if status == "scored" and final_score is not None and final_score >= threshold:
        return "pending_generation", "Eligible — resume not yet built"

    if status in ("expired", "skipped"):
        return "expired", f"Job {status}"

    return "not_processed", "Not yet processed"


def _row_to_job(row, config: dict, user_id: str | None = None,
                conn=None) -> JobResponse:
    """Convert a sqlite3.Row to a JobResponse."""
    threshold = config.get("scoring", {}).get("thresholds", {}).get("generate_resume", 60)
    r_status, r_label = _compute_resume_status(row, threshold, user_id=user_id, conn=conn)
    breakdown = _parse_score_breakdown(row["score_breakdown"], config)

    source = "serpapi"
    try:
        source = row["source"] or "serpapi"
    except (IndexError, KeyError):
        pass

    return JobResponse(
        dedup_key=row["dedup_key"],
        title_raw=row["title_raw"],
        company=row["company"],
        location=row["location"],
        url=row["url"],
        date_posted=row["date_posted"],
        first_seen_run=row["first_seen_run"],
        last_seen_run=row["last_seen_run"],
        times_seen=row["times_seen"],
        pass1_score=row["pass1_score"],
        final_score=row["final_score"],
        status=row["status"],
        resume_path=row["resume_path"],
        jd_source=row["jd_source"],
        jd_word_count=row["jd_word_count"],
        title_experimental=bool(row["title_experimental"]),
        query_source=row["query_source"],
        score_breakdown=breakdown,
        source=source,
        resume_status=r_status,
        resume_status_label=r_label,
    )


def _user_id_filter(user_id: str) -> str:
    """Return a SQL fragment to filter jobs by user_id.

    In local mode (user_id='local'), show jobs with NULL user_id (legacy)
    or user_id='local'.
    """
    if user_id == "local":
        return "(user_id IS NULL OR user_id = 'local')"
    return "user_id = ?"


def _user_id_params(user_id: str) -> tuple:
    """Return SQL params for the user_id filter."""
    if user_id == "local":
        return ()
    return (user_id,)


# ---------------------------------------------------------------------------
# Public endpoints (no auth required)
# ---------------------------------------------------------------------------

@app.get("/api/config/client", response_model=ClientConfigResponse)
def get_client_config():
    """Return public config for the frontend (Google Client ID, etc.)."""
    client_id = os.environ.get("GOOGLE_CLIENT_ID", "")
    return ClientConfigResponse(google_client_id=client_id)


# ---------------------------------------------------------------------------
# Auth endpoints
# ---------------------------------------------------------------------------

@app.post("/api/auth/google", response_model=AuthResponse)
def google_auth(request: GoogleAuthRequest):
    """Verify Google ID token, find-or-create user, return JWT."""
    from src.auth import verify_google_token, create_jwt, generate_user_id

    google_info = verify_google_token(request.token)

    conn = get_connection()
    init_db(conn)

    user_row = find_user_by_google_id(conn, google_info["google_id"])
    if user_row:
        user_id = user_row["id"]
    else:
        user_id = generate_user_id()
        create_user(
            conn, user_id,
            email=google_info["email"],
            name=google_info["name"],
            google_id=google_info["google_id"],
            picture=google_info.get("picture"),
        )

    conn.close()

    token = create_jwt(user_id, google_info["email"])
    return AuthResponse(
        jwt=token,
        user=UserResponse(
            id=user_id,
            email=google_info["email"],
            name=google_info["name"],
            picture=google_info.get("picture"),
        ),
    )


@app.get("/api/auth/me", response_model=UserResponse)
def get_me(user: dict = Depends(get_current_user)):
    """Return current user info from JWT."""
    conn = get_connection()
    init_db(conn)
    user_row = find_user_by_id(conn, user["user_id"])
    conn.close()

    if not user_row:
        raise HTTPException(404, "User not found")

    return UserResponse(
        id=user_row["id"],
        email=user_row["email"],
        name=user_row["name"],
        picture=user_row["picture"],
    )


# ---------------------------------------------------------------------------
# Settings endpoints
# ---------------------------------------------------------------------------

@app.get("/api/settings/status", response_model=SettingsStatusResponse)
def get_settings_status(user: dict = Depends(get_current_user)):
    """Check which keys and data are configured (boolean flags, not values)."""
    conn = get_connection()
    init_db(conn)
    settings = get_user_settings(conn, user["user_id"])
    conn.close()

    if not settings:
        return SettingsStatusResponse()

    return SettingsStatusResponse(
        has_serpapi_key=bool(settings["serpapi_key_enc"]),
        has_anthropic_key=bool(settings["anthropic_key_enc"]),
        has_gemini_key=bool(settings["gemini_key_enc"]),
        has_resume_bank=bool(settings["resume_bank_json"]),
        tailoring_provider=settings["tailoring_provider"] or "gemini",
    )


@app.put("/api/settings/keys")
def update_keys(request: UpdateKeysRequest, user: dict = Depends(get_current_user)):
    """Update one or more API keys (encrypted before storage)."""
    from src.encryption import encrypt

    fields = {}
    if request.serpapi_key is not None:
        fields["serpapi_key_enc"] = encrypt(request.serpapi_key) if request.serpapi_key else ""
    if request.anthropic_api_key is not None:
        fields["anthropic_key_enc"] = encrypt(request.anthropic_api_key) if request.anthropic_api_key else ""
    if request.gemini_api_key is not None:
        fields["gemini_key_enc"] = encrypt(request.gemini_api_key) if request.gemini_api_key else ""
    if request.tailoring_provider is not None:
        fields["tailoring_provider"] = request.tailoring_provider

    if not fields:
        return {"ok": True}

    conn = get_connection()
    init_db(conn)
    upsert_user_settings(conn, user["user_id"], **fields)
    conn.close()
    return {"ok": True}


@app.put("/api/settings/resume-bank")
def upload_resume_bank(request: ResumeBankUploadRequest, user: dict = Depends(get_current_user)):
    """Upload/update the user's resume bank JSON."""
    from src.resume_bank import validate_resume_bank

    bank = request.resume_bank
    errors = validate_resume_bank(bank)
    if errors:
        raise HTTPException(422, detail={"message": "Invalid resume bank", "errors": errors})

    conn = get_connection()
    init_db(conn)
    upsert_user_settings(conn, user["user_id"], resume_bank_json=json.dumps(bank))
    conn.close()
    return {"ok": True}


@app.get("/api/settings/resume-bank")
def get_resume_bank(user: dict = Depends(get_current_user)):
    """Download the user's current resume bank JSON."""
    conn = get_connection()
    init_db(conn)
    bank = _get_user_resume_bank(conn, user["user_id"])
    conn.close()
    if not bank:
        raise HTTPException(404, "No resume bank uploaded")
    return bank


# ---------------------------------------------------------------------------
# Job list endpoints
# ---------------------------------------------------------------------------

@app.get("/api/jobs", response_model=JobListResponse)
def list_jobs(
    days: int = Query(7, ge=1, le=30),
    include_expired: bool = Query(False),
    user: dict = Depends(get_current_user),
):
    """List jobs, optionally filtered by recency."""
    config = _get_config()
    conn = get_connection()
    init_db(conn)
    user_id = user["user_id"]

    cutoff = (date.today() - timedelta(days=days)).isoformat()
    uid_filter = _user_id_filter(user_id)
    uid_params = _user_id_params(user_id)

    if include_expired:
        rows = conn.execute(
            f"SELECT * FROM jobs WHERE last_seen_run >= ? AND (source IS NULL OR source != 'manual') "
            f"AND {uid_filter} "
            f"ORDER BY last_seen_run DESC, final_score DESC",
            (cutoff,) + uid_params,
        ).fetchall()
    else:
        rows = conn.execute(
            f"SELECT * FROM jobs WHERE last_seen_run >= ? AND status != 'expired' "
            f"AND (source IS NULL OR source != 'manual') "
            f"AND {uid_filter} "
            f"ORDER BY last_seen_run DESC, final_score DESC",
            (cutoff,) + uid_params,
        ).fetchall()

    jobs = [_row_to_job(r, config, user_id=user_id, conn=conn) for r in rows]
    date_groups = sorted({j.first_seen_run for j in jobs}, reverse=True)
    conn.close()

    return JobListResponse(jobs=jobs, total=len(jobs), date_groups=date_groups)


@app.get("/api/jobs/eligible", response_model=EligibleJobsResponse)
def list_eligible_jobs(user: dict = Depends(get_current_user)):
    """List jobs eligible for resume generation (scored >= threshold, no resume)."""
    config = _get_config()
    threshold = config["scoring"]["thresholds"]["generate_resume"]
    conn = get_connection()
    init_db(conn)
    user_id = user["user_id"]
    uid_filter = _user_id_filter(user_id)
    uid_params = _user_id_params(user_id)

    rows = conn.execute(
        f"""SELECT dedup_key, title_raw, company, location, final_score
           FROM jobs
           WHERE final_score >= ?
             AND (resume_path IS NULL OR resume_path = '')
             AND status NOT IN ('expired', 'skipped', 'applied')
             AND jd_source != 'skipped'
             AND (source IS NULL OR source != 'manual')
             AND {uid_filter}
           ORDER BY final_score DESC""",
        (threshold,) + uid_params,
    ).fetchall()
    conn.close()

    jobs = [
        EligibleJob(
            dedup_key=r["dedup_key"],
            title_raw=r["title_raw"],
            company=r["company"],
            location=r["location"],
            final_score=r["final_score"],
        )
        for r in rows
    ]
    return EligibleJobsResponse(jobs=jobs, total=len(jobs), threshold=threshold)


@app.get("/api/jobs/{dedup_key}", response_model=JobResponse)
def get_job(dedup_key: str, user: dict = Depends(get_current_user)):
    """Get a single job by dedup_key."""
    config = _get_config()
    conn = get_connection()
    init_db(conn)
    row = get_existing_job(conn, dedup_key)
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Job not found")
    # Verify ownership
    user_id = user["user_id"]
    row_uid = row["user_id"]
    if user_id != "local" and row_uid and row_uid != user_id:
        conn.close()
        raise HTTPException(status_code=404, detail="Job not found")
    result = _row_to_job(row, config, user_id=user_id, conn=conn)
    conn.close()
    return result


# ---------------------------------------------------------------------------
# Resume file endpoints
# ---------------------------------------------------------------------------

@app.get("/api/resumes/{dedup_key}/download")
def download_resume(dedup_key: str, user: dict = Depends(get_current_user)):
    """Serve the DOCX file for download — from DB BLOB or filesystem."""
    conn = get_connection()
    init_db(conn)
    user_id = user["user_id"]

    # Try BLOB storage first (cloud mode)
    if user_id != "local":
        rf = get_resume_file(conn, user_id, dedup_key)
        if rf:
            conn.close()
            return Response(
                content=bytes(rf["content"]),
                media_type=rf["content_type"],
                headers={"Content-Disposition": f'attachment; filename="{rf["filename"]}"'},
            )

    # Fallback: filesystem (local mode)
    row = get_existing_job(conn, dedup_key)
    conn.close()
    if not row or not row["resume_path"]:
        raise HTTPException(404, "No resume for this job")
    path = Path(row["resume_path"])
    if not path.exists():
        raise HTTPException(404, "Resume file not found on disk")
    return FileResponse(
        path=str(path),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=path.name,
    )


@app.get("/api/resumes/{dedup_key}/preview", response_class=HTMLResponse)
def preview_resume(dedup_key: str, user: dict = Depends(get_current_user)):
    """Convert DOCX to HTML for in-browser preview."""
    conn = get_connection()
    init_db(conn)
    user_id = user["user_id"]

    # Try BLOB storage first (cloud mode)
    if user_id != "local":
        rf = get_resume_file(conn, user_id, dedup_key)
        if rf:
            conn.close()
            result = mammoth.convert_to_html(io.BytesIO(bytes(rf["content"])))
            return HTMLResponse(content=result.value)

    # Fallback: filesystem (local mode)
    row = get_existing_job(conn, dedup_key)
    conn.close()
    if not row or not row["resume_path"]:
        raise HTTPException(404, "No resume for this job")
    path = Path(row["resume_path"])
    if not path.exists():
        raise HTTPException(404, "Resume file not found on disk")
    with open(path, "rb") as f:
        result = mammoth.convert_to_html(f)
    return HTMLResponse(content=result.value)


# ---------------------------------------------------------------------------
# Config endpoint
# ---------------------------------------------------------------------------

@app.get("/api/config/thresholds", response_model=ThresholdsResponse)
def get_thresholds():
    config = _get_config()
    t = config["scoring"]["thresholds"]
    return ThresholdsResponse(
        generate_resume=t["generate_resume"],
        include_in_digest=t["include_in_digest"],
    )


# ---------------------------------------------------------------------------
# Manual job endpoints
# ---------------------------------------------------------------------------

def _row_to_manual_job(row, user_id: str | None = None, conn=None) -> ManualJobResponse:
    """Convert a sqlite3.Row to a ManualJobResponse."""
    has_resume = False
    resume_path = row["resume_path"]
    if resume_path:
        if conn and user_id and user_id != "local":
            rf = get_resume_file(conn, user_id, row["dedup_key"])
            has_resume = rf is not None
        else:
            has_resume = Path(resume_path).exists()

    if has_resume:
        r_status, r_label = "available", "Resume available"
    elif resume_path:
        r_status, r_label = "file_missing", "Resume file not found"
    else:
        r_status, r_label = "not_processed", "Resume not yet generated"

    return ManualJobResponse(
        dedup_key=row["dedup_key"],
        title_raw=row["title_raw"],
        company=row["company"],
        url=row["url"],
        jd_word_count=row["jd_word_count"],
        created_at=row["created_at"],
        resume_status=r_status,
        resume_status_label=r_label,
        resume_path=row["resume_path"],
    )


@app.get("/api/manual-jobs", response_model=ManualJobListResponse)
def list_manual_jobs(user: dict = Depends(get_current_user)):
    """List all manually submitted jobs."""
    conn = get_connection()
    init_db(conn)
    user_id = user["user_id"]
    uid_filter = _user_id_filter(user_id)
    uid_params = _user_id_params(user_id)

    rows = conn.execute(
        f"SELECT * FROM jobs WHERE source = 'manual' AND {uid_filter} ORDER BY created_at DESC",
        uid_params,
    ).fetchall()
    jobs = [_row_to_manual_job(r, user_id=user_id, conn=conn) for r in rows]
    conn.close()
    return ManualJobListResponse(jobs=jobs, total=len(jobs))


@app.post("/api/manual-jobs", response_model=ManualJobResponse)
def submit_manual_job(request: ManualJobRequest, user: dict = Depends(get_current_user)):
    """Submit a manual job and generate a tailored resume."""
    from src.manual_inference import infer_company, infer_title
    from src.tailoring import tailor_resume
    from src.doc_generator import generate_docx

    jd_text = request.jd_text.strip()
    word_count = len(jd_text.split())
    if word_count < 50:
        raise HTTPException(422, f"JD too short ({word_count} words). Minimum 50 words required.")

    company = request.company.strip() if request.company else infer_company(jd_text)
    title = request.title.strip() if request.title else infer_title(jd_text)
    url = request.url.strip() if request.url else ""
    dedup_key = f"manual-{uuid.uuid4().hex[:12]}"
    run_date = date.today().isoformat()
    user_id = user["user_id"]

    config = _get_config()
    ensure_directories()

    conn = get_connection()
    init_db(conn)
    bank = _load_resume_bank_for_user(conn, user_id)

    # Get user's tailoring API key and provider
    tailoring_cfg = config.get("tailoring", {})
    provider = tailoring_cfg.get("provider", "gemini")
    api_key = None
    if user_id != "local":
        settings = get_user_settings(conn, user_id)
        if settings and settings["tailoring_provider"]:
            provider = settings["tailoring_provider"]
        if provider == "claude":
            api_key = _get_user_api_key(conn, user_id, "anthropic_key_enc")
        else:
            api_key = _get_user_api_key(conn, user_id, "gemini_key_enc")

    job_dict = {
        "title_raw": title,
        "company": company,
        "location": "Manual submission",
        "url": url,
        "date_posted": None,
        "description_snippet": "",
        "dedup_key": dedup_key,
        "source": "manual",
    }

    try:
        tailored = tailor_resume(job_dict, jd_text, bank, config,
                                 api_key=api_key, provider_override=provider)
    except Exception as e:
        conn.close()
        log.exception("Tailoring failed for manual job")
        raise HTTPException(500, f"Resume tailoring failed: {e}")

    if not tailored.get("experience"):
        errors = tailored.get("validation_errors", [])
        msg = f"Tailoring produced no content. Errors: {errors}" if errors else "Tailoring produced empty resume."
        conn.close()
        log.error(msg)
        raise HTTPException(500, msg)

    # Generate DOCX
    output_dir = PROJECT_ROOT / "data" / "resumes" / "manual"
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        docx_path = generate_docx(tailored, bank, job_dict, output_dir=output_dir)
    except Exception as e:
        conn.close()
        log.exception("DOCX generation failed for manual job")
        raise HTTPException(500, f"DOCX generation failed: {e}")

    # Store DOCX as BLOB in DB for cloud mode
    resume_path_str = str(docx_path)
    if user_id != "local":
        try:
            docx_bytes = Path(docx_path).read_bytes()
            file_id = uuid.uuid4().hex
            store_resume_file(conn, file_id, user_id, dedup_key,
                              Path(docx_path).name, docx_bytes)
            resume_path_str = f"blob:{file_id}"
        except Exception:
            log.warning("Failed to store resume BLOB, keeping file path")

    gaps = tailored.get("gaps")
    insert_manual_job(conn, {
        "dedup_key": dedup_key,
        "title_raw": title,
        "title_normalized": title.lower().strip(),
        "company": company,
        "location": "Manual submission",
        "url": url,
        "run_date": run_date,
        "status": "resume_generated",
        "resume_path": resume_path_str,
        "jd_text": jd_text,
        "jd_source": "manual_paste",
        "jd_word_count": word_count,
        "gaps": str(gaps) if gaps else None,
    })

    # Set user_id on the job
    if user_id != "local":
        update_job(conn, dedup_key, user_id=user_id)

    conn.close()

    return ManualJobResponse(
        dedup_key=dedup_key,
        title_raw=title,
        company=company,
        url=url,
        jd_word_count=word_count,
        created_at=run_date,
        resume_status="available",
        resume_status_label="Resume available",
        resume_path=resume_path_str,
    )


@app.delete("/api/manual-jobs/{dedup_key}", status_code=204)
def delete_manual_job_endpoint(dedup_key: str, user: dict = Depends(get_current_user)):
    """Delete a manual job and its resume file."""
    conn = get_connection()
    init_db(conn)
    user_id = user["user_id"]
    row = get_existing_job(conn, dedup_key)
    if not row:
        conn.close()
        raise HTTPException(404, "Job not found")

    # Verify ownership
    row_uid = row["user_id"]
    if user_id != "local" and row_uid and row_uid != user_id:
        conn.close()
        raise HTTPException(404, "Job not found")

    source = None
    try:
        source = row["source"]
    except (IndexError, KeyError):
        pass
    if source != "manual":
        conn.close()
        raise HTTPException(400, "Only manual jobs can be deleted")

    # Delete resume BLOB from DB
    if user_id != "local":
        delete_resume_file(conn, user_id, dedup_key)

    # Delete resume file from disk (local mode)
    if row["resume_path"] and not row["resume_path"].startswith("blob:"):
        resume_file = Path(row["resume_path"])
        if resume_file.exists():
            resume_file.unlink()

    delete_job(conn, dedup_key)
    conn.close()


@app.post("/api/manual-jobs/{dedup_key}/regenerate", response_model=ManualJobResponse)
def regenerate_manual_job(dedup_key: str, user: dict = Depends(get_current_user)):
    """Re-generate the resume for a manual job using the stored JD."""
    from src.tailoring import tailor_resume
    from src.doc_generator import generate_docx

    conn = get_connection()
    init_db(conn)
    user_id = user["user_id"]
    row = get_existing_job(conn, dedup_key)
    if not row:
        conn.close()
        raise HTTPException(404, "Job not found")

    # Verify ownership
    row_uid = row["user_id"]
    if user_id != "local" and row_uid and row_uid != user_id:
        conn.close()
        raise HTTPException(404, "Job not found")

    source = None
    try:
        source = row["source"]
    except (IndexError, KeyError):
        pass
    if source != "manual":
        conn.close()
        raise HTTPException(400, "Only manual jobs can be regenerated")

    jd_text = row["jd_text"] or ""
    if not jd_text:
        conn.close()
        raise HTTPException(400, "No JD text stored for this job")

    # Delete old resume BLOB
    if user_id != "local":
        delete_resume_file(conn, user_id, dedup_key)

    # Delete old resume file (local mode)
    if row["resume_path"] and not row["resume_path"].startswith("blob:"):
        old_file = Path(row["resume_path"])
        if old_file.exists():
            old_file.unlink()

    config = _get_config()
    ensure_directories()
    bank = _load_resume_bank_for_user(conn, user_id)

    # Get user's tailoring API key and provider
    tailoring_cfg = config.get("tailoring", {})
    provider = tailoring_cfg.get("provider", "gemini")
    api_key = None
    if user_id != "local":
        settings = get_user_settings(conn, user_id)
        if settings and settings["tailoring_provider"]:
            provider = settings["tailoring_provider"]
        if provider == "claude":
            api_key = _get_user_api_key(conn, user_id, "anthropic_key_enc")
        else:
            api_key = _get_user_api_key(conn, user_id, "gemini_key_enc")

    output_dir = PROJECT_ROOT / "data" / "resumes" / "manual"
    output_dir.mkdir(parents=True, exist_ok=True)

    job_dict = {
        "title_raw": row["title_raw"],
        "company": row["company"],
        "location": row["location"],
        "url": row["url"],
        "date_posted": row["date_posted"],
        "description_snippet": "",
        "dedup_key": dedup_key,
        "source": "manual",
    }

    try:
        tailored = tailor_resume(job_dict, jd_text, bank, config,
                                 api_key=api_key, provider_override=provider)
    except Exception as e:
        log.exception("Tailoring failed for manual job regeneration")
        conn.close()
        raise HTTPException(500, f"Resume tailoring failed: {e}")

    if not tailored.get("experience"):
        errors = tailored.get("validation_errors", [])
        msg = f"Tailoring produced no content. Errors: {errors}" if errors else "Tailoring produced empty resume."
        log.error(msg)
        conn.close()
        raise HTTPException(500, msg)

    try:
        docx_path = generate_docx(tailored, bank, job_dict, output_dir=output_dir)
    except Exception as e:
        log.exception("DOCX generation failed for manual job regeneration")
        conn.close()
        raise HTTPException(500, f"DOCX generation failed: {e}")

    # Store DOCX as BLOB
    resume_path_str = str(docx_path)
    if user_id != "local":
        try:
            docx_bytes = Path(docx_path).read_bytes()
            file_id = uuid.uuid4().hex
            store_resume_file(conn, file_id, user_id, dedup_key,
                              Path(docx_path).name, docx_bytes)
            resume_path_str = f"blob:{file_id}"
        except Exception:
            log.warning("Failed to store resume BLOB, keeping file path")

    update_job(conn, dedup_key,
               resume_path=resume_path_str,
               status="resume_generated")
    conn.close()

    return ManualJobResponse(
        dedup_key=dedup_key,
        title_raw=row["title_raw"],
        company=row["company"],
        url=row["url"],
        jd_word_count=row["jd_word_count"],
        created_at=row["created_at"],
        resume_status="available",
        resume_status_label="Resume available",
        resume_path=resume_path_str,
    )


# ---------------------------------------------------------------------------
# Pipeline run endpoints (SSE)
# ---------------------------------------------------------------------------

def _run_discovery_pipeline(queue: asyncio.Queue, loop: asyncio.AbstractEventLoop,
                            user_id: str):
    """Run SerpAPI discovery + filtering + scoring in a background thread."""
    from src.config import load_config, ensure_directories
    from src.db import get_connection, init_db, get_existing_job, upsert_job, decide_action, update_job
    from src.discovery import run_discovery
    from src.filtering import passes_hard_filters, normalize_title, is_target_company_override
    from src.scoring import score_pass1, passes_pass1_cutoff, score_pass2, classify_score
    from src.jd_extractor import extract_jd

    def emit(stage, message, progress=0.0, data=None):
        event = PipelineEvent(stage=stage, message=message, progress=progress, data=data)
        loop.call_soon_threadsafe(queue.put_nowait, event.model_dump())

    try:
        emit("discovery", "Loading config...", 0.0)
        config = load_config(skip_validation=CLOUD_MODE)
        ensure_directories()
        conn = get_connection()
        init_db(conn)
        run_date = date.today().isoformat()

        # Load user's SerpAPI key
        serpapi_key = None
        if user_id != "local":
            serpapi_key = _get_user_api_key(conn, user_id, "serpapi_key_enc")
            if not serpapi_key:
                emit("error", "SerpAPI key not configured. Add it in Settings.", 0.0)
                conn.close()
                return

        emit("discovery", "Running SerpAPI queries...", 0.05)
        raw_jobs = run_discovery(config, serpapi_key=serpapi_key)
        emit("discovery", f"Discovered {len(raw_jobs)} jobs", 0.2)

        emit("filtering", f"Filtering {len(raw_jobs)} jobs...", 0.25)
        passed_jobs = []
        for job in raw_jobs:
            filter_job = {
                "title": job["title_raw"],
                "company": job["company"],
                "location": job["location"],
                "date_posted": job["date_posted"],
                "description": job.get("description_snippet", ""),
            }
            dedup_key = job["dedup_key"]
            existing = get_existing_job(conn, dedup_key)
            action = decide_action(existing)
            if action in ("skip", "resurface"):
                if existing:
                    upsert_job(conn, {**job, "run_date": run_date,
                                      "title_normalized": normalize_title(job["title_raw"])})
                continue

            passes, filter_meta = passes_hard_filters(filter_job, config)
            if not passes:
                reason = filter_meta["reject_reason"]
                job_record = {**job, "run_date": run_date,
                              "title_normalized": normalize_title(job["title_raw"])}
                upsert_job(conn, job_record)
                update_job(conn, dedup_key, status="rejected",
                           reject_reason=f"Hard filter: {reason}")
                # Tag with user_id
                if user_id != "local":
                    update_job(conn, dedup_key, user_id=user_id)
                continue
            passed_jobs.append((job, filter_job, filter_meta))

        emit("filtering", f"{len(passed_jobs)} jobs passed filters", 0.35)

        emit("scoring", f"Scoring {len(passed_jobs)} jobs...", 0.4)
        scored_jobs = []
        for i, (job, filter_job, filter_meta) in enumerate(passed_jobs):
            pass1_result = score_pass1(filter_job, config)
            p1 = pass1_result["pass1_total"]
            if not passes_pass1_cutoff(p1, config):
                job_record = {**job, "run_date": run_date,
                              "title_normalized": normalize_title(job["title_raw"]),
                              "pass1_score": p1}
                upsert_job(conn, job_record)
                update_job(conn, job["dedup_key"], status="rejected",
                           pass1_score=p1,
                           reject_reason=f"Below Pass 1 cutoff ({p1}/75)")
                if user_id != "local":
                    update_job(conn, job["dedup_key"], user_id=user_id)
                continue

            jd_text, jd_source, jd_word_count = extract_jd(job)
            if jd_source == "skipped":
                job_record = {**job, "run_date": run_date,
                              "title_normalized": normalize_title(job["title_raw"]),
                              "pass1_score": p1}
                upsert_job(conn, job_record)
                update_job(conn, job["dedup_key"], status="rejected",
                           pass1_score=p1, jd_source="skipped", jd_word_count=jd_word_count,
                           reject_reason="JD too short")
                if user_id != "local":
                    update_job(conn, job["dedup_key"], user_id=user_id)
                continue

            pass2_result = score_pass2(pass1_result, jd_text, config)
            final_score = pass2_result["final_score"]
            classification = classify_score(final_score, config)

            job_record = {
                **job,
                "title_normalized": normalize_title(job["title_raw"]),
                "run_date": run_date,
                "pass1_score": pass1_result["pass1_total"],
                "final_score": final_score,
                "jd_source": jd_source,
                "jd_word_count": jd_word_count,
                "title_experimental": filter_meta.get("title_experimental", False),
                "score_breakdown": str(pass2_result),
            }
            upsert_job(conn, job_record)
            update_job(conn, job["dedup_key"], status="scored",
                        final_score=final_score, jd_text=jd_text,
                        jd_source=jd_source, jd_word_count=jd_word_count,
                        score_breakdown=str(pass2_result))
            if user_id != "local":
                update_job(conn, job["dedup_key"], user_id=user_id)

            if classification != "discard":
                scored_jobs.append(job["dedup_key"])

            progress = 0.4 + (0.4 * (i + 1) / max(len(passed_jobs), 1))
            emit("scoring", f"Scored {i + 1}/{len(passed_jobs)}", progress)

        conn.close()
        emit("done", f"Discovery complete. {len(scored_jobs)} jobs scored above threshold.", 1.0,
             data={"scored_keys": scored_jobs})

    except Exception as e:
        log.exception("Discovery pipeline failed")
        emit("error", f"Pipeline error: {e}", 0.0)


def _run_resume_generation(queue: asyncio.Queue, loop: asyncio.AbstractEventLoop,
                           dedup_keys: list[str], user_id: str):
    """Generate resumes for selected jobs in a background thread."""
    from src.config import load_config, ensure_directories
    from src.db import get_connection, init_db, get_existing_job, update_job
    from src.jd_extractor import extract_jd
    from src.tailoring import tailor_resume
    from src.doc_generator import generate_docx

    def emit(stage, message, progress=0.0, data=None):
        event = PipelineEvent(stage=stage, message=message, progress=progress, data=data)
        loop.call_soon_threadsafe(queue.put_nowait, event.model_dump())

    try:
        emit("tailoring", "Loading config and resume bank...", 0.0)
        config = load_config(skip_validation=CLOUD_MODE)
        ensure_directories()
        conn = get_connection()
        init_db(conn)
        bank = _load_resume_bank_for_user(conn, user_id)
        total = len(dedup_keys)
        generated = 0

        # Get user's tailoring API key and provider
        tailoring_cfg = config.get("tailoring", {})
        provider = tailoring_cfg.get("provider", "gemini")
        api_key = None
        if user_id != "local":
            settings = get_user_settings(conn, user_id)
            if settings and settings["tailoring_provider"]:
                provider = settings["tailoring_provider"]
            if provider == "claude":
                api_key = _get_user_api_key(conn, user_id, "anthropic_key_enc")
            else:
                api_key = _get_user_api_key(conn, user_id, "gemini_key_enc")

        for i, key in enumerate(dedup_keys):
            row = get_existing_job(conn, key)
            if not row:
                emit("tailoring", f"Job {key} not found, skipping", (i + 1) / total)
                continue

            job = {
                "title_raw": row["title_raw"],
                "company": row["company"],
                "location": row["location"],
                "url": row["url"],
                "date_posted": row["date_posted"],
                "description_snippet": row.get("jd_text") or "",
                "dedup_key": key,
            }

            jd_text = row["jd_text"] or ""
            if not jd_text:
                jd_text, jd_source, jd_wc = extract_jd(job)
                if jd_source == "skipped":
                    emit("tailoring", f"JD too short for {row['company']}, skipping",
                         (i + 1) / total)
                    continue

            progress_base = i / total
            emit("tailoring", f"Tailoring resume {i + 1}/{total}: {row['company']}...",
                 progress_base + 0.3 / total)

            try:
                tailored = tailor_resume(job, jd_text, bank, config,
                                         api_key=api_key, provider_override=provider)

                emit("docx", f"Generating DOCX {i + 1}/{total}: {row['company']}...",
                     progress_base + 0.7 / total)

                docx_path = generate_docx(tailored, bank, job)

                # Store DOCX as BLOB for cloud users
                resume_path_str = str(docx_path)
                if user_id != "local":
                    try:
                        docx_bytes = Path(docx_path).read_bytes()
                        file_id = uuid.uuid4().hex
                        store_resume_file(conn, file_id, user_id, key,
                                          Path(docx_path).name, docx_bytes)
                        resume_path_str = f"blob:{file_id}"
                    except Exception:
                        log.warning("Failed to store resume BLOB for %s", key)

                update_job(conn, key,
                           status="resume_generated",
                           resume_path=resume_path_str,
                           final_score=row["final_score"],
                           jd_text=jd_text,
                           jd_source=row["jd_source"] or "full_fetch",
                           jd_word_count=row["jd_word_count"] or len(jd_text.split()))
                generated += 1
                emit("docx", f"Resume generated for {row['company']}", (i + 1) / total)

            except Exception as e:
                log.exception("Resume generation failed for %s", row["company"])
                emit("error", f"Failed for {row['company']}: {e}", (i + 1) / total)

        conn.close()
        emit("done", f"Resume generation complete. {generated}/{total} resumes created.", 1.0)

    except Exception as e:
        log.exception("Resume generation pipeline failed")
        emit("error", f"Pipeline error: {e}", 0.0)


async def _sse_stream(target_fn, *args):
    """Generic SSE stream wrapper — runs target_fn in a thread, yields events."""
    if not _pipeline_lock.acquire(blocking=False):
        yield {"event": "error", "data": json.dumps(
            PipelineEvent(stage="error", message="Another pipeline run is already in progress").model_dump()
        )}
        return

    queue: asyncio.Queue = asyncio.Queue()
    loop = asyncio.get_event_loop()

    thread = threading.Thread(target=target_fn, args=(queue, loop, *args), daemon=True)
    thread.start()

    try:
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=0.5)
            except asyncio.TimeoutError:
                if not thread.is_alive() and queue.empty():
                    break
                continue

            yield {"event": "pipeline", "data": json.dumps(event)}

            if event.get("stage") in ("done", "error"):
                break
    finally:
        _pipeline_lock.release()
        thread.join(timeout=5)


@app.post("/api/run/discovery")
async def run_discovery_endpoint(request: Request):
    """Run SerpAPI discovery + filter + score. Streams progress via SSE."""
    user = get_current_user(request)
    return EventSourceResponse(_sse_stream(_run_discovery_pipeline, user["user_id"]))


@app.post("/api/run/generate-resumes")
async def run_generate_resumes(request: GenerateResumesRequest, req: Request):
    """Generate resumes for selected jobs. Streams progress via SSE."""
    user = get_current_user(req)
    if not request.dedup_keys:
        raise HTTPException(400, "No jobs selected")
    return EventSourceResponse(
        _sse_stream(_run_resume_generation, request.dedup_keys, user["user_id"])
    )


# ---------------------------------------------------------------------------
# Serve built frontend (production mode)
# ---------------------------------------------------------------------------

_DIST = PROJECT_ROOT / "ui" / "dist"

if _DIST.exists():
    from fastapi.staticfiles import StaticFiles

    # Serve static assets (JS, CSS, etc.)
    app.mount("/assets", StaticFiles(directory=str(_DIST / "assets")), name="static-assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        """Serve the SPA index.html for all non-API routes."""
        file_path = _DIST / full_path
        if file_path.exists() and file_path.is_file():
            return FileResponse(str(file_path))
        return FileResponse(str(_DIST / "index.html"))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    uvicorn.run(app, host="127.0.0.1", port=8000)
