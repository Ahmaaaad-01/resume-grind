"""Pipeline orchestrator — wires discovery through digest delivery.

Usage:
    python -m src.main              # Live run with SerpAPI
    python -m src.main --dry-run    # Use fixture data instead of SerpAPI
"""

import argparse
import logging
import sys
from datetime import date

from src.config import load_config, ensure_directories
from src.db import (
    get_connection, init_db, get_existing_job, upsert_job,
    decide_action, update_job, expire_old_jobs, get_resurfacing_jobs,
)
from src.discovery import run_discovery, run_discovery_dry_run
from src.filtering import passes_hard_filters, normalize_title, is_target_company_override
from src.scoring import (
    score_pass1, passes_pass1_cutoff, score_pass2,
    classify_score,
)
from src.jd_extractor import extract_jd
from src.resume_bank import load_resume_bank
from src.tailoring import tailor_resume
from src.doc_generator import generate_docx
from src.digest import build_digest
from src.notifier import notify

log = logging.getLogger(__name__)


def _setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def run_pipeline(dry_run: bool = False):
    """Execute the full pipeline."""
    _setup_logging()
    run_date = date.today().isoformat()
    log.info("=== Pipeline run: %s (dry_run=%s) ===", run_date, dry_run)

    # --- Setup ---
    config = load_config(skip_validation=dry_run)
    ensure_directories()
    conn = get_connection()
    init_db(conn)

    bank = load_resume_bank()

    # --- Stats tracking ---
    stats = {
        "total_jobs": 0,
        "hard_filter_passed": 0,
        "pass1_filtered": 0,
        "resumes_generated": 0,
        "jd_full_fetch": 0,
        "jd_snippet": 0,
        "jd_skipped": 0,
        "nyc_jobs": 0,
        "remote_jobs": 0,
        "experimental_titles": 0,
        "target_overrides": 0,
        "errors": [],
    }

    # --- Discovery ---
    log.info("Stage 1: Discovery")
    if dry_run:
        raw_jobs = run_discovery_dry_run()
    else:
        raw_jobs = run_discovery(config)

    stats["total_jobs"] = len(raw_jobs)
    for j in raw_jobs:
        if j.get("query_source") == "remote":
            stats["remote_jobs"] += 1
        else:
            stats["nyc_jobs"] += 1

    log.info("Discovered %d unique jobs", len(raw_jobs))

    # --- Per-job pipeline ---
    top_matches = []
    worth_a_look = []
    resume_paths = []

    for job in raw_jobs:
        company = job["company"]
        title = job["title_raw"]
        log.info("Processing: %s at %s", title, company)

        # Map discovery dict keys to what filtering/scoring expect
        filter_job = {
            "title": title,
            "company": company,
            "location": job["location"],
            "date_posted": job["date_posted"],
            "description": job.get("description_snippet", ""),
        }

        # Dedup check
        dedup_key = job["dedup_key"]
        existing = get_existing_job(conn, dedup_key)
        action = decide_action(existing)

        if action in ("skip", "resurface"):
            log.info("  -> %s (already processed)", action.title())
            # Update last_seen
            if existing:
                upsert_job(conn, {**job, "run_date": run_date,
                                  "title_normalized": normalize_title(title)})
            continue

        # Hard filters
        passes, filter_meta = passes_hard_filters(filter_job, config)

        if not passes:
            reason = filter_meta["reject_reason"]
            log.info("  -> Rejected by hard filters: %s", reason)
            upsert_job(conn, {**job, "run_date": run_date,
                              "title_normalized": normalize_title(title)})
            update_job(conn, dedup_key, status="rejected",
                       reject_reason=f"Hard filter: {reason}")
            continue

        stats["hard_filter_passed"] += 1
        is_experimental = filter_meta.get("title_experimental", False)
        if is_experimental:
            stats["experimental_titles"] += 1

        target_override = is_target_company_override(
            job["location"], company, config,
        )
        if target_override:
            stats["target_overrides"] += 1

        # Pass 1 scoring
        pass1_result = score_pass1(filter_job, config)
        pass1_score = pass1_result["pass1_total"]

        if not passes_pass1_cutoff(pass1_score, config):
            log.info("  -> Cut by Pass 1: %s/75", pass1_score)
            stats["pass1_filtered"] += 1
            upsert_job(conn, {**job, "run_date": run_date,
                              "title_normalized": normalize_title(title),
                              "pass1_score": pass1_score})
            update_job(conn, dedup_key, status="rejected",
                       pass1_score=pass1_score,
                       reject_reason=f"Below Pass 1 cutoff ({pass1_score}/75)")
            continue

        # JD extraction
        jd_text, jd_source, jd_word_count = extract_jd(job)
        if jd_source == "full_fetch":
            stats["jd_full_fetch"] += 1
        elif jd_source == "serpapi_snippet":
            stats["jd_snippet"] += 1
        else:
            stats["jd_skipped"] += 1

        if jd_source == "skipped":
            log.info("  -> JD skipped (too short)")
            upsert_job(conn, {**job, "run_date": run_date,
                              "title_normalized": normalize_title(title),
                              "pass1_score": pass1_score})
            update_job(conn, dedup_key, status="rejected",
                       pass1_score=pass1_score,
                       jd_source="skipped", jd_word_count=jd_word_count,
                       reject_reason="JD too short")
            continue

        # Pass 2 scoring
        pass2_result = score_pass2(pass1_result, jd_text, config)
        final_score = pass2_result["final_score"]
        classification = classify_score(final_score, config)

        log.info("  -> Score: %s/100 (%s)", final_score, classification)

        # Build job record for DB and digest
        job_record = {
            **job,
            "title_normalized": normalize_title(title),
            "run_date": run_date,
            "pass1_score": pass1_score,
            "final_score": final_score,
            "jd_source": jd_source,
            "jd_word_count": jd_word_count,
            "title_experimental": is_experimental,
            "score_breakdown": str(pass2_result),
        }

        # Upsert to DB
        upsert_job(conn, job_record)

        if classification == "discard":
            continue

        # Build digest entry
        digest_entry = {
            **job,
            "final_score": final_score,
            "jd_source": jd_source,
            "jd_word_count": jd_word_count,
            "title_experimental": is_experimental,
            "target_company_override": target_override,
            "keyword_stats": {
                "matched": pass2_result.get("keyword_match_count", 0),
                "total": len(config.get("scoring", {}).get("core_skills", [])),
                "missing": [s for s in config.get("scoring", {}).get("core_skills", [])
                            if s not in pass2_result.get("keyword_matched_skills", [])],
            },
            "gaps": [],
            "bullets": [],
            "validation_errors": [],
            "resume_path": None,
        }

        if classification == "generate_resume":
            # Tailor resume
            try:
                tailored = tailor_resume(job, jd_text, bank, config)
                digest_entry["validation_errors"] = tailored.get("validation_errors", [])
                digest_entry["gaps"] = tailored.get("gaps", [])

                # Extract bullets for digest
                for role in tailored.get("experience", []):
                    for bullet in role.get("bullets_selected", []):
                        digest_entry["bullets"].append(bullet)

                # Generate DOCX
                docx_path = generate_docx(tailored, bank, job)
                digest_entry["resume_path"] = str(docx_path.resolve())
                resume_paths.append(docx_path)
                stats["resumes_generated"] += 1

                # Update DB
                update_job(conn, dedup_key,
                           status="resume_generated",
                           resume_path=str(docx_path),
                           final_score=final_score,
                           jd_text=jd_text,
                           jd_source=jd_source,
                           jd_word_count=jd_word_count)

                log.info("  -> Resume generated: %s", docx_path.name)
            except Exception as e:
                log.error("  -> Tailoring/DOCX failed: %s", e)
                stats["errors"].append(f"{company} - {title}: {e}")
                update_job(conn, dedup_key, status="scored",
                           final_score=final_score)

            digest_entry["match_reason"] = _build_match_reason(pass2_result)
            top_matches.append(digest_entry)

        elif classification == "include_in_digest":
            update_job(conn, dedup_key, status="scored",
                       final_score=final_score)
            worth_a_look.append(digest_entry)

    # --- Resurfacing ---
    resurfaced_rows = get_resurfacing_jobs(conn)
    resurfaced = []
    for row in resurfaced_rows:
        resurfaced.append({
            "company": row["company"],
            "title_raw": row["title_raw"],
            "final_score": row["final_score"] or 0,
            "first_seen_run": row["first_seen_run"],
            "url": row["url"],
            "resume_path": row["resume_path"],
        })

    # --- Expire old jobs ---
    expired_count = expire_old_jobs(conn)
    if expired_count:
        log.info("Expired %d old jobs", expired_count)

    # --- Build and deliver digest ---
    log.info("Stage 2: Building digest")
    digest_results = {
        "run_date": run_date,
        "top_matches": top_matches,
        "worth_a_look": worth_a_look,
        "resurfaced": resurfaced,
        "review_carefully": [],
        "stats": stats,
    }
    digest_html = build_digest(digest_results)

    log.info("Stage 3: Delivering digest")
    digest_path = notify(digest_html, resume_paths, config, run_date=run_date)

    # --- Summary ---
    log.info("=== Pipeline complete ===")
    log.info("  Jobs discovered: %d", stats["total_jobs"])
    log.info("  Passed hard filters: %d", stats["hard_filter_passed"])
    log.info("  Cut by Pass 1: %d", stats["pass1_filtered"])
    log.info("  Resumes generated: %d", stats["resumes_generated"])
    log.info("  Digest: %s", digest_path)

    conn.close()
    return digest_results


def _build_match_reason(pass2_result: dict) -> str:
    """Build a human-readable match reason from scoring breakdown."""
    parts = []
    if pass2_result.get("title", 0) >= 25:
        parts.append("strong title match")
    if pass2_result.get("company", 0) >= 10:
        parts.append("target company")
    elif pass2_result.get("company", 0) >= 6:
        parts.append("tech/fintech company")
    if pass2_result.get("location", 0) >= 8:
        parts.append("good location fit")
    matched = pass2_result.get("keyword_match_count", 0)
    if matched:
        parts.append(f"keyword overlap ({matched}/20)")
    return ", ".join(parts) if parts else "general match"


def main():
    parser = argparse.ArgumentParser(description="PM Job Pipeline")
    parser.add_argument("--dry-run", action="store_true",
                        help="Use fixture data instead of live SerpAPI calls")
    args = parser.parse_args()
    run_pipeline(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
