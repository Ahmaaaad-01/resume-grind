# PM Job Pipeline — Consolidated v1 Spec

## Status

This is the **active source of truth** for the v1 implementation. It supersedes all prior versions.

**Revision history**:
- v1.0: Original locked spec + addendums 1 and 2
- v1.1: Incorporates design review decisions — two-pass scoring, JD fallback chain, local-first execution, denylist fix, bullet minimum rules, title scoring clarification
- v1.2 (current): Search coverage / recall improvements — broader query set, 3-day discovery window, remote-specific query, experimental title allowlist, target-company location override, Pass 1 cutoff monitoring

---

## 1. Source Strategy

**Single source**: SerpAPI `google_jobs` engine only. No RSS feeds, no Wellfound, no Lever/Greenhouse scraping. Google Jobs already aggregates from LinkedIn, Indeed, Glassdoor, Lever, Greenhouse, and company career pages.

**6 queries per run**, organized into two groups:

```python
# Group A: NYC-localized queries (5 queries)
# These use the configured serpapi_location (default: "New York, NY")
NYC_QUERIES = [
    "associate product manager",
    "product manager entry level",
    "APM product",
    "junior product manager PM1",
    "product manager",               # Broad — catches generic-titled PM roles
]

# Group B: Remote-focused query (1 query)
# Uses location "United States" to catch remote roles at companies HQ'd outside NYC
REMOTE_QUERIES = [
    "product manager remote",
]
```

The broad `"product manager"` query is essential — many companies (including target companies like Robinhood) post roles as simply "Product Manager" with no seniority qualifier. The YOE requirement is buried in the JD, not the title. Hard filters handle the extra noise from senior roles.

The `"product manager remote"` query uses `location: "United States"` instead of `"New York, NY"` to surface remote-first roles at companies headquartered outside NYC (e.g., Stripe in SF, Notion in SF, Discord in SF). Without this, SerpAPI's NYC-localized results may not rank these roles highly enough to appear.

**Parameters**:

```python
# For NYC_QUERIES
NYC_SEARCH_PARAMS = {
    "engine": "google_jobs",
    "location": "New York, NY",          # From config — serpapi_location
    "chips": "date_posted:3days",        # 3-day window — matches hard filter freshness
    "num": 10,
}

# For REMOTE_QUERIES
REMOTE_SEARCH_PARAMS = {
    "engine": "google_jobs",
    "location": "United States",         # From config — remote_search_location
    "chips": "date_posted:3days",
    "num": 10,
}
```

**Date filter**: `date_posted:3days` (or the closest SerpAPI-supported option — verify in Step 0). The previous `date_posted:today` filter created a gap: the spec allows jobs up to 3 days old, but discovery only surfaced jobs from the last ~24 hours. The discovery window now matches the hard filter's freshness window. Deduplication (Section 4) prevents the same job from being re-processed across runs.

**Note on SerpAPI date filter values**: SerpAPI may support `date_posted:today`, `date_posted:3days`, `date_posted:week`, or different syntax. Confirm the exact supported values in Step 0. If `3days` is not available, use `date_posted:week` and let the hard filter's 3-day posting age check do the precise cutoff.

Total raw results per run: up to 60 (6 queries × 10), which dedup and filter down to 5–15 actionable jobs.

**Free tier budget**: 100 searches/month ÷ 6 queries/run = ~16 runs/month. That covers weekday runs for 3 weeks. If you run daily (Mon–Fri, ~22 runs/month), you'll need 132 searches — slightly over the free tier. Options: (a) accept occasional overages, (b) drop to 5 queries by combining the two weakest, or (c) upgrade to the paid tier ($50/mo for 5,000 searches). Monitor usage in the first 2 weeks and decide.

**Important — validate SerpAPI response shape early**: Before building downstream modules, run a real SerpAPI query and confirm the actual fields returned (title, company, location, date, description snippet, apply links). The pipeline must handle both cases: (a) SerpAPI returns a direct apply URL, and (b) SerpAPI returns only a `job_id` and inline description with no direct URL. See Section 3c for the fallback design. Also confirm the exact supported values for the `chips` date filter parameter.

---

## 2. Hard Filters

Binary pass/fail. A job that fails any one of these is discarded before scoring. No AI — pure deterministic logic.

### 2a. Title Filter — Two-Pass Classification

**Pass 1 — Denylist** (reject immediately if any pattern matches, case-insensitive with word boundaries):

```python
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
```

**Note**: `\bem\b` is deliberately excluded. It false-positives on legitimate titles containing "em" as a token. "Engineering Manager" is already caught by `\bengineering manager\b`. A standalone "EM" title won't match the allowlist, so it's rejected by default anyway.

**Pass 2 — Allowlist** (must match at least one to proceed):

```python
TITLE_ALLOWLIST = [
    r'\bproduct manager\b',
    r'\bassociate product manager\b',
    r'\bapm\b',                     # Only valid after denylist clears "am/pm"
    r'\bpm[0-9]\b',                 # PM1, PM2, PM3
    r'\bpm i\b', r'\bpm ii\b',     # PM I, PM II
    r'\bjunior product manager\b',
    r'\bproduct management\b',
    r'\bproduct analyst\b',
]
```

**Logic**: Three-pass classification. Denylist runs first — if any pattern matches, reject immediately. Then check the core allowlist — if it matches, the job passes as a standard PM role. Then check the experimental allowlist (config-driven) — if it matches, the job passes but is flagged as a non-standard title. If neither allowlist matches, reject (standalone "PM" with no qualifying context is rejected by default).

```python
import re

def classify_title(raw_title: str, config: dict) -> tuple[bool, str, bool]:
    """
    Returns (passes_filter, normalized_title, is_experimental).
    is_experimental=True means the title matched the experimental allowlist,
    not the core allowlist. It will be flagged in the digest.
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

    # Pass 3: Experimental allowlist — PM-adjacent roles (config-driven)
    for pattern in config.get('title_filter', {}).get('experimental_allowlist', []):
        if re.search(pattern, t):
            return (True, normalize_title(t), True)

    # No match — reject
    return (False, t, False)
```

The experimental allowlist is defined in `config/config.yaml` (see Section 12) and can be modified without code changes. Matches are stored with `title_experimental: true` in the database and flagged in the digest: "⚠️ Non-standard PM title — review carefully." This lets you test recall expansion for PM-adjacent roles without polluting the core results.


def normalize_title(title: str) -> str:
    """Stable normalized form for dedup and display."""
    t = title.lower().strip()
    t = re.sub(r'^(junior|jr\.?|associate|entry[ -]level)\s+', '', t)
    t = re.sub(r'\s*[-–—,]\s*(remote|hybrid|contract|full[ -]time|intern).*$', '', t)
    t = re.sub(r'\s*\(.*?\)\s*', ' ', t)
    t = re.sub(r'\bapm\b', 'product manager', t)
    t = re.sub(r'\bpm([0-9])\b', r'product manager \1', t)
    t = re.sub(r'\bpm (i|ii|iii)\b', r'product manager \1', t)
    t = re.sub(r'\s+', ' ', t).strip()
    return t
```

**Key design decisions**:
- Denylist runs first. "Senior Associate Product Manager" is caught by `\bsenior\b` before the allowlist sees "product manager."
- "Product Manager II" passes the filter. Whether it's too senior is a scoring question (YOE factor), not a filter question.
- Dual titles like "Product Manager / Project Manager" are rejected because denylist catches "project manager."

### 2b. Location Filter — Config-Driven with Target-Company Override

Configured in `config/config.yaml`. v1 targets New York metro. `accept_relocation` is `false` globally, but jobs at target-list companies bypass the location filter entirely — they always pass so you're aware of them, even if they require relocation.

```python
def passes_location_filter(job_location: str, company: str, config: dict) -> bool:
    loc = job_location.lower().strip()
    loc_config = config['location']

    # Target-company override: always pass, regardless of location
    target_companies = [c.lower() for c in config['scoring']['target_companies']]
    if company.lower().strip() in target_companies:
        return True

    if loc_config['accept_remote']:
        remote_signals = ['remote', 'work from home', 'anywhere', 'distributed']
        if any(signal in loc for signal in remote_signals):
            return True

    in_metro = any(alias in loc for alias in loc_config['metro_aliases'])

    hybrid_signals = ['hybrid', 'flexible']
    is_hybrid = any(signal in loc for signal in hybrid_signals)
    if is_hybrid and in_metro and loc_config['accept_hybrid_in_metro']:
        return True

    if in_metro and loc_config['accept_onsite_in_metro']:
        return True

    if loc_config['accept_relocation']:
        return True

    return False
```

Target-company jobs that pass only because of the override still get scored normally on location — they'll receive 2/10 for relocation, which pushes them down the ranking relative to remote and NYC jobs. But they'll appear in the digest so you can decide whether to pursue relocation or ask about remote flexibility during the process.

### 2c. Other Hard Filters

| Filter | Rule |
|--------|------|
| **YOE** | If JD states minimum ≥ 5 years, reject. If ≤ 4 years or not mentioned, pass. |
| **Posting age** | ≤ 3 days old (from SerpAPI `detected_extensions.posted_at`). |
| **Language** | JD must be in English. |

---

## 3. Two-Pass Scoring

Scoring happens in two passes to avoid fetching full JDs for jobs that will obviously be discarded.

### 3a. Pass 1 — Snippet-Based Partial Score

Runs immediately after hard filters, using only data available from the SerpAPI response (no network fetch required).

**Factors scored in Pass 1** (75 points possible):

| Factor | Max | Method |
|--------|-----|--------|
| Title precision | 25 | See `score_title()` below |
| YOE fit | 20 | Range tiers |
| Location | 10 | See `score_location()` below |
| Target company | 10 | Config list |
| Posting recency | 10 | Days since posted |

**Pass 1 cutoff**: Jobs scoring **< 30 out of 75** are discarded. Survivors proceed to Pass 2.

This cutoff eliminates jobs that fail on multiple non-keyword dimensions (wrong seniority + bad location + old post), without penalizing jobs that might have great keyword overlap once the full JD is available. The 30/75 threshold is tunable after observing real job volumes.

**Monitoring requirement**: After the first 5 runs, check how many jobs are being cut by Pass 1 vs. hard filters. If Pass 1 cuts fewer than 2 jobs per run on average, lower the cutoff to 20 or remove it entirely — it's not earning its keep and could be silently hurting recall. The digest footer should report: "Pass 1 filtered: N jobs (out of M hard-filter survivors)."

### 3b. Pass 2 — Full JD Score

For all Pass 1 survivors:

1. **Fetch the full JD** using the fallback chain (see Section 3c below).
2. **Score keyword overlap** against the full JD text (25 points).
3. **Compute final score** = Pass 1 score + keyword overlap score (0–100).

**Final thresholds**:
- **≥ 60**: Generate tailored resume. Include in digest under "Top Matches."
- **40–59**: Include in digest as "Worth a Look" (link only, no resume).
- **< 40**: Discard silently.

This means the pipeline fetches full JDs for roughly 15–25 jobs per run (all hard-filter survivors above the Pass 1 cutoff), then generates resumes for only the top scorers. Slightly more fetches than scoring everything on snippets, but much more accurate ranking.

### 3c. JD Extraction Fallback Chain

When fetching the full job description for Pass 2 scoring and for tailoring, use this ordered fallback:

```python
def extract_jd(job: dict) -> tuple[str, str]:
    """
    Returns (jd_text, source) where source is one of:
    'full_fetch', 'serpapi_snippet', 'skipped'.

    Attempts full page fetch first, falls back to SerpAPI description,
    skips if content is too short to be useful.
    """
    MIN_WORDS_THRESHOLD = 50

    # Attempt 1: Full page fetch from apply URL
    if job.get('apply_url'):
        try:
            full_text = fetch_and_parse(job['apply_url'])
            if len(full_text.split()) >= MIN_WORDS_THRESHOLD:
                return (full_text, 'full_fetch')
        except (FetchError, ParseError, TimeoutError):
            pass  # Fall through to next attempt

    # Attempt 2: SerpAPI inline description/snippet
    snippet = job.get('description', '') or job.get('snippet', '')
    if len(snippet.split()) >= MIN_WORDS_THRESHOLD:
        return (snippet, 'serpapi_snippet')

    # Attempt 3: Skip — not enough content to score or tailor
    return ('', 'skipped')
```

**Word count thresholds**:
- **Under 50 words**: Skip. Not enough content to score keywords or tailor a resume against. Job is logged as `jd_extraction_failed` and excluded from the digest.
- **50–150 words**: Marginal but usable. Keyword scoring and tailoring proceed, but the digest flags it: "⚠️ Short JD — resume may be less precisely tailored."
- **Over 150 words**: Solid. Full scoring and tailoring with no caveats.

**JD source is stored** in the database (`jd_source` field — see Section 4) so you can track how often the pipeline falls back to snippets and whether those resumes perform differently.

### 3d. Title Scoring

Title scoring is purely about role type and seniority level. Specialty fit (growth, consumer, mobile, etc.) is handled by keyword overlap in Pass 2, not by title scoring.

```python
def score_title(raw_title: str) -> int:
    t = raw_title.lower().strip()
    if any(re.search(p, t) for p in [
        r'\bapm\b', r'\bassociate product manager\b',
        r'\bpm1\b', r'\bpm i\b', r'\bjunior product manager\b'
    ]):
        return 25
    if re.search(r'\bproduct manager\b', t):
        return 20
    if re.search(r'\b(growth|platform|core|payments)\s+pm\b', t):
        return 15
    if re.search(r'\bproduct analyst\b', t):
        return 12
    return 10
```

### 3e. YOE Scoring

| JD requirement | Points |
|----------------|--------|
| 0–2 years | 20 |
| 1–3 years | 18 |
| 2–4 years | 14 |
| Not specified | 12 |
| 3–5 years | 8 |

### 3f. Location Scoring

```python
def score_location(job_location: str, config: dict) -> int:
    loc = job_location.lower().strip()
    metro_aliases = config['location']['metro_aliases']
    in_metro = any(alias in loc for alias in metro_aliases)

    remote_signals = ['remote', 'work from home', 'anywhere', 'distributed']
    is_remote = any(signal in loc for signal in remote_signals)

    hybrid_signals = ['hybrid', 'flexible']
    is_hybrid = any(signal in loc for signal in hybrid_signals)

    if is_remote:
        return 10
    if is_hybrid and in_metro:
        return 8
    if in_metro and not is_hybrid:
        return 6
    return 2
```

### 3g. Keyword Overlap Scoring (Pass 2 only)

```python
CORE_SKILLS = [
    "product management", "roadmap", "A/B testing", "user research",
    "agile", "scrum", "cross-functional", "stakeholder management",
    "SQL", "data analysis", "KPIs", "metrics", "mobile",
    "consumer", "fintech", "Jira", "Figma", "PRD",
    "user stories", "go-to-market"
]
# score = (match_count / 20) * 25
```

This factor is scored only in Pass 2 because it requires the full JD text (or at minimum a 50+ word snippet) for accurate matching.

### 3h. Company Scoring

| Match | Points |
|-------|--------|
| On target list | 10 |
| Tech/fintech company | 6 |
| Other | 3 |

Target companies are configured in `config/config.yaml` (see Section 12).

### 3i. Recency Scoring

| Age | Points |
|-----|--------|
| Today | 10 |
| Yesterday | 7 |
| 2 days ago | 4 |
| 3 days ago | 2 |

---

## 4. Deduplication and Freshness

### Dedup key

```python
import hashlib

def dedup_key(company: str, title: str, location: str) -> str:
    norm = f"{company.lower().strip()}|{normalize_title(title)}|{location.lower().strip()}"
    return hashlib.sha256(norm.encode()).hexdigest()[:16]
```

The same job on Lever, LinkedIn, and Google Jobs will have different URLs but the same dedup key. URL is stored but never used for dedup.

**Normalization before hashing**:

| Field | Normalization |
|-------|--------------|
| `company` | Lowercase, strip whitespace, remove Inc/LLC/Corp suffixes |
| `title` | Run through `normalize_title()` (Section 2a) |
| `location` | Lowercase, strip whitespace. "San Francisco, CA" and "SF Bay Area" → "san francisco ca". "Remote" stays "remote". |

### SQLite `jobs` table

```sql
CREATE TABLE IF NOT EXISTS jobs (
    dedup_key        TEXT PRIMARY KEY,
    title_raw        TEXT NOT NULL,
    title_normalized TEXT NOT NULL,
    company          TEXT NOT NULL,
    location         TEXT NOT NULL,
    url              TEXT NOT NULL,
    date_posted      TEXT,
    first_seen_run   TEXT NOT NULL,
    last_seen_run    TEXT NOT NULL,
    times_seen       INTEGER DEFAULT 1,
    pass1_score      REAL,             -- Score from Pass 1 (0-75)
    final_score      REAL,             -- Final score after Pass 2 (0-100)
    status           TEXT DEFAULT 'new',
    resume_path      TEXT,
    jd_text          TEXT,
    jd_source        TEXT,             -- 'full_fetch', 'serpapi_snippet', or 'skipped'
    jd_word_count    INTEGER,          -- Word count of extracted JD
    title_experimental BOOLEAN DEFAULT 0, -- True if matched experimental allowlist
    query_source     TEXT,             -- 'nyc' or 'remote' — which query group found this job
    score_breakdown  TEXT,
    gaps             TEXT,
    created_at       TEXT DEFAULT (datetime('now')),
    updated_at       TEXT DEFAULT (datetime('now'))
);

CREATE INDEX idx_status ON jobs(status);
CREATE INDEX idx_first_seen ON jobs(first_seen_run);
```

**Status values**: `new` | `scored` | `resume_generated` | `applied` | `skipped` | `expired`

### Decision logic per run

```python
def decide_action(job, existing_row) -> str:
    """Returns one of: 'process', 'skip', 'resurface'"""
    if existing_row is None:
        return 'process'

    status = existing_row['status']
    days_since_first_seen = (today - existing_row['first_seen_run']).days

    if status in ('applied', 'skipped'):
        return 'skip'

    if status == 'resume_generated':
        if days_since_first_seen >= 7:
            return 'resurface'
        return 'skip'

    if status == 'scored':
        return 'resurface'

    if status == 'new':
        return 'process'

    if days_since_first_seen > 14:
        return 'skip'

    return 'skip'
```

| Action | What happens |
|--------|-------------|
| `process` | Full pipeline: Pass 1 score → Pass 2 score → extract JD → tailor resume → generate DOCX → include in digest |
| `skip` | Do nothing. Update `last_seen_run` and `times_seen` in DB. |
| `resurface` | Include in digest under "Reminder: Still Open." Link to existing resume. No regeneration. |

### Expiration

```python
def expire_old_jobs(db, cutoff_days=14):
    db.execute("""
        UPDATE jobs
        SET status = 'expired', updated_at = datetime('now')
        WHERE status NOT IN ('applied', 'skipped', 'expired')
        AND julianday('now') - julianday(first_seen_run) > ?
    """, (cutoff_days,))
```

### Reposted jobs

Same `dedup_key` but new URL and newer `date_posted`. The dedup key catches it, `last_seen_run` and `times_seen` are updated, and the URL is updated to the newest one. The existing `status` drives the decision logic.

### Manual regeneration

No automatic regeneration in v1. To regenerate after updating your resume bank:

```bash
python -m src.main --regenerate-all-pending
```

---

## 5. Resume Bank Schema (`data/master_resume/resume_bank.json`)

### Top-level structure

```json
{
  "meta": {
    "version": "1.0",
    "last_updated": "YYYY-MM-DD",
    "candidate_name": "First Last"
  },
  "contact": { ... },
  "summaries": [ ... ],
  "experience": [ ... ],
  "skills": { ... },
  "education": [ ... ],
  "projects": [ ... ]
}
```

### `contact`

```json
{
  "name": "First Last",
  "email": "you@email.com",
  "phone": "555-123-4567",
  "linkedin": "linkedin.com/in/yourhandle",
  "location": "City, State"
}
```

### `summaries`

```json
[
  {
    "id": "sum-consumer",
    "focus": "consumer_product",
    "text": "2–3 sentence summary under 350 characters.",
    "best_for_tags": ["consumer", "mobile", "B2C"]
  }
]
```

Rules: minimum 2, maximum 5 variants. Each must be 2–3 sentences, under 350 characters. Claude selects the variant whose `best_for_tags` have the highest overlap with JD keywords, then may swap 1–2 phrases for keyword fit. No new claims, no new experience.

### `experience`

```json
[
  {
    "role_id": "role-c1",
    "company": "Company Name",
    "title": "Product Manager",
    "start_date": "2023-09",
    "end_date": "present",
    "location": "City, State / Remote",
    "include_always": true,
    "bullets": [
      {
        "id": "b01",
        "text": "Full bullet text as it appears on the master resume.",
        "tags": ["mobile", "consumer", "launch", "cross-functional"],
        "has_metric": true,
        "metric_value": "2M+ users",
        "priority": 1
      }
    ]
  }
]
```

**Bullet field definitions**:

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Globally unique. Pattern: `b{NN}`. This is the `source_ids` value Claude references. |
| `text` | string | Exact bullet text from master resume. Source of truth. |
| `tags` | string[] | 3–8 lowercase keyword tags for scoring and selection. |
| `has_metric` | bool | Whether the bullet contains a quantified result. |
| `metric_value` | string or null | The specific metric, for human reference only. |
| `priority` | int (1–3) | 1 = strongest, always include if relevant. 2 = solid, include if space allows. 3 = situational, only if it fills a specific JD keyword gap. |

**Role field definitions**:

| Field | Type | Description |
|-------|------|-------------|
| `role_id` | string | Unique. Pattern: `role-{xx}`. |
| `company` | string | As it appears on the resume. Never altered by Claude. |
| `title` | string | Exact title. Never altered by Claude. |
| `start_date` | string | YYYY-MM. |
| `end_date` | string | YYYY-MM or "present". |
| `include_always` | bool | If true, role always appears (with bullet selection). If false, role is included only when 2+ bullet tags overlap with JD keywords. Roles with `include_always: false` and fewer than 3 bullets should use this flag — Claude includes them when relevant rather than being forced to pad irrelevant bullets to meet a minimum. |
| `bullets` | array | Ideally 4–8 bullets for `include_always: true` roles (gives Claude selection room). Roles with fewer than 3 bullets should have `include_always: false`. |

**Bullet count rules**:
- For `include_always: true` roles: Claude selects 3–4 bullets per the `max_bullets_per_role` / `min_bullets_per_role` config.
- For `include_always: false` roles: Claude includes all available bullets if the role is selected (no minimum enforced). If a role has 2 bullets and both are relevant, both appear. If only 1 is relevant, include 1.
- This prevents the scenario where Claude is forced to include irrelevant bullets just to meet a minimum for a short role.

### `skills`

```json
{
  "technical": [
    { "skill": "SQL", "tags": ["data", "analytics", "technical"] }
  ],
  "domain": [
    { "skill": "Consumer Products", "tags": ["consumer", "B2C", "mobile"] }
  ],
  "methods": [
    { "skill": "Agile / Scrum", "tags": ["agile", "scrum", "sprint"] }
  ]
}
```

Claude reorders skills within each category to front-load JD-relevant ones. Claude does not add skills not in this list.

### `education`

```json
[
  {
    "id": "edu-1",
    "school": "University Name",
    "degree": "B.S. in Some Field",
    "graduation": "2023",
    "honors": null,
    "include_always": true
  }
]
```

### `projects` (optional — Claude includes 0 or 1)

```json
[
  {
    "id": "proj-1",
    "name": "Project Name",
    "context": "Personal project / Hackathon / etc.",
    "bullets": [
      {
        "id": "pb01",
        "text": "Built a web tool that does X, used by Y people",
        "tags": ["technical", "product", "web"],
        "has_metric": true,
        "metric_value": "Y users"
      }
    ],
    "include_when_tags": ["technical", "side project", "web"],
    "include_always": false
  }
]
```

---

## 6. Resume Tailoring

### Bullet tiers

Every bullet in a tailored resume falls into exactly one tier:

| Tier | Label | What it means | Limit per resume |
|------|-------|---------------|-----------------|
| Selected | `selected` | Verbatim from resume bank | Unlimited |
| Rephrased | `rephrased` | Light keyword/phrasing edits. Same facts, metrics, scope. | Unlimited |
| Derived | `derived` | New bullet synthesizing 1–3 existing bullets from the **same role**. Provably true given their combined evidence. | **Max 3** |

### What "derived" means

A derived bullet may:

1. **Combine scope from multiple bullets.** Bank has `b01` ("mobile feature for 2M+ users") and `b05` ("20+ user research interviews"). Derived: "Integrated user research insights from 20+ interviews into the product roadmap for a mobile feature serving 2M+ cardholders." True — both happened — but no single bullet says it.

2. **Reframe an achievement for a different audience.** Bank has `b06` ("predictive models... increasing offer acceptance rate by 8%"). Derived for a growth role: "Drove 8% improvement in conversion through predictive targeting models built in partnership with the data science team." Same facts, growth framing.

3. **Elevate implicit scope.** Bank has `b03` ("wrote PRDs for 3 major feature releases, aligning stakeholders across..."). Derived: "Managed end-to-end product lifecycle for 3 major releases, from requirements definition through cross-functional stakeholder alignment." Surfaces implicit lifecycle ownership.

### What "derived" must never do

- Invent a metric. If no source bullet contains a number, the derived bullet cannot contain one.
- Claim a tool the candidate didn't use.
- Upgrade ownership: "partnered with" cannot become "led" unless a source bullet establishes leadership.
- Invent a responsibility not evidenced by any source bullet.
- Merge experience across different companies. Derived bullets can only combine bullets from the same role.

### Claude's output schema per bullet

```json
{
  "source_ids": ["b01", "b05"],
  "tier": "derived",
  "text_final": "Integrated user research insights from 20+ interviews into the product roadmap for a mobile feature serving 2M+ cardholders",
  "derivation_rationale": "Combines user research scope from b05 with mobile feature scope from b01. Both occurred in the same role and timeframe. No new claims introduced.",
  "modification": "synthesized"
}
```

For `selected` bullets: `source_ids` is a single-element array, `tier` is `"selected"`, `derivation_rationale` is `null`, `modification` is `"none"`.

For `rephrased` bullets: `source_ids` is a single-element array, `tier` is `"rephrased"`, `derivation_rationale` is `null`, `modification` describes the change.

### Full tailored output schema

```json
{
  "summary_used": "sum-fintech",
  "summary_text_final": "Final summary text...",
  "experience": [
    {
      "role_id": "role-c1",
      "bullets_selected": [
        {
          "source_ids": ["b02"],
          "tier": "selected",
          "text_final": "...",
          "derivation_rationale": null,
          "modification": "none"
        }
      ]
    }
  ],
  "skills_order": ["SQL", "A/B Testing", "Figma"],
  "project_included": null,
  "gaps": ["JD asks for X — candidate has adjacent Y but not X specifically"]
}
```

### Validation

```python
def validate_tailored_output(tailored: dict, bank: dict) -> list[str]:
    errors = []
    bank_ids = set()
    for role in bank['experience']:
        for b in role['bullets']:
            bank_ids.add(b['id'])
    for proj in bank.get('projects', []):
        for b in proj['bullets']:
            bank_ids.add(b['id'])

    derived_count = 0

    for role in tailored['experience']:
        role_match = next(
            (r for r in bank['experience'] if r['role_id'] == role['role_id']),
            None
        )
        role_bullet_ids = set()
        if role_match:
            role_bullet_ids = {b['id'] for b in role_match['bullets']}

        for bullet in role['bullets_selected']:
            tier = bullet.get('tier', 'selected')
            sids = bullet.get('source_ids', [])

            for sid in sids:
                if sid not in bank_ids:
                    errors.append(f"INVALID source_id: {sid} not found in resume bank")

            if tier == 'derived':
                derived_count += 1
                if len(sids) < 1 or len(sids) > 3:
                    errors.append(
                        f"DERIVED bullet has {len(sids)} source_ids (must be 1-3): "
                        f"{bullet['text_final'][:60]}..."
                    )
                for sid in sids:
                    if sid not in role_bullet_ids:
                        errors.append(
                            f"DERIVED bullet references {sid} which belongs to a "
                            f"different role than {role['role_id']}"
                        )
                if not bullet.get('derivation_rationale'):
                    errors.append(
                        f"DERIVED bullet missing derivation_rationale: "
                        f"{bullet['text_final'][:60]}..."
                    )
            elif tier in ('rephrased', 'selected'):
                if len(sids) != 1:
                    errors.append(
                        f"{tier.upper()} bullet must have exactly 1 source_id, "
                        f"got {len(sids)}"
                    )

    if derived_count > 3:
        errors.append(f"EXCEEDED derived bullet limit: {derived_count}/3 allowed")

    return errors
```

If validation fails, the resume is still generated but flagged in the digest.

### Claude system prompt

```
You are a resume tailoring assistant. You will receive:
1. A structured resume bank (JSON) containing the candidate's real
   experience, bullets, skills, and projects — each with a unique ID.
2. A job description.

Your task: produce a tailored resume by SELECTING, REPHRASING, and
optionally DERIVING content from the resume bank.

BULLET TIERS:
- "selected": Use a bank bullet verbatim. Set tier to "selected",
  source_ids to [original_id], modification to "none".
- "rephrased": Lightly edit a bank bullet for keyword alignment.
  Facts, metrics, and scope must remain identical. Set tier to
  "rephrased", source_ids to [original_id], describe the change
  in modification.
- "derived": Synthesize a new bullet from 1-3 bank bullets IN THE
  SAME ROLE. The derived bullet must be provably true given the
  source bullets. Set tier to "derived", source_ids to the
  supporting bullet IDs, and write a derivation_rationale
  explaining how the sources support the new bullet.

DERIVED BULLET RULES:
- Maximum 3 derived bullets per resume.
- All source bullets must be from the same role.
- No invented metrics — only reuse numbers from source bullets.
- No invented tools, technologies, or methodologies.
- No upgrading ownership: "partnered" cannot become "led" unless
  a source bullet establishes leadership.
- No inventing responsibilities not evidenced by any source bullet.
- Every derived bullet must include a derivation_rationale.

BULLET COUNT RULES:
- For roles marked include_always: select 3-4 bullets, prioritizing
  JD relevance.
- For optional roles (include_always: false): include all available
  bullets if the role is selected. No minimum enforced.

GENERAL RULES:
- Choose the best summary variant; make minimal keyword edits.
- Reorder skills to front-load JD-relevant skills.
- Do NOT add skills not present in the skills section.
- If the JD requires experience the candidate lacks, note it in
  the "gaps" field — do NOT fabricate it.

Output format: JSON matching the schema provided.
```

### Claude model

`claude-sonnet-4-20250514`

---

## 7. Human Review Checkpoint

No automated approval. The pipeline generates everything and delivers it. You review, optionally edit, and manually submit.

**Per-job digest block**:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ROBINHOOD — PM1, Product Manager
Score: 88/100  |  Remote  |  Posted: Today
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

WHY THIS MATCHES:
Consumer fintech, PM1 title, strong keyword overlap (16/20),
your mobile + growth experience maps directly.

WHAT THE RESUME EMPHASIZES:
• [selected] Mobile feature launch bullet (b01) — unchanged
• [rephrased] A/B testing bullet (b02) — rephrased for "experimentation"
• [DERIVED from b01+b05] "Integrated user research insights from 20+
  interviews into the product roadmap for a mobile feature serving 2M+
  cardholders"
  -> Rationale: Combines user research scope (b05) with mobile feature
     scope (b01). Same role, same timeframe.

GAPS TO KNOW ABOUT:
• JD asks for "experience with crypto/trading products" — you don't
  have this. Your fintech + consumer experience is adjacent.
• JD prefers 3+ years — you have 2.5. Minor gap.

KEYWORD COVERAGE: 16/20 matched
Missing: "trading", "brokerage", "Series 7", "order flow"

JD SOURCE: full_fetch (1,247 words)

ACTIONS:
  View Job Posting    Download Resume (DOCX)
```

**Warning flag triggers** (job still included, grouped in "Review Carefully"):
- Score is 40–59
- Tailoring validation failed (any invalid `source_id`)
- More than 5 JD keywords unmatched
- YOE gap is ≥ 2 years
- JD source is `serpapi_snippet` with < 150 words ("⚠️ Short JD — resume may be less precisely tailored")
- Title matched experimental allowlist ("⚠️ Non-standard PM title — review carefully")
- Job passed location filter only via target-company override ("⚠️ Requires relocation — passed because [Company] is on your target list")

---

## 8. Output Format

### DOCX only

No PDF, no LaTeX. DOCX gives full control and ATS systems parse it reliably.

### Template spec

```
Font:           Times New Roman
Size:           Name 16pt bold, section headers 12pt bold, body 12pt
Margins:        0.7" all sides
Columns:        1 (single column — never two-column)
Sections:       Contact → Summary → Experience → Skills → Education → Projects (optional)
Section headers: ALL CAPS, bold, thin bottom border
Bullet style:   Standard round bullet (•), 0.25" indent
Line spacing:   1.0 within sections, 6pt space between bullets
Page target:    1 page hard constraint
```

### Section rules

- **Contact**: Name centered. One line: `email | phone | LinkedIn | location`. No address.
- **Summary**: 2–3 sentences. Chosen from summary variants, lightly edited for the role.
- **Experience**: Reverse chronological. Company bold, title italic, dates right-aligned. 3–4 bullets for `include_always` roles; all available bullets for optional roles. Each bullet leads with a strong action verb.
- **Skills**: Single line or two lines, comma-separated. Grouped: `Technical: ... | Domain: ... | Methods: ...`
- **Education**: One line. School, degree, graduation date. No GPA unless 3.7+.
- **Projects**: Optional. Max 1 project, 1–2 bullets. Include only if JD-relevant and space allows.

### File naming

Pattern: `{FirstName}_{LastName}_Resume_{Company}_{ShortTitle}.docx`

### Storage

```
data/resumes/{YYYY-MM-DD}/
├── FirstName_LastName_Resume_Robinhood_PM1.docx
├── FirstName_LastName_Resume_Stripe_APM.docx
└── ...
```

One flat folder per run date.

---

## 9. Notification

### Local-first design with optional Gmail

The pipeline always generates a local HTML digest file. If Gmail credentials are configured, it also sends the digest via email. Gmail is never a blocker — the pipeline succeeds even without it.

```python
def notify(digest_html: str, resume_paths: list[str], config: dict):
    """
    Always saves local HTML digest. Optionally sends via Gmail.
    """
    # Always: save local digest
    date_str = date.today().isoformat()
    digest_path = f"data/digests/{date_str}.html"
    save_file(digest_path, digest_html)

    # Always: open in browser for immediate review
    webbrowser.open(f"file://{os.path.abspath(digest_path)}")

    # Optional: send via Gmail if credentials exist
    if gmail_credentials_configured():
        try:
            send_gmail(
                subject=build_subject_line(date_str, resume_count=len(resume_paths)),
                html_body=digest_html,
                attachments=resume_paths,
            )
            log.info("Gmail digest sent successfully")
        except GmailError as e:
            log.warning(f"Gmail send failed (non-fatal): {e}")
            # Pipeline still succeeds — local digest is available


def gmail_credentials_configured() -> bool:
    """Check if Gmail OAuth credentials exist in data/ directory."""
    return os.path.exists("data/gmail_credentials.json")
```

**When it runs**: At the end of each pipeline run.

**Subject line** (Gmail): `PM Jobs — Mar 20 — 8 roles, 6 resumes ready`

**Email structure**:

1. **Header**: Run date, jobs found, resumes generated, pipeline health.
2. **Top Matches** (score ≥ 60): Company, title, score, location, match rationale, JD link, DOCX attached.
3. **Worth a Look** (score 40–59): Company, title, score, JD link. No resume.
4. **Reminder: Still Open**: Jobs with `status = 'resume_generated'` that are 7+ days old. Link to existing resume. No regeneration.
5. **Review Carefully**: Resumes with validation failures, short JDs, experimental titles, target-company relocation overrides, or large gaps.
6. **Footer**: Pipeline stats for monitoring and tuning:
   - Errors and skipped jobs with reasons
   - JD extraction stats (full fetch / snippet fallback / skipped)
   - Pass 1 filtering stats: "Pass 1 filtered: N jobs (out of M hard-filter survivors)" — for monitoring whether the 30/75 cutoff is useful
   - Query source stats: "NYC queries: N jobs, Remote query: M jobs" — for tracking whether the remote query is pulling its weight
   - Experimental title matches: count of jobs that matched only the experimental allowlist
   - Target-company relocation overrides: count of jobs that passed only via the target-company location bypass

**Resumes**: In Gmail, attached directly as DOCX files. In local HTML, linked as file:// paths to the `data/resumes/` directory.

**Format**: HTML rendered from a Jinja2 template. Gmail includes a plain-text fallback.

---

## 10. Architecture

### Pipeline flow

```
Manual trigger or cron
    |
    v
main.py (orchestrates all stages)
    |
    +-- discovery.py      SerpAPI, 4 queries, returns raw job list
    |       |
    +-- filtering.py      Hard filters (title, location, YOE, age)
    |       |
    +-- scoring.py        Pass 1: partial score on snippet-only fields (0-75)
    |       |              Cut jobs < 30/75
    +-- jd_extractor.py   Fetch full JD (fallback chain: URL → snippet → skip)
    |       |
    +-- scoring.py        Pass 2: add keyword overlap score (0-25)
    |       |              Final score 0-100. Apply thresholds.
    +-- tailoring.py      Claude API — select/rephrase/derive bullets
    |       |
    +-- doc_generator.py  DOCX generation from tailored JSON
    |       |
    +-- digest.py         Jinja2 HTML assembly (local file + optional email)
    |       |
    +-- notifier.py       Save local HTML, open browser, optionally send Gmail
    |       |
    +-- db.py             SQLite — dedup, run logs, status tracking
```

### Execution model: local-first

v1 runs locally via manual trigger or local cron. No GitHub Actions, no VPS, no cloud deployment.

```bash
# Manual run
python -m src.main

# Local cron (optional — add to your crontab)
0 7 * * 1-5 cd /path/to/pm-job-pipeline && python -m src.main
```

The architecture is compatible with future GitHub Actions deployment, but v1 does not optimize for it. Specifically:
- All config is file-based (easily converted to environment variables later).
- SQLite is local (can be swapped for a cloud DB or persisted as an Actions artifact later).
- Gmail OAuth credentials live in `data/` (can be converted to an Actions secret later).
- The pipeline is a single `main.py` entry point with no server or daemon.

### Tech stack (locked)

| Layer | Tool |
|-------|------|
| Language | Python 3.11+ |
| Job search | SerpAPI (`google_jobs` engine) |
| AI tailoring | Claude API (`claude-sonnet-4-20250514`) |
| Resume generation | python-docx (or docx-js — decide during build step 8) |
| Database | SQLite3 (stdlib) |
| Email templating | Jinja2 |
| Email sending | Gmail API (`google-api-python-client`) — optional |
| HTTP requests | httpx |
| HTML parsing | BeautifulSoup4 |
| Config | PyYAML |
| Scheduling | Local cron (v1). GitHub Actions (future). |

### `requirements.txt`

```
anthropic
google-api-python-client
google-auth-oauthlib
httpx
beautifulsoup4
python-docx
jinja2
pyyaml
```

---

## 11. Repo Structure

```
pm-job-pipeline/
├── .github/
│   └── workflows/
│       └── daily_run.yml              # Placeholder — not active in v1
├── config/
│   ├── config.yaml                    # COMMITTED — no personal data
│   └── config.example.yaml            # COMMITTED — identical structure, for new users
├── data/                              # GITIGNORED ENTIRELY
│   ├── master_resume/
│   │   ├── master_resume.docx
│   │   └── resume_bank.json
│   ├── resumes/
│   │   └── YYYY-MM-DD/
│   │       └── *.docx
│   ├── digests/
│   │   └── YYYY-MM-DD.html
│   └── gmail_credentials.json         # OAuth token — gitignored
├── db/                                # GITIGNORED
│   └── pipeline.db
├── docs/                              # COMMITTED — spec and design docs
│   └── spec.md                        # This file
├── examples/                          # COMMITTED — fake data for new users
│   ├── resume_bank.example.json
│   ├── sample_tailored_output.json
│   ├── sample_digest.html
│   └── sample_job_response.json
├── src/
│   ├── __init__.py
│   ├── main.py
│   ├── discovery.py
│   ├── filtering.py
│   ├── scoring.py
│   ├── jd_extractor.py
│   ├── resume_bank.py
│   ├── tailoring.py
│   ├── doc_generator.py
│   ├── digest.py
│   ├── notifier.py
│   ├── db.py
│   └── config.py
├── templates/
│   ├── resume.py                      # DOCX builder class
│   └── digest.html                    # Jinja2 email/digest template
├── tests/
│   ├── test_filtering.py
│   ├── test_scoring.py
│   ├── test_tailoring.py
│   └── fixtures/                      # COMMITTED — fake test data only
│       ├── fake_resume_bank.json
│       ├── fake_jd.md
│       └── fake_serpapi_response.json
├── .env                               # GITIGNORED — API keys
├── .env.example                       # COMMITTED — template with dummy values
├── .gitignore
├── requirements.txt
└── README.md
```

### Privacy rules

- `data/` and `db/` are entirely gitignored. All personal data lives there.
- `config/config.yaml` is committed. It contains only search parameters, scoring weights, and structural preferences — no PII, no API keys, no resume content.
- `examples/` uses a fully fictional persona ("Alex Sample").
- `tests/fixtures/` uses fake data. The test suite runs on a fresh clone without any personal files.
- API keys in `.env` (gitignored).

### `.gitignore`

```gitignore
# Personal data
data/
db/

# Secrets
.env
*.env
!.env.example

# Python
__pycache__/
*.pyc
*.pyo
*.egg-info/
dist/
build/
.venv/
venv/

# OS
.DS_Store
Thumbs.db

# IDE
.vscode/
.idea/
*.swp
*.swo

# Logs
logs/
*.log
```

### `.env.example`

```bash
SERPAPI_KEY=your_serpapi_key_here
ANTHROPIC_API_KEY=your_anthropic_key_here
GMAIL_SENDER_ADDRESS=you@gmail.com
```

---

## 12. Config (`config/config.yaml`)

```yaml
search:
  # Group A: NYC-localized queries
  nyc_queries:
    - "associate product manager"
    - "product manager entry level"
    - "APM product"
    - "junior product manager PM1"
    - "product manager"                # Broad — catches generic-titled PM roles
  # Group B: Remote-focused query (uses remote_search_location)
  remote_queries:
    - "product manager remote"
  serpapi_location: "New York, NY"     # Used for nyc_queries
  remote_search_location: "United States"  # Used for remote_queries
  date_filter: "3days"                 # 3-day window — matches hard filter freshness
  results_per_query: 10

location:
  target_metro: "new_york"
  metro_aliases:
    - "new york"
    - "nyc"
    - "manhattan"
    - "brooklyn"
    - "queens"
    - "jersey city"
    - "hoboken"
    - "new york, ny"
    - "ny metro"
  accept_remote: true
  accept_hybrid_in_metro: true
  accept_onsite_in_metro: true
  accept_relocation: false             # Global default. Target companies bypass this.

title_filter:
  # PM-adjacent titles to test for recall. Matches are flagged in digest.
  experimental_allowlist:
    - '\bproduct operations\b'
    - '\bgrowth analyst\b'
    - '\bproduct strategy\b'

scoring:
  pass1_cutoff: 30       # Out of 75. Monitor after 5 runs — lower or remove if <2 jobs cut/run.
  core_skills:
    - "product management"
    - "roadmap"
    - "A/B testing"
    - "user research"
    - "agile"
    - "scrum"
    - "cross-functional"
    - "stakeholder management"
    - "SQL"
    - "data analysis"
    - "KPIs"
    - "metrics"
    - "mobile"
    - "consumer"
    - "fintech"
    - "Jira"
    - "Figma"
    - "PRD"
    - "user stories"
    - "go-to-market"
  target_companies:
    - "Robinhood"
    - "Stripe"
    - "Square"
    - "Block"
    - "Cash App"
    - "Coinbase"
    - "Chime"
    - "SoFi"
    - "Plaid"
    - "Affirm"
    - "Duolingo"
    - "Spotify"
    - "Notion"
    - "Figma"
    - "Discord"
    - "DoorDash"
    - "Instacart"
    - "Airbnb"
    - "Reddit"
    - "Pinterest"
  thresholds:
    generate_resume: 60
    include_in_digest: 40

jd_extraction:
  min_word_count: 50             # Below this, skip the job
  short_jd_warning_threshold: 150 # Below this, flag in digest

tailoring:
  max_derived_bullets: 3
  max_bullets_per_role: 4
  min_bullets_per_role: 3        # Only enforced for include_always roles

output:
  resume_format: "docx"
  file_naming: "{first}_{last}_Resume_{company}_{title}"

notification:
  always_local_html: true        # Always generate and open local digest
  gmail_enabled: false           # Set to true after configuring Gmail OAuth
```

### Startup validation (`src/config.py`)

```python
REQUIRED_PATHS = {
    'data/master_resume/resume_bank.json': (
        'Resume bank not found. Run:\n'
        '  cp examples/resume_bank.example.json '
        'data/master_resume/resume_bank.json\n'
        'Then edit it with your real experience.'
    ),
    '.env': (
        'Environment file not found. Run:\n'
        '  cp .env.example .env\n'
        'Then add your API keys.'
    ),
}

def check_setup():
    missing = False
    for path, message in REQUIRED_PATHS.items():
        if not os.path.exists(path):
            print(f"Missing: {path}\n   {message}\n")
            missing = True
    if missing:
        sys.exit(1)
```

### New user setup

```bash
git clone https://github.com/you/pm-job-pipeline.git
cd pm-job-pipeline

mkdir -p data/master_resume data/resumes data/digests db

cp .env.example .env
# Edit .env with your real API keys

cp examples/resume_bank.example.json data/master_resume/resume_bank.json
# Edit with your real experience

python -m src.main --dry-run
```

---

## 13. Build Order

Build in this exact sequence. Each step has a concrete test before moving on.

| Step | Module | Test | Notes |
|------|--------|------|-------|
| 0 | **SerpAPI validation** | Sign up for free tier, run one real query, inspect response JSON | Do this before writing any code. Confirm field names, description format, whether apply URLs are present, and exact supported values for `chips` date filter (especially whether `date_posted:3days` works). Update `discovery.py` field mappings based on real response shape. |
| 1 | Repo setup, `config.yaml`, `requirements.txt` | `pip install -r requirements.txt` succeeds | |
| 2 | `resume_bank.py` — parse master resume into `resume_bank.json` | Every bullet has `id`, `tags`, `priority`. Verified by you. | Most important artifact. |
| 3 | `discovery.py` — SerpAPI call, returns normalized job list | Run all 6 queries (5 NYC + 1 remote). Confirm 15+ PM jobs come back. Verify remote query returns results not in NYC results. | Tag each result with `query_source` ('nyc' or 'remote'). Field mappings based on Step 0. |
| 4 | `filtering.py` — hard filters (including 3-pass title classification and target-company location override) | Feed 50+ raw jobs, confirm: senior roles drop, experimental titles are flagged not dropped, target-company jobs outside NYC pass with flag | |
| 5 | `scoring.py` — Pass 1 partial scoring | Manually verify Pass 1 scores for 5 known jobs feel right | |
| 6 | `jd_extractor.py` — fetch full JD with fallback chain | Test against 10 URLs. Confirm full-fetch, snippet-fallback, and skip behaviors all work. Log word counts. | |
| 7 | `scoring.py` — Pass 2 keyword scoring | Final scores for 5 jobs with full JDs feel right | |
| 8 | `tailoring.py` — Claude API call | Generate 3 tailored resumes, manually verify every bullet traces to the bank | |
| 9 | `doc_generator.py` — DOCX render | Open in Word, confirm formatting matches spec | |
| 10 | `main.py` + `db.py` — wire stages 3–9, dedup | Full end-to-end run, DOCX files appear in `data/resumes/` | |
| 11 | `digest.py` + `notifier.py` — local HTML digest | Run pipeline, digest opens in browser with correct content. Verify footer includes Pass 1 filtering stats, query source stats, and experimental/override counts. | |
| 12 | Gmail integration (optional) | If Gmail configured, receive actual email with attachments | Non-blocking. Skip if you want to iterate on other steps first. |
| 13 | Run 3–5 consecutive days | Fix bugs. Specifically monitor: (a) is Pass 1 cutoff filtering >2 jobs/run? (b) is the remote query adding unique jobs? (c) are experimental titles surfacing anything useful? (d) are target-company overrides firing? Tune based on findings. | |