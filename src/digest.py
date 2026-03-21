"""Build the HTML digest from pipeline results using Jinja2."""

import logging
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from src.config import PROJECT_ROOT

log = logging.getLogger(__name__)

TEMPLATES_DIR = PROJECT_ROOT / "templates"


def _build_warnings(job: dict) -> list[str]:
    """Generate warning flags for a job based on spec Section 7."""
    warnings = []

    # Score 40-59 range
    score = job.get("final_score", 0)
    if 40 <= score < 60:
        pass  # No extra warning — it's already in "Worth a Look"

    # Validation failures
    for err in job.get("validation_errors", []):
        warnings.append(f"Tailoring validation: {err}")

    # Short JD
    jd_source = job.get("jd_source", "")
    jd_word_count = job.get("jd_word_count", 0)
    if jd_source == "serpapi_snippet" and jd_word_count and jd_word_count < 150:
        warnings.append("Short JD — resume may be less precisely tailored")

    # Experimental title
    if job.get("title_experimental"):
        warnings.append("Non-standard PM title — review carefully")

    # Target company relocation override
    if job.get("target_company_override"):
        company = job.get("company", "this company")
        warnings.append(f"Requires relocation — passed because {company} is on your target list")

    # Large keyword gap
    keyword_stats = job.get("keyword_stats", {})
    missing = keyword_stats.get("missing", [])
    if len(missing) > 5:
        warnings.append(f"{len(missing)} JD keywords unmatched")

    return warnings


def build_digest(results: dict) -> str:
    """Render the HTML digest from pipeline results.

    Args:
        results: Dict containing:
            run_date: str
            top_matches: list[dict] — jobs with score >= 60
            worth_a_look: list[dict] — jobs with score 40-59
            resurfaced: list[dict] — jobs resurfacing from previous runs
            review_carefully: list[dict] — jobs with warnings
            stats: dict — pipeline statistics

    Returns:
        Rendered HTML string.
    """
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=True,
    )
    template = env.get_template("digest.html")

    # Add warnings to all job lists
    for job_list_key in ("top_matches", "worth_a_look", "resurfaced", "review_carefully"):
        for job in results.get(job_list_key, []):
            if "warnings" not in job:
                job["warnings"] = _build_warnings(job)

    # Move jobs with warnings from top_matches to review_carefully
    top = results.get("top_matches", [])
    review = results.get("review_carefully", [])
    clean_top = []
    for job in top:
        if job.get("warnings"):
            review.append(job)
        else:
            clean_top.append(job)
    results["top_matches"] = clean_top
    results["review_carefully"] = review

    # Ensure stats has all required fields
    stats = results.get("stats", {})
    stats.setdefault("total_jobs", 0)
    stats.setdefault("resumes_generated", 0)
    stats.setdefault("hard_filter_passed", 0)
    stats.setdefault("pass1_filtered", 0)
    stats.setdefault("jd_full_fetch", 0)
    stats.setdefault("jd_snippet", 0)
    stats.setdefault("jd_skipped", 0)
    stats.setdefault("nyc_jobs", 0)
    stats.setdefault("remote_jobs", 0)
    stats.setdefault("experimental_titles", 0)
    stats.setdefault("target_overrides", 0)
    stats.setdefault("errors", [])
    results["stats"] = stats

    html = template.render(**results)
    log.info("Digest rendered: %d top, %d look, %d resurface, %d review",
             len(results.get("top_matches", [])),
             len(results.get("worth_a_look", [])),
             len(results.get("resurfaced", [])),
             len(results.get("review_carefully", [])))
    return html
