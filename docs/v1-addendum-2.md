# PM Job Pipeline — v1 Spec Addendum #2

*Three revisions to the locked spec. These override the corresponding sections in the original spec and Addendum #1.*

---

## Revision 1: Resume Tailoring Scope — Derived Bullets

**This replaces the "What Claude IS allowed to do" and "What Claude is NOT allowed to do" sections from the original spec.**

### Three tiers of bullet output

Every bullet in a tailored resume falls into exactly one of three tiers:

| Tier | Label | What it means | Limit per resume |
|------|-------|---------------|-----------------|
| **Selected** | `selected` | A bullet copied verbatim from the resume bank. No changes. | Unlimited |
| **Rephrased** | `rephrased` | A bullet from the bank with light keyword or phrasing edits. Same facts, same metrics, same scope. | Unlimited |
| **Derived** | `derived` | A new bullet that synthesizes or reframes real experience from 1–3 existing bank bullets. Says something the bank bullets don't say individually, but that is provably true given their combined evidence. | **Max 3 per resume** |

### What "derived" means, precisely

A derived bullet is a new sentence that:

1. **Combines scope from multiple bullets.** Example: Bank has `b01` ("Led mobile feature launch for 2M+ users") and `b05` ("Conducted 20+ user research interviews"). A derived bullet could say: "Integrated user research insights from 20+ interviews into the product roadmap for a mobile feature serving 2M+ cardholders." This is true — you did both things, and they were connected — but no single bank bullet says this.

2. **Reframes an achievement for a different audience.** Example: Bank has `b06` ("Partnered with data science team to build predictive models for credit card offer targeting, increasing offer acceptance rate by 8%"). A derived bullet for a growth PM role could say: "Drove 8% improvement in conversion through predictive targeting models built in partnership with the data science team." Same facts, reframed around growth language.

3. **Elevates implicit scope.** Example: Bank has `b03` ("Defined product requirements and wrote PRDs for 3 major feature releases, aligning stakeholders across product, engineering, legal, and compliance"). A derived bullet could say: "Managed end-to-end product lifecycle for 3 major releases, from requirements definition through cross-functional stakeholder alignment across engineering, legal, and compliance." This surfaces "product lifecycle management" which is implicit in the original but not stated.

### What "derived" does NOT mean

A derived bullet must never:

- **Invent a metric.** If no source bullet contains a number, the derived bullet cannot contain a number.
- **Claim a tool you didn't use.** If no source bullet mentions Tableau, a derived bullet cannot mention Tableau.
- **Upgrade your role.** "Partnered with" cannot become "Led." "Contributed to" cannot become "Owned." "Supported" cannot become "Drove" — unless another source bullet establishes that you did drive it.
- **Invent a responsibility.** If no source bullet mentions pricing strategy, a derived bullet cannot claim you worked on pricing.
- **Merge experience across different companies.** Derived bullets can only combine bullets from the same role.

### Enforcement: the `source_ids` array

Selected and rephrased bullets map to exactly one `source_id`. Derived bullets map to 1–3 `source_ids` — the bank bullets that provide the evidence.

**Claude's output schema for a derived bullet:**

```json
{
  "source_ids": ["b01", "b05"],
  "tier": "derived",
  "text_final": "Integrated user research insights from 20+ interviews into the product roadmap for a mobile feature serving 2M+ cardholders",
  "derivation_rationale": "Combines the user research scope from b05 with the mobile feature scope from b01. Both occurred in the same role and timeframe. No new claims introduced.",
  "modification": "synthesized"
}
```

Compare to a selected bullet:

```json
{
  "source_ids": ["b02"],
  "tier": "selected",
  "text_final": "Designed and executed A/B testing program for onboarding flow, achieving a 15% improvement in 30-day activation rate",
  "derivation_rationale": null,
  "modification": "none"
}
```

And a rephrased bullet:

```json
{
  "source_ids": ["b04"],
  "tier": "rephrased",
  "text_final": "Built SQL dashboards to track feature adoption and funnel conversion, enabling data-informed backlog prioritization",
  "derivation_rationale": null,
  "modification": "rephrased: 'drop-off' → 'conversion' to match JD language"
}
```

### Validation logic update

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
        # Collect all bank bullets for this role to enforce same-role derivation
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

            # Every source_id must exist in the bank
            for sid in sids:
                if sid not in bank_ids:
                    errors.append(
                        f"INVALID source_id: {sid} not found in resume bank"
                    )

            if tier == 'derived':
                derived_count += 1

                # Derived bullets must have 1-3 source_ids
                if len(sids) < 1 or len(sids) > 3:
                    errors.append(
                        f"DERIVED bullet has {len(sids)} source_ids "
                        f"(must be 1-3): {bullet['text_final'][:60]}..."
                    )

                # All source_ids must belong to the same role
                for sid in sids:
                    if sid not in role_bullet_ids:
                        errors.append(
                            f"DERIVED bullet references {sid} which belongs "
                            f"to a different role than {role['role_id']}"
                        )

                # Must include a derivation rationale
                if not bullet.get('derivation_rationale'):
                    errors.append(
                        f"DERIVED bullet missing derivation_rationale: "
                        f"{bullet['text_final'][:60]}..."
                    )

            elif tier == 'rephrased':
                if len(sids) != 1:
                    errors.append(
                        f"REPHRASED bullet must have exactly 1 source_id, "
                        f"got {len(sids)}"
                    )

            elif tier == 'selected':
                if len(sids) != 1:
                    errors.append(
                        f"SELECTED bullet must have exactly 1 source_id, "
                        f"got {len(sids)}"
                    )

    # Hard cap: max 3 derived bullets per resume
    if derived_count > 3:
        errors.append(
            f"EXCEEDED derived bullet limit: {derived_count}/3 allowed"
        )

    return errors
```

### How derived bullets appear in the digest

Derived bullets get a visible marker in the review section so you know exactly which ones to scrutinize:

```
WHAT THE RESUME EMPHASIZES:
• [selected] Mobile feature launch bullet (b01) — unchanged
• [rephrased] A/B testing bullet (b02) — rephrased for "experimentation"
• [DERIVED from b01+b05] "Integrated user research insights from 20+
  interviews into the product roadmap for a mobile feature serving 2M+
  cardholders"
  ↳ Rationale: Combines user research scope (b05) with mobile feature
    scope (b01). Same role, same timeframe.
```

This gives you a 5-second visual scan: black-text bullets are safe, derived bullets are flagged for your attention.

### Updated Claude system prompt (replaces the original)

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

GENERAL RULES:
- Select 3-4 bullets per role, prioritizing JD relevance.
- Choose the best summary variant; make minimal keyword edits.
- Reorder skills to front-load JD-relevant skills.
- Do NOT add skills not present in the skills section.
- If the JD requires experience the candidate lacks, note it in
  the "gaps" field — do NOT fabricate it.

Output format: JSON matching the schema provided.
```

---

## Revision 2: Location Scope — New York (Configurable)

**This replaces the location hard-filter rule in the original spec and updates `config.yaml`.**

### The decision: v1 targets New York area only

The hard filter for location now checks against a configurable location profile, not a hardcoded metro area.

### Config structure

In `config/config.yaml`:

```yaml
location:
  # The metro area you're targeting. Used for hard filtering.
  target_metro: "new_york"

  # Matches: if ANY of these strings appear in the job's location field
  # (case-insensitive), the job is considered "in your metro."
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

  # Remote jobs always pass the location filter.
  accept_remote: true

  # Hybrid jobs pass only if they match a metro alias above.
  accept_hybrid_in_metro: true

  # On-site jobs pass only if they match a metro alias above.
  accept_onsite_in_metro: true

  # Jobs requiring relocation to another city. Set to false to reject.
  accept_relocation: false
```

### To switch cities later

Change `target_metro` and `metro_aliases`. Nothing else in the codebase changes. Example for San Francisco:

```yaml
location:
  target_metro: "san_francisco"
  metro_aliases:
    - "san francisco"
    - "sf"
    - "bay area"
    - "san jose"
    - "oakland"
    - "palo alto"
    - "mountain view"
    - "south bay"
    - "san francisco, ca"
  accept_remote: true
  accept_hybrid_in_metro: true
  accept_onsite_in_metro: true
  accept_relocation: false
```

### Updated hard-filter logic

```python
def passes_location_filter(job_location: str, config: dict) -> bool:
    """
    Determine if a job's location passes the configured location filter.
    job_location is the raw location string from SerpAPI.
    """
    loc = job_location.lower().strip()
    loc_config = config['location']

    # Remote always passes (if configured)
    if loc_config['accept_remote']:
        remote_signals = ['remote', 'work from home', 'anywhere', 'distributed']
        if any(signal in loc for signal in remote_signals):
            return True

    # Check metro match
    in_metro = any(alias in loc for alias in loc_config['metro_aliases'])

    # Hybrid in metro
    hybrid_signals = ['hybrid', 'flexible']
    is_hybrid = any(signal in loc for signal in hybrid_signals)
    if is_hybrid and in_metro and loc_config['accept_hybrid_in_metro']:
        return True

    # On-site in metro (no hybrid/remote signal, but location matches)
    if in_metro and loc_config['accept_onsite_in_metro']:
        return True

    # Relocation required (location doesn't match metro, not remote)
    if loc_config['accept_relocation']:
        return True

    return False
```

### Updated scoring rubric for location

The location score (0–10 points) now references the config:

```python
def score_location(job_location: str, config: dict) -> int:
    loc = job_location.lower().strip()
    metro_aliases = config['location']['metro_aliases']
    in_metro = any(alias in loc for alias in metro_aliases)

    remote_signals = ['remote', 'work from home', 'anywhere', 'distributed']
    is_remote = any(signal in loc for signal in remote_signals)

    hybrid_signals = ['hybrid', 'flexible']
    is_hybrid = any(signal in loc for signal in hybrid_signals)

    if is_remote and not in_metro:
        return 10  # Fully remote
    if is_remote and in_metro:
        return 10  # Remote-friendly, based in your metro — best case
    if is_hybrid and in_metro:
        return 8   # Hybrid in your metro
    if in_metro and not is_hybrid:
        return 6   # On-site in your metro
    if is_remote:
        return 10  # Catch-all remote
    return 2       # Passed filter somehow but not ideal
```

### SerpAPI query parameter update

The `location` parameter in SerpAPI queries is also configurable:

```yaml
search:
  queries:
    - "associate product manager"
    - "product manager entry level"
    - "APM product"
    - "junior product manager PM1"
  serpapi_location: "New York, NY"  # Used as SerpAPI's location param
  date_filter: "today"
  results_per_query: 10
```

To switch cities, change `serpapi_location` alongside `metro_aliases`. They stay in sync in the same config file.

---

## Revision 3: Public Repo Privacy and Data Separation

### The problem

The repo will be public on GitHub. Your master resume, resume bank, generated resumes, API keys, SQLite database, and email digests are all private. The codebase must be usable by anyone who clones it without containing any of your personal data.

### Design principle: all personal data lives in one directory, that directory is gitignored entirely

Every file that contains personal information lives under `data/` or is a dotenv file. The repo ships with example/sample files instead. A contributor clones the repo, copies the examples, fills in their own data, and runs the pipeline.

### Revised folder structure

```
pm-job-pipeline/
├── .github/
│   └── workflows/
│       └── daily_run.yml
├── config/
│   ├── config.yaml                    # ✅ COMMITTED — no personal data, just structure
│   └── config.example.yaml            # ✅ COMMITTED — identical to config.yaml for new users
├── data/                              # ❌ ENTIRE DIRECTORY GITIGNORED
│   ├── master_resume/
│   │   ├── master_resume.docx         # Your real resume
│   │   └── resume_bank.json           # Your parsed resume data
│   ├── resumes/                       # Generated tailored resumes
│   │   └── 2026-03-20/
│   │       └── *.docx
│   └── digests/                       # Email digest HTML
│       └── 2026-03-20.html
├── db/                                # ❌ GITIGNORED
│   └── pipeline.db                    # SQLite with your job data
├── examples/                          # ✅ COMMITTED — sample data for new users
│   ├── resume_bank.example.json       # Fake person, realistic structure
│   ├── sample_tailored_output.json    # What Claude's output looks like
│   ├── sample_digest.html             # What the email looks like
│   └── sample_job_response.json       # What SerpAPI returns
├── src/
│   ├── __init__.py                    # ✅ COMMITTED
│   ├── main.py                        # ✅ COMMITTED
│   ├── discovery.py                   # ✅ COMMITTED
│   ├── filtering.py                   # ✅ COMMITTED
│   ├── scoring.py                     # ✅ COMMITTED
│   ├── jd_extractor.py               # ✅ COMMITTED
│   ├── resume_bank.py                 # ✅ COMMITTED
│   ├── tailoring.py                   # ✅ COMMITTED
│   ├── doc_generator.py               # ✅ COMMITTED
│   ├── digest.py                      # ✅ COMMITTED
│   ├── notifier.py                    # ✅ COMMITTED
│   ├── db.py                          # ✅ COMMITTED
│   └── config.py                      # ✅ COMMITTED
├── templates/
│   ├── resume.py                      # ✅ COMMITTED
│   └── digest.html                    # ✅ COMMITTED
├── tests/
│   ├── test_filtering.py              # ✅ COMMITTED
│   ├── test_scoring.py                # ✅ COMMITTED
│   ├── test_tailoring.py              # ✅ COMMITTED
│   └── fixtures/                      # ✅ COMMITTED — fake test data
│       ├── fake_resume_bank.json
│       ├── fake_jd.md
│       └── fake_serpapi_response.json
├── .env                               # ❌ GITIGNORED — API keys
├── .env.example                       # ✅ COMMITTED — template with dummy values
├── .gitignore                         # ✅ COMMITTED
├── requirements.txt                   # ✅ COMMITTED
└── README.md                          # ✅ COMMITTED
```

### Exact `.gitignore`

```gitignore
# ── Personal data (NEVER commit) ──
data/
db/

# ── Secrets ──
.env
*.env
!.env.example

# ── Python ──
__pycache__/
*.pyc
*.pyo
*.egg-info/
dist/
build/
.venv/
venv/

# ── OS ──
.DS_Store
Thumbs.db

# ── IDE ──
.vscode/
.idea/
*.swp
*.swo

# ── Logs ──
logs/
*.log
```

### `.env.example` (committed)

```bash
# Copy this file to .env and fill in your real values.
# NEVER commit .env to the repo.

SERPAPI_KEY=your_serpapi_key_here
ANTHROPIC_API_KEY=your_anthropic_key_here

# Gmail API credentials — follow setup instructions in README
# OAuth credentials are stored in data/ which is gitignored
GMAIL_SENDER_ADDRESS=you@gmail.com
```

### `config/config.example.yaml` (committed, identical structure to `config.yaml`)

```yaml
# Copy this file to config.yaml and customize for your search.
# config.yaml is committed but contains NO personal data —
# only search parameters and structural preferences.

search:
  queries:
    - "associate product manager"
    - "product manager entry level"
    - "APM product"
    - "junior product manager PM1"
  serpapi_location: "New York, NY"
  date_filter: "today"
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
  accept_relocation: false

scoring:
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

tailoring:
  max_derived_bullets: 3
  max_bullets_per_role: 4
  min_bullets_per_role: 3

output:
  resume_format: "docx"
  file_naming: "{first}_{last}_Resume_{company}_{title}"
```

### `examples/resume_bank.example.json` (committed — fully fictional person)

```json
{
  "meta": {
    "version": "1.0",
    "last_updated": "2026-01-15",
    "candidate_name": "Alex Sample"
  },
  "contact": {
    "name": "Alex Sample",
    "email": "alex.sample@example.com",
    "phone": "555-000-0000",
    "linkedin": "linkedin.com/in/alexsample",
    "location": "New York, NY"
  },
  "summaries": [
    {
      "id": "sum-consumer",
      "focus": "consumer_product",
      "text": "Product Manager with 2 years of experience building consumer mobile products at a Fortune 500 retail company. Track record of launching features, running experiments, and improving engagement metrics.",
      "best_for_tags": ["consumer", "mobile", "B2C", "engagement", "growth"]
    },
    {
      "id": "sum-data",
      "focus": "data_driven",
      "text": "Data-driven Product Manager with 2 years of experience translating analytics into product decisions. Built and iterated consumer features using A/B testing, funnel analysis, and user research.",
      "best_for_tags": ["data", "analytics", "A/B testing", "metrics", "experimentation"]
    }
  ],
  "experience": [
    {
      "role_id": "role-ex1",
      "company": "Example Corp",
      "title": "Product Manager",
      "start_date": "2024-01",
      "end_date": "present",
      "location": "New York, NY",
      "include_always": true,
      "bullets": [
        {
          "id": "b01",
          "text": "Led development of a mobile checkout feature used by 500K+ monthly users, coordinating with engineering, design, and QA",
          "tags": ["mobile", "consumer", "launch", "cross-functional"],
          "has_metric": true,
          "metric_value": "500K+ users",
          "priority": 1
        },
        {
          "id": "b02",
          "text": "Ran A/B tests on onboarding flow, improving 7-day retention by 12%",
          "tags": ["A/B testing", "experimentation", "retention", "growth"],
          "has_metric": true,
          "metric_value": "12% improvement",
          "priority": 1
        },
        {
          "id": "b03",
          "text": "Wrote PRDs for 4 feature releases, aligning stakeholders across product, engineering, and marketing",
          "tags": ["PRD", "requirements", "stakeholder management", "roadmap"],
          "has_metric": true,
          "metric_value": "4 releases",
          "priority": 2
        },
        {
          "id": "b04",
          "text": "Built SQL dashboards to monitor conversion funnels and feature adoption, supporting weekly product reviews",
          "tags": ["SQL", "data analysis", "dashboards", "funnel", "analytics"],
          "has_metric": false,
          "metric_value": null,
          "priority": 2
        }
      ]
    }
  ],
  "skills": {
    "technical": [
      { "skill": "SQL", "tags": ["data", "analytics", "technical"] },
      { "skill": "A/B Testing", "tags": ["experimentation", "growth"] },
      { "skill": "Jira", "tags": ["agile", "tools"] },
      { "skill": "Figma", "tags": ["design", "prototyping"] }
    ],
    "domain": [
      { "skill": "Consumer Products", "tags": ["consumer", "B2C"] },
      { "skill": "Mobile Apps", "tags": ["mobile", "iOS", "Android"] }
    ],
    "methods": [
      { "skill": "Agile / Scrum", "tags": ["agile", "scrum"] },
      { "skill": "User Research", "tags": ["user research", "discovery"] },
      { "skill": "Roadmap Planning", "tags": ["roadmap", "strategy"] }
    ]
  },
  "education": [
    {
      "id": "edu-1",
      "school": "State University",
      "degree": "B.S. in Business Administration",
      "graduation": "2023",
      "honors": null,
      "include_always": true
    }
  ],
  "projects": [
    {
      "id": "proj-1",
      "name": "ShopTrack",
      "context": "Personal project",
      "bullets": [
        {
          "id": "pb01",
          "text": "Built a price-tracking web app with 200 active users, using Python and a simple recommendation engine",
          "tags": ["technical", "web", "side project", "consumer"],
          "has_metric": true,
          "metric_value": "200 users"
        }
      ],
      "include_when_tags": ["technical", "side project", "web"],
      "include_always": false
    }
  ]
}
```

### How `config.yaml` stays safe to commit

`config.yaml` contains only search parameters, scoring weights, and structural preferences. It does **not** contain:

- Your name, email, phone, or any PII
- API keys or secrets
- File paths to personal documents
- Any content from your resume

Your name appears only in `data/master_resume/resume_bank.json` (gitignored) and `.env` (gitignored). The config references structural keys like `target_companies` and `core_skills` — these are professional preferences, not PII, and are safe to commit publicly.

### Data initialization flow for new users

The README should instruct new users:

```bash
# 1. Clone the repo
git clone https://github.com/you/pm-job-pipeline.git
cd pm-job-pipeline

# 2. Create your personal data directories
mkdir -p data/master_resume data/resumes data/digests db

# 3. Set up secrets
cp .env.example .env
# Edit .env with your real API keys

# 4. Create your resume bank
# Option A: Copy the example and edit it
cp examples/resume_bank.example.json data/master_resume/resume_bank.json
# Then edit with your real experience

# Option B: Use the parser to generate from your DOCX
# Place your resume at data/master_resume/master_resume.docx
python -m src.resume_bank parse

# 5. Verify your setup
python -m src.main --dry-run
```

### Data initialization flow in code

`src/config.py` checks for required files at startup and gives clear errors:

```python
import os
import sys

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
            print(f"❌ Missing: {path}\n   {message}\n")
            missing = True
    if missing:
        sys.exit(1)
```

### Test fixtures use fake data only

All files in `tests/fixtures/` use the fictional "Alex Sample" persona. Tests never reference real resume data. The test suite runs against example data so CI works on a fresh clone without any personal files present.

```python
# tests/conftest.py
import pytest
import json

@pytest.fixture
def fake_resume_bank():
    with open('tests/fixtures/fake_resume_bank.json') as f:
        return json.load(f)

@pytest.fixture
def fake_jd():
    with open('tests/fixtures/fake_jd.md') as f:
        return f.read()
```

### GitHub Actions secrets

For the scheduled daily run, API keys are stored as GitHub Actions encrypted secrets, never in the repo:

```yaml
# .github/workflows/daily_run.yml
env:
  SERPAPI_KEY: ${{ secrets.SERPAPI_KEY }}
  ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
  GMAIL_CREDENTIALS: ${{ secrets.GMAIL_CREDENTIALS }}
```

The workflow checks out the repo, creates the `data/` and `db/` directories, downloads the resume bank from a private source (GitHub Actions secret or a private gist), runs the pipeline, and sends the digest. Generated resumes exist only in the ephemeral runner — they're sent via email and then discarded. Nothing personal is ever written to the repo.

### Summary of what is and isn't committed

| Content | Committed? | Location |
|---------|:---:|----------|
| All Python source code | ✅ | `src/` |
| Templates (DOCX builder, email HTML) | ✅ | `templates/` |
| Config structure (queries, scoring weights) | ✅ | `config/config.yaml` |
| Example resume bank (fake person) | ✅ | `examples/` |
| Test fixtures (fake data) | ✅ | `tests/fixtures/` |
| `.env.example` | ✅ | root |
| README with setup instructions | ✅ | root |
| GitHub Actions workflow | ✅ | `.github/` |
| Your real resume bank | ❌ | `data/master_resume/` |
| Your real resume DOCX | ❌ | `data/master_resume/` |
| Generated tailored resumes | ❌ | `data/resumes/` |
| Email digests | ❌ | `data/digests/` |
| SQLite database | ❌ | `db/` |
| API keys | ❌ | `.env` |
| Gmail OAuth credentials | ❌ | `data/` |