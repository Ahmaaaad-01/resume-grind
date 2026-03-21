# PM Job Pipeline — v1 Spec Addendum

*Three sections added to the locked v1 spec. Implementation-ready.*

---

## Addendum A: Deduplication and Freshness Behavior

### How to identify the same job across runs

Every job gets a **dedup key**: a normalized hash of three fields.

```python
import hashlib

def dedup_key(company: str, title: str, location: str) -> str:
    """
    Normalize and hash to create a stable identity for a job posting,
    even if it appears across multiple sources or with minor text variations.
    """
    norm = f"{company.lower().strip()}|{normalize_title(title)}|{location.lower().strip()}"
    return hashlib.sha256(norm.encode()).hexdigest()[:16]
```

**Why these three fields and not URL**: The same job posted on Lever, LinkedIn, and Google Jobs will have three different URLs but the same company + title + location. URL is stored but never used for dedup.

**Normalization rules applied before hashing**:

| Field | Normalization |
|-------|--------------|
| `company` | Lowercase, strip whitespace, remove Inc/LLC/Corp suffixes, collapse "Block, Inc." → "block" |
| `title` | Run through `normalize_title()` (defined in Addendum C), which strips seniority prefixes and normalizes PM variants. "Associate Product Manager, Growth" → "product manager growth" |
| `location` | Lowercase, strip whitespace, normalize "San Francisco, CA" and "SF Bay Area" → "san francisco ca". "Remote" stays "remote". |

### SQLite `jobs` table for tracking

```sql
CREATE TABLE IF NOT EXISTS jobs (
    dedup_key       TEXT PRIMARY KEY,
    title_raw       TEXT NOT NULL,
    title_normalized TEXT NOT NULL,
    company         TEXT NOT NULL,
    location        TEXT NOT NULL,
    url             TEXT NOT NULL,
    date_posted     TEXT,              -- ISO date from SerpAPI
    first_seen_run  TEXT NOT NULL,     -- ISO date of the pipeline run that first found this
    last_seen_run   TEXT NOT NULL,     -- ISO date of the most recent run where this appeared
    times_seen      INTEGER DEFAULT 1, -- how many runs this job appeared in
    score           REAL,
    status          TEXT DEFAULT 'new', -- new | scored | resume_generated | applied | skipped | expired
    resume_path     TEXT,              -- path to generated DOCX, if any
    jd_text         TEXT,
    score_breakdown TEXT,              -- JSON string
    gaps            TEXT,              -- JSON string from tailoring
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now'))
);

CREATE INDEX idx_status ON jobs(status);
CREATE INDEX idx_first_seen ON jobs(first_seen_run);
```

### Decision logic: skip, resurface, or regenerate

Every job in a given run's results gets checked against this table. The logic is a single function:

```python
def decide_action(job, existing_row) -> str:
    """
    Returns one of: 'process', 'skip', 'resurface', 'regenerate'
    """
    if existing_row is None:
        # Never seen before. Process it fully.
        return 'process'

    status = existing_row['status']
    days_since_first_seen = (today - existing_row['first_seen_run']).days
    times_seen = existing_row['times_seen']

    # CASE 1: Already applied or manually skipped. Never show again.
    if status in ('applied', 'skipped'):
        return 'skip'

    # CASE 2: Resume was generated but you haven't applied yet.
    # If it's been < 7 days since first seen, skip silently (you already have the resume).
    # If it's been 7+ days, resurface as a reminder — but don't regenerate.
    if status == 'resume_generated':
        if days_since_first_seen >= 7:
            return 'resurface'
        return 'skip'

    # CASE 3: Was scored but no resume generated (score was 40-59 "worth a look").
    # If it shows up again, that's a signal it's still open. Resurface it.
    if status == 'scored':
        return 'resurface'

    # CASE 4: Status is 'new' (somehow got saved but never processed — pipeline crash).
    # Reprocess it.
    if status == 'new':
        return 'process'

    # CASE 5: Expired (> 14 days old). Skip.
    if days_since_first_seen > 14:
        return 'skip'

    return 'skip'
```

**What each action means in the pipeline**:

| Action | What happens |
|--------|-------------|
| `process` | Full pipeline: score → extract JD → tailor resume → generate DOCX → include in digest |
| `skip` | Do nothing. Job does not appear in the digest. Update `last_seen_run` and `times_seen` in DB. |
| `resurface` | Include in digest under a "**Reminder: Still Open**" section. Link to the existing resume (no regeneration). One-line note: "You saw this on {first_seen_run}. Still open." |
| `regenerate` | Not used in v1. Reserved for a future case where the JD text changes significantly. |

### Handling reposted jobs

A "repost" is when a company takes down a posting and puts up a new one with the same or very similar title. This looks like a new job but isn't.

**How it manifests**: Same `dedup_key` but a new URL and a more recent `date_posted`.

**v1 behavior**: The dedup key catches it. The existing row is found, `last_seen_run` and `times_seen` are updated, and the URL is updated to the newest one. The decision logic above applies — if you already applied, it stays skipped; if you generated a resume but didn't apply, it resurfaces as a reminder after 7 days.

**Edge case — same company, slightly different title**: "Product Manager" vs. "Product Manager, Growth" at the same company. These produce different dedup keys and are treated as different jobs. This is correct — they likely are different roles. If they're truly duplicates, you'll catch it during human review (the digest will show both).

### When to regenerate a resume

**v1 rule: never automatically regenerate.** Once a resume is generated for a dedup key, it's final. Reasons:

1. Your master resume bank rarely changes mid-search.
2. JD text rarely changes meaningfully for the same posting.
3. Regeneration costs an API call and risks producing inconsistent versions.

**If you manually update your resume bank** (e.g., add a new bullet after a project ships), you can run a one-time command:

```bash
python -m src.main --regenerate-all-pending
```

This finds all jobs with `status = 'resume_generated'` where you haven't applied yet, and re-runs tailoring + doc generation with the updated bank. This is a manual trigger only, never automatic.

### Expiration

Jobs older than 14 days (based on `first_seen_run`) are automatically set to `status = 'expired'` at the start of each run. They never appear in digests again. This keeps the DB clean and the digest focused.

```python
def expire_old_jobs(db, cutoff_days=14):
    db.execute("""
        UPDATE jobs
        SET status = 'expired', updated_at = datetime('now')
        WHERE status NOT IN ('applied', 'skipped', 'expired')
        AND julianday('now') - julianday(first_seen_run) > ?
    """, (cutoff_days,))
```

---

## Addendum B: Exact `resume_bank.json` Schema

### Top-level structure

```json
{
  "meta": {
    "version": "1.0",
    "last_updated": "2026-03-20",
    "candidate_name": "Alex Sample"
  },
  "contact": { ... },
  "summaries": [ ... ],
  "experience": [ ... ],
  "skills": { ... },
  "education": [ ... ],
  "projects": [ ... ]
}
```

### `contact` (static, copied into every resume)

```json
{
  "name": "Alex Sample",
  "email": "alex@email.com",
  "phone": "555-123-4567",
  "linkedin": "linkedin.com/in/alexsample",
  "location": "Springfield, VA"
}
```

### `summaries` (array of variants — Claude picks one per job)

```json
[
  {
    "id": "sum-consumer",
    "focus": "consumer_product",
    "text": "Product Manager with 2.5 years of experience driving consumer mobile product strategy at Example Corp. Proven track record of launching user-facing features, running A/B tests, and improving key engagement metrics. Skilled at cross-functional collaboration with engineering, design, and data teams.",
    "best_for_tags": ["consumer", "mobile", "B2C", "engagement", "growth"]
  },
  {
    "id": "sum-fintech",
    "focus": "fintech",
    "text": "Consumer-focused Product Manager with 2.5 years of experience in financial services. Led credit card and mobile banking product initiatives at Example Corp, delivering measurable improvements in user activation and retention. Combines strong analytical skills with a user-first product sense.",
    "best_for_tags": ["fintech", "banking", "financial", "credit", "payments"]
  },
  {
    "id": "sum-data",
    "focus": "data_driven",
    "text": "Data-driven Product Manager with 2.5 years of experience translating user insights and quantitative analysis into product decisions. Built and iterated consumer features at Example Corp using A/B testing, funnel analysis, and cross-functional stakeholder alignment.",
    "best_for_tags": ["data", "analytics", "A/B testing", "metrics", "experimentation"]
  }
]
```

**Rules for summaries**:
- Minimum 2, maximum 5 variants.
- Each must be 2–3 sentences, under 350 characters.
- `best_for_tags` is what Claude uses to select — it picks the summary whose tags have the highest overlap with the JD's extracted keywords.
- Claude may swap 1–2 phrases to better match the JD (e.g., insert a company's product domain). It must not change claims or add experience.

### `experience` (array of roles, each with tagged bullets)

```json
[
  {
    "role_id": "role-c1",
    "company": "Example Corp",
    "title": "Product Manager",
    "start_date": "2023-09",
    "end_date": "present",
    "location": "McLean, VA / Remote",
    "include_always": true,
    "bullets": [
      {
        "id": "b01",
        "text": "Led end-to-end development of a mobile feature used by 2M+ cardholders, coordinating across engineering, design, and QA teams to deliver on a 12-week timeline",
        "tags": ["mobile", "consumer", "launch", "cross-functional", "coordination", "timeline"],
        "has_metric": true,
        "metric_value": "2M+ users",
        "priority": 1
      },
      {
        "id": "b02",
        "text": "Designed and executed A/B testing program for onboarding flow, achieving a 15% improvement in 30-day activation rate",
        "tags": ["A/B testing", "experimentation", "onboarding", "activation", "metrics", "growth"],
        "has_metric": true,
        "metric_value": "15% improvement",
        "priority": 1
      },
      {
        "id": "b03",
        "text": "Defined product requirements and wrote PRDs for 3 major feature releases, aligning stakeholders across product, engineering, legal, and compliance",
        "tags": ["PRD", "requirements", "stakeholder management", "compliance", "roadmap"],
        "has_metric": true,
        "metric_value": "3 releases",
        "priority": 2
      },
      {
        "id": "b04",
        "text": "Built SQL dashboards to monitor feature adoption and funnel drop-off, enabling data-informed prioritization of backlog items",
        "tags": ["SQL", "data analysis", "dashboards", "funnel", "prioritization", "analytics"],
        "has_metric": false,
        "metric_value": null,
        "priority": 2
      },
      {
        "id": "b05",
        "text": "Conducted 20+ user research interviews and synthesized findings into actionable product recommendations presented to senior leadership",
        "tags": ["user research", "interviews", "synthesis", "leadership", "communication"],
        "has_metric": true,
        "metric_value": "20+ interviews",
        "priority": 2
      },
      {
        "id": "b06",
        "text": "Partnered with data science team to build predictive models for credit card offer targeting, increasing offer acceptance rate by 8%",
        "tags": ["data science", "credit card", "targeting", "conversion", "fintech", "ML"],
        "has_metric": true,
        "metric_value": "8% increase",
        "priority": 3
      }
    ]
  }
]
```

**Field definitions for each bullet**:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | Yes | Globally unique. Pattern: `b{NN}`. This is the `source_id` Claude must reference in every tailored output. |
| `text` | string | Yes | The full bullet text exactly as it appears on your master resume. This is the source of truth. |
| `tags` | string[] | Yes | 3–8 lowercase keyword tags. Used for scoring keyword overlap and for Claude's selection logic. Tags should include: skills mentioned, themes, job function areas, and industry terms. |
| `has_metric` | bool | Yes | Whether the bullet contains a quantified result. Bullets with metrics are preferred during selection. |
| `metric_value` | string or null | Yes | The specific metric, for human reference. Not used by the pipeline programmatically. |
| `priority` | int (1–3) | Yes | Your pre-set priority. 1 = strongest bullet, always include if relevant. 2 = solid, include if space allows. 3 = situational, include only if it fills a specific JD keyword gap. |

**Field definitions for each role**:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `role_id` | string | Yes | Unique ID for the role. Pattern: `role-{xx}`. |
| `company` | string | Yes | Company name as it should appear on the resume. |
| `title` | string | Yes | Your exact title. Never altered by Claude. |
| `start_date` | string | Yes | YYYY-MM format. |
| `end_date` | string | Yes | YYYY-MM or "present". |
| `location` | string | Yes | As it should appear on the resume. |
| `include_always` | bool | Yes | If `true`, this role always appears (just with different bullet selection). If `false`, the role is optional and only included when relevant. |
| `bullets` | array | Yes | 3–8 bullets. Claude selects 3–4 per role for the tailored resume. |

### `skills` (structured for reordering)

```json
{
  "technical": [
    { "skill": "SQL", "tags": ["data", "analytics", "technical"] },
    { "skill": "A/B Testing", "tags": ["experimentation", "growth", "data"] },
    { "skill": "Jira", "tags": ["agile", "project management", "tools"] },
    { "skill": "Figma", "tags": ["design", "prototyping", "tools"] },
    { "skill": "Python (basic)", "tags": ["technical", "data", "scripting"] },
    { "skill": "Amplitude", "tags": ["analytics", "product analytics", "tools"] }
  ],
  "domain": [
    { "skill": "Consumer Products", "tags": ["consumer", "B2C", "mobile"] },
    { "skill": "Credit Cards", "tags": ["fintech", "financial", "credit"] },
    { "skill": "Mobile Apps", "tags": ["mobile", "iOS", "Android"] }
  ],
  "methods": [
    { "skill": "Agile / Scrum", "tags": ["agile", "scrum", "sprint"] },
    { "skill": "User Research", "tags": ["user research", "interviews", "discovery"] },
    { "skill": "Roadmap Planning", "tags": ["roadmap", "strategy", "prioritization"] },
    { "skill": "Go-to-Market Strategy", "tags": ["GTM", "launch", "go-to-market"] },
    { "skill": "Stakeholder Management", "tags": ["stakeholder", "communication", "leadership"] },
    { "skill": "Funnel Analysis", "tags": ["funnel", "conversion", "analytics", "growth"] }
  ]
}
```

Claude reorders skills within each category so that JD-relevant ones appear first. Claude does not add skills that aren't in this list.

### `education` (static, always included as-is)

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

### `projects` (optional section — Claude includes 0 or 1)

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
        "tags": ["technical", "product", "web", "user-facing"],
        "has_metric": true,
        "metric_value": "Y users"
      }
    ],
    "include_when_tags": ["technical", "side project", "web", "startup"],
    "include_always": false
  }
]
```

`include_when_tags`: Claude includes this project only if 2+ of these tags overlap with JD keywords. Otherwise, the Projects section is omitted to save space.

### How `source_id` tracing works end-to-end

**Step 1 — Claude outputs tailored content as JSON**:

```json
{
  "summary_used": "sum-fintech",
  "summary_text_final": "Consumer-focused Product Manager with 2.5 years...",
  "experience": [
    {
      "role_id": "role-c1",
      "bullets_selected": [
        {
          "source_id": "b01",
          "text_final": "Led end-to-end development of a mobile feature used by 2M+ cardholders, driving cross-functional collaboration across engineering, design, and QA",
          "modification": "rephrased for 'cross-functional collaboration' keyword"
        },
        {
          "source_id": "b02",
          "text_final": "Designed and executed A/B testing program for onboarding flow, achieving a 15% improvement in 30-day activation rate",
          "modification": "none"
        },
        {
          "source_id": "b04",
          "text_final": "Built SQL dashboards to track feature adoption and funnel conversion, enabling data-informed backlog prioritization",
          "modification": "rephrased: 'drop-off' → 'conversion' to match JD language"
        }
      ]
    }
  ],
  "skills_order": ["SQL", "A/B Testing", "Figma", ...],
  "project_included": null,
  "gaps": ["JD asks for experience with crypto trading — candidate has fintech but not crypto specifically"]
}
```

**Step 2 — Pipeline validates source_ids**:

```python
def validate_tailored_output(tailored: dict, bank: dict) -> list[str]:
    """
    Returns a list of validation errors. Empty list = all good.
    """
    errors = []
    bank_ids = set()
    for role in bank['experience']:
        for b in role['bullets']:
            bank_ids.add(b['id'])
    for proj in bank.get('projects', []):
        for b in proj['bullets']:
            bank_ids.add(b['id'])

    for role in tailored['experience']:
        for bullet in role['bullets_selected']:
            sid = bullet['source_id']
            if sid not in bank_ids:
                errors.append(f"INVALID source_id: {sid} not found in resume bank")

    summary_ids = {s['id'] for s in bank['summaries']}
    if tailored['summary_used'] not in summary_ids:
        errors.append(f"INVALID summary_id: {tailored['summary_used']}")

    return errors
```

**Step 3 — If validation fails**:

The resume is still generated (so you have something to work with), but it's flagged in the digest:

```
⚠️ TAILORING VERIFICATION FAILED
This resume contains 1 bullet that could not be traced to your
resume bank. Review carefully before submitting.
Invalid source_id: b99 — this bullet may have been generated by
Claude rather than selected from your experience.
```

You can then manually check whether Claude rephrased too aggressively or actually hallucinated.

---

## Addendum C: Title Normalization and Hard-Filter Logic

### The "PM" false positive problem

The string "PM" appears in many non-product-manager titles:

- **Project Manager** — different role entirely
- **Program Manager** — different role (common at Amazon, Google)
- **Property Manager** — real estate
- **Plant Manager** — manufacturing
- **Performance Marketing Manager** — marketing
- **PM Shift Lead**, **PM Cashier** — "PM" means afternoon/evening

Naive substring matching on "PM" will flood your results with garbage.

### Solution: Two-pass title classification

**Pass 1 — Denylist check** (reject immediately if any of these match):

```python
TITLE_DENYLIST = [
    # Seniority (case-insensitive exact word boundary matches)
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
    r'\bengineering manager\b', r'\bem\b',
    r'\btechnical program\b', r'\btpm\b',
]
```

**Pass 2 — Allowlist check** (must match at least one to proceed):

```python
TITLE_ALLOWLIST = [
    # Exact product manager variants (case-insensitive, word boundaries)
    r'\bproduct manager\b',
    r'\bassociate product manager\b',
    r'\bapm\b',                         # Only valid AFTER denylist clears "am/pm"
    r'\bpm[0-9]\b',                     # PM1, PM2, PM3
    r'\bpm i\b', r'\bpm ii\b',         # PM I, PM II (Roman numerals)
    r'\bjunior product manager\b',
    r'\bproduct management\b',
    r'\bproduct analyst\b',             # Often PM-adjacent entry-level
]
```

**Logic**:

```python
import re

def classify_title(raw_title: str) -> tuple[bool, str]:
    """
    Returns (passes_filter: bool, normalized_title: str).
    """
    t = raw_title.lower().strip()

    # Pass 1: Denylist — reject if any pattern matches
    for pattern in TITLE_DENYLIST:
        if re.search(pattern, t):
            return (False, t)

    # Pass 2: Allowlist — must match at least one
    for pattern in TITLE_ALLOWLIST:
        if re.search(pattern, t):
            return (True, normalize_title(t))

    # If neither denylist nor allowlist matched, reject.
    # This catches standalone "PM" with no qualifying context.
    return (False, t)


def normalize_title(title: str) -> str:
    """
    Produce a stable normalized form for dedup and display.
    """
    t = title.lower().strip()

    # Remove fluff prefixes/suffixes
    t = re.sub(r'^(junior|jr\.?|associate|entry[ -]level)\s+', '', t)
    t = re.sub(r'\s*[-–—,]\s*(remote|hybrid|contract|full[ -]time|intern).*$', '', t)
    t = re.sub(r'\s*\(.*?\)\s*', ' ', t)  # Remove parentheticals like "(Remote)"

    # Normalize PM variants to a common form
    t = re.sub(r'\bapm\b', 'product manager', t)
    t = re.sub(r'\bpm([0-9])\b', r'product manager \1', t)
    t = re.sub(r'\bpm (i|ii|iii)\b', r'product manager \1', t)

    # Collapse whitespace
    t = re.sub(r'\s+', ' ', t).strip()
    return t
```

### Edge-case examples with expected behavior

| Raw Title | Denylist Hit? | Allowlist Hit? | Result | Why |
|-----------|:---:|:---:|--------|-----|
| `Product Manager` | No | Yes → `\bproduct manager\b` | ✅ Pass | Core target |
| `Associate Product Manager` | No | Yes → `\bassociate product manager\b` | ✅ Pass | Core target |
| `PM1, Product Manager` | No | Yes → `\bpm[0-9]\b` | ✅ Pass | Exact Robinhood-style title |
| `Product Manager, Growth` | No | Yes → `\bproduct manager\b` | ✅ Pass | Specialty PM, still relevant |
| `Product Manager II` | No | Yes → `\bproduct manager\b` | ✅ Pass | Mid-level, but passes. Scoring will rank it by YOE fit. |
| `Junior Product Manager` | No | Yes → `\bjunior product manager\b` | ✅ Pass | Core target |
| `APM — Consumer` | No | Yes → `\bapm\b` | ✅ Pass | Core target |
| `Product Analyst` | No | Yes → `\bproduct analyst\b` | ✅ Pass | PM-adjacent entry role |
| `Senior Product Manager` | Yes → `\bsenior\b` | — | ❌ Reject | Too senior |
| `Sr. Product Manager, Payments` | Yes → `\bsr\b` | — | ❌ Reject | Too senior |
| `Lead Product Manager` | Yes → `\blead\b` | — | ❌ Reject | Too senior |
| `Group Product Manager` | Yes → `\bgroup\b` | — | ❌ Reject | Too senior |
| `Staff Product Manager` | Yes → `\bstaff\b` | — | ❌ Reject | Too senior |
| `Director of Product` | Yes → `\bdirector\b` | — | ❌ Reject | Too senior |
| `VP Product` | Yes → `\bvp\b` | — | ❌ Reject | Too senior |
| `Project Manager` | Yes → `\bproject manager\b` | — | ❌ Reject | Wrong role |
| `Technical Program Manager` | Yes → `\btechnical program\b` | — | ❌ Reject | Wrong role |
| `Program Manager, Operations` | Yes → `\bprogram manager\b` | — | ❌ Reject | Wrong role |
| `PM Shift Lead — Retail` | Yes → `\bpm shift\b` | — | ❌ Reject | "PM" means afternoon |
| `Property Manager` | Yes → `\bproperty manager\b` | — | ❌ Reject | Real estate |
| `PM` (standalone, no context) | No | No (no allowlist match) | ❌ Reject | Ambiguous — could be anything. Rejected by default. |
| `Marketing Manager` | Yes → `\bmarketing manager\b` | — | ❌ Reject | Wrong function |
| `Performance Marketing PM` | Yes → `\bperformance marketing\b` | — | ❌ Reject | Marketing, not product |
| `Engineering Manager` | Yes → `\bengineering manager\b` | — | ❌ Reject | Wrong function |
| `TPM — Cloud Infrastructure` | Yes → `\btpm\b` | — | ❌ Reject | Technical program manager |
| `Product Manager / Project Manager` | Yes → `\bproject manager\b` | — | ❌ Reject | Ambiguous dual-title, denylist fires first. Safe to reject — if it's a real PM role, it'll show up under a cleaner title elsewhere. |
| `Product Management Intern` | No | Yes → `\bproduct management\b` | ✅ Pass | Could be relevant. Scoring will rank it low if it's literally an internship (YOE field will say "0" or "intern"). |

### Key design principles behind this logic

1. **Denylist runs first.** A title like "Senior Associate Product Manager" gets caught by `\bsenior\b` before the allowlist ever sees "product manager." This is intentional — seniority always wins.

2. **Standalone "PM" is rejected by default.** If neither list matches, the job is rejected. This means a job titled just "PM" with no other context gets dropped. This is the right call — the ambiguity risk is too high. Real product manager postings almost always include the full phrase.

3. **"Product Manager II" passes the filter but gets scored.** The hard filter only blocks clearly wrong titles. Whether "PM II" is too senior for you is a scoring question (the YOE factor in the rubric will handle it), not a filter question. This prevents you from missing roles where "II" means 2 years of experience, not 5+.

4. **Dual titles are rejected.** "Product Manager / Project Manager" fails because the denylist catches "project manager." This is conservative but safe — if the company genuinely means product management, they'll have a separate clean posting.

5. **Order of operations**: denylist → allowlist → default reject. No exceptions, no fuzzy matching, no AI in the loop. This is a deterministic function you can unit-test with the exact table above.

### How this integrates with the scoring rubric

The title-match score (0–25 points) from the v1 spec uses the **pre-normalization raw title** for precision scoring:

```python
def score_title(raw_title: str) -> int:
    t = raw_title.lower().strip()

    # Exact early-career signals → max points
    if any(re.search(p, t) for p in [
        r'\bapm\b', r'\bassociate product manager\b',
        r'\bpm1\b', r'\bpm i\b', r'\bjunior product manager\b'
    ]):
        return 25

    # Generic "product manager" with no seniority → strong match
    if re.search(r'\bproduct manager\b', t):
        return 20

    # Specialty variants
    if re.search(r'\b(growth|platform|core|payments)\s+pm\b', t):
        return 15

    # PM-adjacent
    if re.search(r'\bproduct analyst\b', t):
        return 12

    # Passed the hard filter but doesn't match well
    return 10
```

This means a "PM1" at Robinhood gets 25/25, a generic "Product Manager" gets 20/25, and a "Product Analyst" gets 12/25 — before any other factors are scored.