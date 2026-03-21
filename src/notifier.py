"""Notification — save local HTML digest and optionally send via Gmail.

Always saves local HTML + opens in browser. Gmail is optional and non-blocking.
"""

import logging
import os
import webbrowser
from datetime import date
from pathlib import Path

from src.config import PROJECT_ROOT

log = logging.getLogger(__name__)


def _gmail_credentials_configured() -> bool:
    """Check if Gmail OAuth credentials exist."""
    return (PROJECT_ROOT / "data" / "gmail_credentials.json").exists()


def _build_subject_line(run_date: str, total_jobs: int, resume_count: int) -> str:
    """Build email subject line per spec."""
    from datetime import datetime
    try:
        dt = datetime.fromisoformat(run_date)
        formatted = dt.strftime("%b %d")
    except (ValueError, TypeError):
        formatted = run_date
    return f"PM Jobs — {formatted} — {total_jobs} roles, {resume_count} resumes ready"


def notify(digest_html: str, resume_paths: list[str | Path],
           config: dict, run_date: str | None = None) -> Path:
    """Save local HTML digest and optionally send via Gmail.

    Args:
        digest_html: Rendered HTML string from digest.py.
        resume_paths: List of paths to generated DOCX resumes.
        config: Application config dict.
        run_date: ISO date string. Defaults to today.

    Returns:
        Path to the saved local digest file.
    """
    if run_date is None:
        run_date = date.today().isoformat()

    # Always: save local digest
    digest_dir = PROJECT_ROOT / "data" / "digests"
    digest_dir.mkdir(parents=True, exist_ok=True)
    digest_path = digest_dir / f"{run_date}.html"
    digest_path.write_text(digest_html, encoding="utf-8")
    log.info("Digest saved: %s", digest_path)

    # Always: open in browser
    try:
        webbrowser.open(f"file://{digest_path.resolve()}")
        log.info("Digest opened in browser")
    except Exception:
        log.warning("Could not open browser — digest saved at %s", digest_path)

    # Optional: Gmail
    notification_cfg = config.get("notification", {})
    if notification_cfg.get("gmail_enabled", False) and _gmail_credentials_configured():
        try:
            _send_gmail(
                subject=_build_subject_line(run_date, len(resume_paths), len(resume_paths)),
                html_body=digest_html,
                attachments=[str(p) for p in resume_paths],
            )
            log.info("Gmail digest sent successfully")
        except Exception as e:
            log.warning("Gmail send failed (non-fatal): %s", e)

    return digest_path


def _send_gmail(subject: str, html_body: str, attachments: list[str]) -> None:
    """Send digest via Gmail API. Placeholder for v1 — not yet implemented."""
    # Gmail OAuth integration is optional in v1.
    # When implemented, this will use google-api-python-client.
    raise NotImplementedError(
        "Gmail sending not yet implemented. "
        "Set notification.gmail_enabled: false in config.yaml."
    )
