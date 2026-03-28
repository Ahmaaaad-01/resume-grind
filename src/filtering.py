"""Hard filters: title classification, location, YOE, posting age, language."""

import re

# ---------------------------------------------------------------------------
# Title denylist / allowlist (from spec Section 2a)
# ---------------------------------------------------------------------------

TITLE_DENYLIST = [
    # Seniority
    r'\bsenior\b', r'\bsr\b', r'\bstaff\b', r'\bprincipal\b',
    r'\bdirector\b', r'\bvp\b', r'\bhead of\b', r'\bgroup\b',
    r'\blead\b', r'\bmanaging\b',

    # Wrong "PM" roles
    r'\bproject manager\b', r'\bprogram manager\b',
    r'\bproperty manager\b', r'\bplant manager\b',
    r'\bperformance marketing\b',

    # Time-based "PM"
    r'\bpm shift\b', r'\bevening\b', r'\bnight\b', r'\bam/pm\b',
    r'\bpm cashier\b', r'\bpm crew\b',

    # Adjacent but wrong roles
    r'\bmarketing manager\b', r'\bbrand manager\b',
    r'\baccount manager\b', r'\bsales manager\b',
    r'\boperations manager\b', r'\bcustomer success\b',
    r'\bui/ux\b', r'\bdesign manager\b',
    r'\bengineering manager\b',
    r'\btechnical program\b', r'\btpm\b',
]

TITLE_ALLOWLIST = [
    r'\bproduct manager\b',
    r'\bassociate product manager\b',
    r'\bpm[0-9]\b',
    r'\bpm i\b', r'\bpm ii\b',
    r'\bjunior product manager\b',
    r'\bproduct management\b',
    r'\bproduct analyst\b',
]


# ---------------------------------------------------------------------------
# Title normalization
# ---------------------------------------------------------------------------

def normalize_title(title: str) -> str:
    """Stable normalized form for dedup and display."""
    t = title.lower().strip()
    t = re.sub(r'^(junior|jr\.?|associate|entry[ -]level)\s+', '', t)
    t = re.sub(r'\s*[-\u2013\u2014,]\s*(remote|hybrid|contract|full[ -]time|intern).*$', '', t)
    t = re.sub(r'\s*\(.*?\)\s*', ' ', t)
    t = re.sub(r'\bapm\b', 'product manager', t)
    t = re.sub(r'\bpm([0-9])\b', r'product manager \1', t)
    t = re.sub(r'\bpm (i|ii|iii)\b', r'product manager \1', t)
    t = re.sub(r'\s+', ' ', t).strip()
    return t


# ---------------------------------------------------------------------------
# 3-pass title classification
# ---------------------------------------------------------------------------

def classify_title(raw_title: str, config: dict) -> tuple[bool, str, bool]:
    """
    Three-pass title classification.

    Returns (passes_filter, normalized_title, is_experimental).
    is_experimental=True means the title matched the experimental allowlist,
    not the core allowlist.
    """
    t = raw_title.lower().strip()

    # Pass 1: Denylist — reject immediately
    for pattern in TITLE_DENYLIST:
        if re.search(pattern, t):
            return (False, t, False)

    # Pass 2: Core allowlist — standard PM roles
    for pattern in TITLE_ALLOWLIST:
        if re.search(pattern, t):
            return (True, normalize_title(t), False)

    # Pass 3: Experimental allowlist — config-driven PM-adjacent roles
    for pattern in config.get('title_filter', {}).get('experimental_allowlist', []):
        if re.search(pattern, t):
            return (True, normalize_title(t), True)

    # No match — reject
    return (False, t, False)


# ---------------------------------------------------------------------------
# Location filter
# ---------------------------------------------------------------------------

REMOTE_SIGNALS = ['remote', 'work from home', 'anywhere', 'distributed']
HYBRID_SIGNALS = ['hybrid', 'flexible']


def passes_location_filter(job_location: str, company: str, config: dict) -> bool:
    """
    Check if a job's location passes the configured location filter.

    Target-list companies bypass the location filter entirely.
    """
    loc = job_location.lower().strip()
    loc_config = config['location']

    # Target-company override: always pass, regardless of location
    target_companies = [c.lower() for c in config['scoring']['target_companies']]
    if company.lower().strip() in target_companies:
        return True

    # Remote
    if loc_config['accept_remote']:
        if any(signal in loc for signal in REMOTE_SIGNALS):
            return True

    # Metro match
    in_metro = any(alias in loc for alias in loc_config['metro_aliases'])

    # Hybrid in metro
    is_hybrid = any(signal in loc for signal in HYBRID_SIGNALS)
    if is_hybrid and in_metro and loc_config['accept_hybrid_in_metro']:
        return True

    # On-site in metro
    if in_metro and loc_config['accept_onsite_in_metro']:
        return True

    # Relocation
    if loc_config['accept_relocation']:
        return True

    return False


def is_target_company_override(job_location: str, company: str, config: dict) -> bool:
    """
    Check if a job passes location filter ONLY because of the target-company
    override (i.e., it would fail otherwise). Used for digest flagging.
    """
    target_companies = [c.lower() for c in config['scoring']['target_companies']]
    if company.lower().strip() not in target_companies:
        return False

    # Check if it would pass without the override
    loc = job_location.lower().strip()
    loc_config = config['location']

    if loc_config['accept_remote']:
        if any(signal in loc for signal in REMOTE_SIGNALS):
            return False  # Would pass anyway via remote

    in_metro = any(alias in loc for alias in loc_config['metro_aliases'])
    is_hybrid = any(signal in loc for signal in HYBRID_SIGNALS)

    if is_hybrid and in_metro and loc_config['accept_hybrid_in_metro']:
        return False
    if in_metro and loc_config['accept_onsite_in_metro']:
        return False
    if loc_config['accept_relocation']:
        return False

    # Only passed because of target-company override
    return True


# ---------------------------------------------------------------------------
# YOE filter
# ---------------------------------------------------------------------------

# Patterns to extract years-of-experience requirements from JD text
_YOE_RANGE_PATTERN = re.compile(
    r'(\d+)\s*(?:[-\u2013\u2014]|to)\s*(\d+)\s*\+?\s*years?',
    re.IGNORECASE,
)

_YOE_SINGLE_PATTERNS = [
    # "5+ years of experience" / "5 years experience" / "5+ years of relevant experience"
    re.compile(r'(\d+)\s*\+?\s*years?\s+(?:of\s+)?(?:\w+\s+)?experience', re.IGNORECASE),
    # "minimum 5 years" / "at least 5 years"
    re.compile(r'(?:minimum|at\s+least|min\.?)\s*(\d+)\s*\+?\s*years?', re.IGNORECASE),
]


def extract_yoe(jd_text: str) -> int | None:
    """
    Extract the minimum years-of-experience requirement from JD text.

    Returns the minimum YOE found, or None if no requirement detected.
    For ranges like "3-5 years", returns the lower bound (3).
    For "5+ years", returns 5.
    """
    if not jd_text:
        return None

    min_yoe_found = None

    # Check range patterns first ("3-5 years", "2 to 4 years")
    for match in _YOE_RANGE_PATTERN.finditer(jd_text):
        yoe = int(match.group(1))  # Take the lower bound
        if min_yoe_found is None or yoe < min_yoe_found:
            min_yoe_found = yoe

    # Check single-number patterns ("5+ years", "minimum 3 years")
    for pattern in _YOE_SINGLE_PATTERNS:
        for match in pattern.finditer(jd_text):
            yoe = int(match.group(1))
            if min_yoe_found is None or yoe < min_yoe_found:
                min_yoe_found = yoe

    return min_yoe_found


def check_yoe(jd_text: str) -> bool:
    """
    Check if a job's YOE requirement is within range.

    Returns True (pass) if requirement is <= 5 years or not specified.
    Returns False (reject) if requirement is >= 6 years.
    """
    yoe = extract_yoe(jd_text)
    if yoe is None:
        return True  # No requirement detected — pass (conservative)
    return yoe <= 5


# ---------------------------------------------------------------------------
# Master filter function
# ---------------------------------------------------------------------------

def passes_hard_filters(
    job: dict,
    config: dict,
) -> tuple[bool, dict]:
    """
    Apply all hard filters to a job.

    Returns (passes, metadata) where metadata contains:
      - title_passes: bool
      - title_normalized: str
      - title_experimental: bool
      - location_passes: bool
      - location_target_override: bool
      - yoe_passes: bool
      - reject_reason: str | None

    Note: Posting age filter was removed — SerpAPI's date_posted chip
    handles freshness, and SerpAPI returns relative date strings ("2 days ago")
    that can't be parsed as ISO dates. See Tuning-Round-2.md Section 8.3.
    """
    meta = {
        "title_passes": False,
        "title_normalized": "",
        "title_experimental": False,
        "location_passes": False,
        "location_target_override": False,
        "yoe_passes": False,
        "reject_reason": None,
    }

    # Title filter
    passes, normalized, is_experimental = classify_title(
        job.get("title", ""), config
    )
    meta["title_passes"] = passes
    meta["title_normalized"] = normalized
    meta["title_experimental"] = is_experimental
    if not passes:
        meta["reject_reason"] = "title"
        return (False, meta)

    # Location filter
    location_passes = passes_location_filter(
        job.get("location", ""), job.get("company", ""), config
    )
    meta["location_passes"] = location_passes
    meta["location_target_override"] = is_target_company_override(
        job.get("location", ""), job.get("company", ""), config
    )
    if not location_passes:
        meta["reject_reason"] = "location"
        return (False, meta)

    # YOE filter
    jd_text = job.get("description", "") or job.get("snippet", "") or ""
    yoe_passes = check_yoe(jd_text)
    meta["yoe_passes"] = yoe_passes
    if not yoe_passes:
        meta["reject_reason"] = "yoe"
        return (False, meta)

    return (True, meta)
