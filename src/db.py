"""SQLite database for job tracking, deduplication, and status management."""

import hashlib
import re
import sqlite3
from datetime import date, datetime
from pathlib import Path

from src.config import PROJECT_ROOT

DB_PATH = PROJECT_ROOT / "db" / "pipeline.db"

SCHEMA = """\
CREATE TABLE IF NOT EXISTS jobs (
    dedup_key          TEXT PRIMARY KEY,
    title_raw          TEXT NOT NULL,
    title_normalized   TEXT NOT NULL,
    company            TEXT NOT NULL,
    location           TEXT NOT NULL,
    url                TEXT NOT NULL,
    date_posted        TEXT,
    first_seen_run     TEXT NOT NULL,
    last_seen_run      TEXT NOT NULL,
    times_seen         INTEGER DEFAULT 1,
    pass1_score        REAL,
    final_score        REAL,
    status             TEXT DEFAULT 'new',
    resume_path        TEXT,
    jd_text            TEXT,
    jd_source          TEXT,
    jd_word_count      INTEGER,
    title_experimental BOOLEAN DEFAULT 0,
    query_source       TEXT,
    score_breakdown    TEXT,
    gaps               TEXT,
    created_at         TEXT DEFAULT (datetime('now')),
    updated_at         TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_first_seen ON jobs(first_seen_run);
"""


def get_connection() -> sqlite3.Connection:
    """Open a connection to the SQLite database, creating it if needed."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    """Create tables and indexes if they don't exist."""
    conn.executescript(SCHEMA)
    conn.commit()


# ---------------------------------------------------------------------------
# Normalization helpers (used for dedup key generation)
# ---------------------------------------------------------------------------

def normalize_company(company: str) -> str:
    """Lowercase, strip whitespace, remove Inc/LLC/Corp suffixes."""
    c = company.lower().strip()
    c = re.sub(r',?\s*(inc\.?|llc\.?|corp\.?|ltd\.?|co\.?)$', '', c, flags=re.IGNORECASE)
    return c.strip()


def normalize_location(location: str) -> str:
    """Lowercase, strip whitespace, and remove trailing country/extras for dedup."""
    loc = location.lower().strip()
    # Remove trailing ", United States" or ", US" and similar
    loc = re.sub(r',?\s*united states\b.*$', '', loc)
    loc = re.sub(r',?\s*\bus\b.*$', '', loc)
    # Remove parenthetical extras like "(+1 other)"
    loc = re.sub(r'\s*\(.*?\)\s*', '', loc)
    return loc.strip()


def normalize_title_for_dedup(title: str) -> str:
    """
    Stable normalized form for dedup key generation.
    Must match the normalize_title() logic in filtering.py.
    """
    t = title.lower().strip()
    t = re.sub(r'^(junior|jr\.?|associate|entry[ -]level)\s+', '', t)
    t = re.sub(r'\s*[-\u2013\u2014,]\s*(remote|hybrid|contract|full[ -]time|intern).*$', '', t)
    t = re.sub(r'\s*\(.*?\)\s*', ' ', t)
    t = re.sub(r'\bapm\b', 'product manager', t)
    t = re.sub(r'\bpm([0-9])\b', r'product manager \1', t)
    t = re.sub(r'\bpm (i|ii|iii)\b', r'product manager \1', t)
    t = re.sub(r'\s+', ' ', t).strip()
    return t


def make_dedup_key(company: str, title: str, location: str) -> str:
    """Generate a 16-char hex dedup key from normalized company|title|location."""
    norm = f"{normalize_company(company)}|{normalize_title_for_dedup(title)}|{normalize_location(location)}"
    return hashlib.sha256(norm.encode()).hexdigest()[:16]


# ---------------------------------------------------------------------------
# CRUD operations
# ---------------------------------------------------------------------------

def get_existing_job(conn: sqlite3.Connection, dedup_key: str) -> sqlite3.Row | None:
    """Look up a job by its dedup key. Returns None if not found."""
    cur = conn.execute("SELECT * FROM jobs WHERE dedup_key = ?", (dedup_key,))
    return cur.fetchone()


def upsert_job(conn: sqlite3.Connection, job: dict) -> None:
    """
    Insert a new job or update an existing one.

    For new jobs: insert with all fields.
    For existing jobs: update last_seen_run, times_seen, and url (in case of repost).
    """
    existing = get_existing_job(conn, job["dedup_key"])

    if existing is None:
        conn.execute(
            """
            INSERT INTO jobs (
                dedup_key, title_raw, title_normalized, company, location,
                url, date_posted, first_seen_run, last_seen_run, times_seen,
                pass1_score, final_score, status, jd_source, jd_word_count,
                title_experimental, query_source
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, 'new', ?, ?, ?, ?)
            """,
            (
                job["dedup_key"],
                job["title_raw"],
                job["title_normalized"],
                job["company"],
                job["location"],
                job["url"],
                job.get("date_posted"),
                job["run_date"],
                job["run_date"],
                job.get("pass1_score"),
                job.get("final_score"),
                job.get("jd_source"),
                job.get("jd_word_count"),
                job.get("title_experimental", False),
                job.get("query_source"),
            ),
        )
    else:
        conn.execute(
            """
            UPDATE jobs
            SET last_seen_run = ?,
                times_seen = times_seen + 1,
                url = ?,
                updated_at = datetime('now')
            WHERE dedup_key = ?
            """,
            (job["run_date"], job["url"], job["dedup_key"]),
        )
    conn.commit()


def update_job(conn: sqlite3.Connection, dedup_key: str, **fields) -> None:
    """Update specific fields on a job row."""
    if not fields:
        return
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [dedup_key]
    conn.execute(
        f"UPDATE jobs SET {set_clause}, updated_at = datetime('now') WHERE dedup_key = ?",
        values,
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Decision logic
# ---------------------------------------------------------------------------

def decide_action(existing_row: sqlite3.Row | None, today: date | None = None) -> str:
    """
    Determine what to do with a job based on its current DB state.

    Returns one of: 'process', 'skip', 'resurface'.
    """
    if existing_row is None:
        return "process"

    if today is None:
        today = date.today()

    status = existing_row["status"]
    first_seen = datetime.fromisoformat(existing_row["first_seen_run"]).date()
    days_since_first_seen = (today - first_seen).days

    # Already applied or manually skipped — never show again
    if status in ("applied", "skipped"):
        return "skip"

    # Resume generated but not yet applied
    if status == "resume_generated":
        if days_since_first_seen >= 7:
            return "resurface"
        return "skip"

    # Scored but no resume — still open signal
    if status == "scored":
        return "resurface"

    # Status 'new' means pipeline crashed before processing
    if status == "new":
        return "process"

    # Expired or unknown
    if days_since_first_seen > 14:
        return "skip"

    return "skip"


def expire_old_jobs(conn: sqlite3.Connection, cutoff_days: int = 14) -> int:
    """
    Mark old jobs as expired. Returns the number of jobs expired.
    """
    cur = conn.execute(
        """
        UPDATE jobs
        SET status = 'expired', updated_at = datetime('now')
        WHERE status NOT IN ('applied', 'skipped', 'expired')
        AND julianday('now') - julianday(first_seen_run) > ?
        """,
        (cutoff_days,),
    )
    conn.commit()
    return cur.rowcount


def get_resurfacing_jobs(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Get jobs that should be resurfaced in the digest (scored or stale resume_generated)."""
    cur = conn.execute(
        """
        SELECT * FROM jobs
        WHERE (status = 'scored')
        OR (status = 'resume_generated'
            AND julianday('now') - julianday(first_seen_run) >= 7)
        ORDER BY final_score DESC
        """
    )
    return cur.fetchall()
