"""SerpAPI job discovery — 4 queries (3 NYC + 1 remote), normalize and dedup results.

SerpAPI google_jobs response shape (validated 2026-03-21):
  jobs_results[]: array of job objects
  Per job:
    title:              str — raw job title
    company_name:       str — may include "via" source (e.g., "JPMC Candidate Experience page")
    location:           str — city, state
    description:        str — full JD text (not just a snippet)
    detected_extensions:
      posted_at:        str — e.g., "2 days ago", "Today"
      schedule_type:    str — e.g., "Full-time"
    apply_options[]:    array of {title, link} — apply URLs
    job_id:             str — base64-encoded Google Jobs ID
    via:                str — source site name
    share_link:         str — Google Jobs share URL
"""

import json
import logging
from pathlib import Path

from serpapi import GoogleSearch

from src.config import get_env
from src.db import make_dedup_key

log = logging.getLogger(__name__)


def _build_search_params(query: str, location: str, config: dict,
                         serpapi_key: str | None = None) -> dict:
    """Build SerpAPI search parameters for a single query.

    Args:
        serpapi_key: If provided, use this key instead of the env var.
                     Used in multi-tenant mode where each user has their own key.
    """
    search_cfg = config["search"]
    date_filter = search_cfg.get("date_filter", "3days")
    api_key = serpapi_key or get_env("SERPAPI_KEY")
    return {
        "engine": "google_jobs",
        "q": query,
        "location": location,
        "chips": f"date_posted:{date_filter}",
        "num": search_cfg.get("results_per_query", 10),
        "api_key": api_key,
    }


def _normalize_job(raw: dict, query_source: str) -> dict:
    """Normalize a single SerpAPI job result into a standard job dict.

    Returns a dict matching what filtering.py and scoring.py expect.
    """
    # Extract best apply URL from apply_options
    apply_url = ""
    apply_options = raw.get("apply_options") or []
    if apply_options:
        apply_url = apply_options[0].get("link", "")

    # Fall back to share_link if no apply URL
    if not apply_url:
        apply_url = raw.get("share_link", "")

    # Extract posted_at from detected_extensions
    extensions = raw.get("detected_extensions") or {}
    posted_at = extensions.get("posted_at", "")

    title_raw = raw.get("title", "").strip()
    company = raw.get("company_name", "").strip()
    location = raw.get("location", "").strip()
    description = raw.get("description", "")

    return {
        "title_raw": title_raw,
        "company": company,
        "location": location,
        "url": apply_url,
        "date_posted": posted_at,
        "description_snippet": description,
        "query_source": query_source,
        "job_id": raw.get("job_id", ""),
        "via": raw.get("via", ""),
        "dedup_key": make_dedup_key(company, title_raw, location),
    }


def _run_single_query(query: str, location: str, query_source: str,
                       config: dict, serpapi_key: str | None = None) -> list[dict]:
    """Run one SerpAPI query and return normalized job dicts.

    Sends num directly (e.g. num=40). SerpAPI google_jobs supports num up to ~100.
    If SerpAPI returns fewer, that's all that matched.
    """
    params = _build_search_params(query, location, config, serpapi_key=serpapi_key)
    log.info("SerpAPI query: %r location=%r num=%s", query, location, params.get("num"))

    try:
        search = GoogleSearch(params)
        results = search.get_dict()
    except Exception:
        log.exception("SerpAPI query failed: %r", query)
        return []

    raw_jobs = results.get("jobs_results") or []
    log.info("  -> %d results", len(raw_jobs))

    normalized = []
    for raw in raw_jobs:
        try:
            job = _normalize_job(raw, query_source)
            normalized.append(job)
        except Exception:
            log.exception("Failed to normalize job: %s", raw.get("title", "?"))
    return normalized


def run_discovery(config: dict, serpapi_key: str | None = None) -> list[dict]:
    """Run all SerpAPI queries and return deduplicated normalized job list.

    Args:
        config: Loaded config dict.
        serpapi_key: If provided, use this key instead of the env var.

    Returns list of job dicts, each containing:
        title_raw, company, location, url, date_posted,
        description_snippet, query_source, job_id, via, dedup_key
    """
    search_cfg = config["search"]
    nyc_queries = search_cfg.get("nyc_queries", [])
    remote_queries = search_cfg.get("remote_queries", [])
    nyc_location = search_cfg.get("serpapi_location", "New York, NY")
    remote_location = search_cfg.get("remote_search_location", "United States")

    all_jobs: list[dict] = []

    for query in nyc_queries:
        jobs = _run_single_query(query, nyc_location, "nyc", config, serpapi_key=serpapi_key)
        all_jobs.extend(jobs)

    for query in remote_queries:
        jobs = _run_single_query(query, remote_location, "remote", config, serpapi_key=serpapi_key)
        all_jobs.extend(jobs)

    # Dedup across queries — keep first occurrence
    seen_keys: set[str] = set()
    unique_jobs: list[dict] = []
    for job in all_jobs:
        key = job["dedup_key"]
        if key not in seen_keys:
            seen_keys.add(key)
            unique_jobs.append(job)

    log.info("Discovery: %d raw -> %d unique jobs", len(all_jobs), len(unique_jobs))
    return unique_jobs


def run_discovery_dry_run(fixture_path: str | Path | None = None) -> list[dict]:
    """Load jobs from a fixture file instead of calling SerpAPI.

    Uses tests/fixtures/fake_serpapi_response.json by default.
    """
    if fixture_path is None:
        fixture_path = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "fake_serpapi_response.json"
    else:
        fixture_path = Path(fixture_path)

    with open(fixture_path) as f:
        data = json.load(f)

    raw_jobs = data.get("jobs_results") or []
    log.info("Dry-run: loaded %d jobs from %s", len(raw_jobs), fixture_path)

    jobs = []
    for raw in raw_jobs:
        try:
            job = _normalize_job(raw, "dry_run")
            jobs.append(job)
        except Exception:
            log.exception("Failed to normalize fixture job: %s", raw.get("title", "?"))

    # Dedup
    seen_keys: set[str] = set()
    unique_jobs: list[dict] = []
    for job in jobs:
        key = job["dedup_key"]
        if key not in seen_keys:
            seen_keys.add(key)
            unique_jobs.append(job)

    return unique_jobs
