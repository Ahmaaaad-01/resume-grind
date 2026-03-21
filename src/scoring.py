"""Two-pass scoring rubric: Pass 1 (snippet-based, 0-75) and Pass 2 (keyword overlap, 0-25)."""

import re
from datetime import date

from src.filtering import extract_yoe, REMOTE_SIGNALS, HYBRID_SIGNALS


# ---------------------------------------------------------------------------
# Title scoring (spec Section 3d)
# ---------------------------------------------------------------------------

_EARLY_CAREER_PATTERNS = [
    r'\bapm\b',
    r'\bassociate product manager\b',
    r'\bpm1\b',
    r'\bpm i\b',
    r'\bjunior product manager\b',
]

_SPECIALTY_PM_PATTERN = re.compile(
    r'\b(growth|platform|core|payments)\s+pm\b', re.IGNORECASE
)


def score_title(raw_title: str) -> int:
    """
    Score title precision. Purely about role type and seniority level.
    Specialty fit is handled by keyword overlap in Pass 2.

    Returns 10-25 points.
    """
    t = raw_title.lower().strip()

    # Exact early-career signals → max points
    if any(re.search(p, t) for p in _EARLY_CAREER_PATTERNS):
        return 25

    # Generic "product manager" with no seniority → strong match
    if re.search(r'\bproduct manager\b', t):
        return 20

    # Specialty PM variants
    if _SPECIALTY_PM_PATTERN.search(t):
        return 15

    # PM-adjacent
    if re.search(r'\bproduct analyst\b', t):
        return 12

    # Passed hard filter but doesn't match well
    return 10


# ---------------------------------------------------------------------------
# YOE scoring (spec Section 3e)
# ---------------------------------------------------------------------------

def score_yoe(jd_text: str) -> int:
    """
    Score YOE fit based on the requirement extracted from JD text.

    Returns 8-20 points.
    """
    yoe = extract_yoe(jd_text)

    if yoe is None:
        return 12  # Not specified

    if yoe <= 2:
        return 20  # 0-2 years
    if yoe <= 3:
        return 18  # 1-3 years (lower bound is 3, so range includes 3)
    if yoe <= 4:
        return 14  # 2-4 years
    # 3-5+ years
    return 8


# ---------------------------------------------------------------------------
# Location scoring (spec Section 3f)
# ---------------------------------------------------------------------------

def score_location(job_location: str, config: dict) -> int:
    """
    Score location fit.

    Returns 2-10 points.
    """
    loc = job_location.lower().strip()
    metro_aliases = config['location']['metro_aliases']
    in_metro = any(alias in loc for alias in metro_aliases)

    is_remote = any(signal in loc for signal in REMOTE_SIGNALS)
    is_hybrid = any(signal in loc for signal in HYBRID_SIGNALS)

    if is_remote:
        return 10
    if is_hybrid and in_metro:
        return 8
    if in_metro and not is_hybrid:
        return 6
    return 2


# ---------------------------------------------------------------------------
# Company scoring (spec Section 3h)
# ---------------------------------------------------------------------------

def score_company(company: str, config: dict) -> int:
    """
    Score company match.

    Returns 3, 6, or 10 points.
    """
    c = company.lower().strip()

    # On target list → 10
    target_companies = [tc.lower() for tc in config['scoring']['target_companies']]
    if c in target_companies:
        return 10

    # Tech/fintech signal match → 6
    signals = config['scoring'].get('tech_fintech_signals', [])
    if any(signal in c for signal in signals):
        return 6

    # Other → 3
    return 3


# ---------------------------------------------------------------------------
# Recency scoring (spec Section 3i)
# ---------------------------------------------------------------------------

def score_recency(date_posted: str | None, today: date | None = None) -> int:
    """
    Score posting recency.

    Returns 2-10 points.
    """
    if today is None:
        today = date.today()

    if not date_posted:
        return 2  # Unknown date — conservative

    try:
        posted = date.fromisoformat(date_posted)
    except ValueError:
        return 2

    age_days = (today - posted).days

    if age_days <= 0:
        return 10  # Today
    if age_days == 1:
        return 7   # Yesterday
    if age_days == 2:
        return 4   # 2 days ago
    if age_days == 3:
        return 2   # 3 days ago
    return 2       # Older (shouldn't reach here if hard filter is working)


# ---------------------------------------------------------------------------
# Keyword overlap scoring (spec Section 3g) — Pass 2 only
# ---------------------------------------------------------------------------

def score_keywords(jd_text: str, config: dict) -> tuple[int, int, list[str]]:
    """
    Score keyword overlap against full JD text.

    Returns (score, match_count, matched_skills).
    Score = (match_count / 20) * 25, rounded to nearest int.
    """
    core_skills = config['scoring']['core_skills']
    jd_lower = jd_text.lower()

    matched = []
    for skill in core_skills:
        if skill.lower() in jd_lower:
            matched.append(skill)

    match_count = len(matched)
    total_skills = len(core_skills)
    score = round((match_count / total_skills) * 25)

    return (score, match_count, matched)


# ---------------------------------------------------------------------------
# Pass 1: Snippet-based partial score (0-75)
# ---------------------------------------------------------------------------

def score_pass1(
    job: dict,
    config: dict,
    today: date | None = None,
) -> dict:
    """
    Compute Pass 1 partial score from snippet-available factors.

    Returns a dict with individual scores and total:
    {
        'title': int,
        'yoe': int,
        'location': int,
        'company': int,
        'recency': int,
        'pass1_total': int,
    }
    """
    # YOE scoring uses the snippet/description text available from SerpAPI
    jd_snippet = job.get('description', '') or job.get('snippet', '') or ''

    title = score_title(job.get('title', ''))
    yoe = score_yoe(jd_snippet)
    location = score_location(job.get('location', ''), config)
    company = score_company(job.get('company', ''), config)
    recency = score_recency(job.get('date_posted'), today)

    return {
        'title': title,
        'yoe': yoe,
        'location': location,
        'company': company,
        'recency': recency,
        'pass1_total': title + yoe + location + company + recency,
    }


def passes_pass1_cutoff(pass1_score: int, config: dict) -> bool:
    """Check if a Pass 1 score meets the cutoff threshold."""
    cutoff = config['scoring'].get('pass1_cutoff', 30)
    return pass1_score >= cutoff


# ---------------------------------------------------------------------------
# Pass 2: Add keyword overlap for final score (0-100)
# ---------------------------------------------------------------------------

def score_pass2(
    pass1_breakdown: dict,
    jd_text: str,
    config: dict,
) -> dict:
    """
    Compute Pass 2 final score by adding keyword overlap to Pass 1 score.

    Returns the full breakdown dict with added keyword fields and final_score.
    """
    keyword_score, match_count, matched_skills = score_keywords(jd_text, config)

    breakdown = {
        **pass1_breakdown,
        'keywords': keyword_score,
        'keyword_match_count': match_count,
        'keyword_matched_skills': matched_skills,
        'final_score': pass1_breakdown['pass1_total'] + keyword_score,
    }

    return breakdown


def classify_score(final_score: int, config: dict) -> str:
    """
    Classify a final score into an action tier.

    Returns 'generate_resume', 'include_in_digest', or 'discard'.
    """
    thresholds = config['scoring']['thresholds']
    if final_score >= thresholds['generate_resume']:
        return 'generate_resume'
    if final_score >= thresholds['include_in_digest']:
        return 'include_in_digest'
    return 'discard'
