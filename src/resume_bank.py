"""Load and validate the resume bank JSON file.

The resume bank is manually authored. This module only loads and validates —
it never modifies the file.
"""

import json
import logging
from pathlib import Path

from src.config import PROJECT_ROOT

log = logging.getLogger(__name__)

DEFAULT_PATH = PROJECT_ROOT / "data" / "master_resume" / "resume_bank.json"


def load_resume_bank(path: str | Path | None = None) -> dict:
    """Load resume bank from JSON file and validate its structure.

    Args:
        path: Path to resume_bank.json. Defaults to data/master_resume/resume_bank.json.

    Returns:
        Parsed and validated resume bank dict.

    Raises:
        FileNotFoundError: If the file doesn't exist.
        ValueError: If validation fails (with all errors listed).
    """
    if path is None:
        path = DEFAULT_PATH
    path = Path(path)

    with open(path) as f:
        bank = json.load(f)

    errors = validate_resume_bank(bank)
    if errors:
        msg = f"Resume bank validation failed ({len(errors)} errors):\n"
        msg += "\n".join(f"  - {e}" for e in errors)
        raise ValueError(msg)

    log.info("Resume bank loaded: %d roles, %d summaries",
             len(bank.get("experience", [])),
             len(bank.get("summaries", [])))
    return bank


def validate_resume_bank(bank: dict) -> list[str]:
    """Validate resume bank structure. Returns list of error strings (empty = valid)."""
    errors: list[str] = []

    # --- meta ---
    if "meta" not in bank:
        errors.append("Missing 'meta' section")
    else:
        for field in ("version", "last_updated", "candidate_name"):
            if field not in bank["meta"]:
                errors.append(f"meta.{field} is missing")

    # --- contact ---
    if "contact" not in bank:
        errors.append("Missing 'contact' section")
    else:
        for field in ("name", "email", "phone", "linkedin", "location"):
            if field not in bank["contact"]:
                errors.append(f"contact.{field} is missing")

    # --- summaries ---
    summaries = bank.get("summaries", [])
    if len(summaries) < 2:
        errors.append(f"Need at least 2 summary variants, got {len(summaries)}")
    if len(summaries) > 5:
        errors.append(f"Maximum 5 summary variants, got {len(summaries)}")

    summary_ids: set[str] = set()
    for i, s in enumerate(summaries):
        for field in ("id", "focus", "text", "best_for_tags"):
            if field not in s:
                errors.append(f"summaries[{i}] missing '{field}'")
        sid = s.get("id", "")
        if sid:
            if sid in summary_ids:
                errors.append(f"Duplicate summary id: {sid}")
            summary_ids.add(sid)
        text = s.get("text", "")
        if len(text) > 350:
            errors.append(f"Summary '{sid}' exceeds 350 chars ({len(text)} chars)")

    # --- experience ---
    all_ids: set[str] = set()
    experience = bank.get("experience", [])
    if not experience:
        errors.append("No experience entries")

    for i, role in enumerate(experience):
        for field in ("role_id", "company", "title", "start_date", "end_date",
                       "location", "include_always", "bullets"):
            if field not in role:
                errors.append(f"experience[{i}] missing '{field}'")

        role_id = role.get("role_id", f"experience[{i}]")
        bullets = role.get("bullets", [])
        include_always = role.get("include_always", False)

        if include_always and len(bullets) < 3:
            errors.append(
                f"Role '{role_id}' has include_always=true but only "
                f"{len(bullets)} bullets (need at least 3)"
            )

        for j, b in enumerate(bullets):
            for field in ("id", "text", "tags", "priority"):
                if field not in b:
                    errors.append(f"Role '{role_id}' bullet[{j}] missing '{field}'")
            bid = b.get("id", "")
            if bid:
                if bid in all_ids:
                    errors.append(f"Duplicate bullet id: {bid}")
                all_ids.add(bid)
            if "has_metric" not in b:
                errors.append(f"Role '{role_id}' bullet[{j}] missing 'has_metric'")

    # --- skills ---
    if "skills" not in bank:
        errors.append("Missing 'skills' section")
    else:
        skills = bank["skills"]
        for category in ("technical", "platform"):
            if category not in skills:
                errors.append(f"skills.{category} is missing")
            else:
                for k, s in enumerate(skills[category]):
                    if "skill" not in s:
                        errors.append(f"skills.{category}[{k}] missing 'skill'")
                    if "tags" not in s:
                        errors.append(f"skills.{category}[{k}] missing 'tags'")

    # --- education ---
    education = bank.get("education", [])
    if not education:
        errors.append("No education entries")
    for i, edu in enumerate(education):
        for field in ("id", "school", "degree", "graduation", "include_always"):
            if field not in edu:
                errors.append(f"education[{i}] missing '{field}'")
        eid = edu.get("id", "")
        if eid:
            if eid in all_ids:
                errors.append(f"Duplicate education id: {eid}")
            all_ids.add(eid)

    # --- projects (optional) ---
    for i, proj in enumerate(bank.get("projects", [])):
        for field in ("id", "name", "context", "bullets"):
            if field not in proj:
                errors.append(f"projects[{i}] missing '{field}'")
        pid = proj.get("id", "")
        if pid:
            if pid in all_ids:
                errors.append(f"Duplicate project id: {pid}")
            all_ids.add(pid)
        for j, b in enumerate(proj.get("bullets", [])):
            for field in ("id", "text", "tags", "has_metric"):
                if field not in b:
                    errors.append(f"Project '{pid}' bullet[{j}] missing '{field}'")
            bid = b.get("id", "")
            if bid:
                if bid in all_ids:
                    errors.append(f"Duplicate project bullet id: {bid}")
                all_ids.add(bid)

    return errors


def get_all_bullet_ids(bank: dict) -> set[str]:
    """Extract all bullet IDs from experience and projects."""
    ids: set[str] = set()
    for role in bank.get("experience", []):
        for b in role.get("bullets", []):
            ids.add(b["id"])
    for proj in bank.get("projects", []):
        for b in proj.get("bullets", []):
            ids.add(b["id"])
    return ids


def get_role_bullet_ids(bank: dict, role_id: str) -> set[str]:
    """Get bullet IDs belonging to a specific role."""
    for role in bank.get("experience", []):
        if role.get("role_id") == role_id:
            return {b["id"] for b in role.get("bullets", [])}
    return set()
