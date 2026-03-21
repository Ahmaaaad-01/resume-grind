# PM Job Pipeline — v1 Locked Spec

*No optionality. One decision per layer. Build this.*

---

## 1. Source Strategy: SerpAPI Google Jobs — Single Source, Single Query Set

**The decision**: SerpAPI's Google Jobs endpoint is the only job source in v1. No RSS feeds, no Wellfound, no Lever/Greenhouse direct scraping, no secondary sources. Google Jobs already aggregates from LinkedIn, Indeed, Glassdoor, Lever, Greenhouse, and company career pages. One source covers 90%+ of postings.

**Exact queries** (run all 4 every execution):

```python
QUERIES = [
    "associate product manager",
    "product manager entry level",
    "APM product",
    "junior product manager PM1",
]
```

**Fixed parameters per query**:

```python
SEARCH_PARAMS = {
    "engine": "google_jobs",
    "location": "United States",
    "chips": "date_posted:today",   # Only jobs posted in the last 24 hours
    "num": 10,                       # Max results per query
}
```

**Why this and nothing else**: SerpAPI returns structured JSON with title, company, location, posting date, job description snippet, and apply link. No HTML parsing needed. The free tier gives 100 searches/month — that's 25 daily runs at 4 queries each, which covers a full month of weekday runs. You don't need a paid tier for v1.

**Total jobs per run**: Up to 40 raw results (4 queries × 10), which dedup and filter down to 5–15 actionable jobs.

---

## 2. Target Role Criteria: Exact Hard Filters

These are binary pass/fail. A job that fails any one of these is discarded before scoring.

| Filter | Rule | Rationale |
|--------|------|-----------|
| **Title** | Must contain one of: `product manager`, `PM`, `APM`, `associate product manager`, `PM1`, `PM I` (case-insensitive). Must NOT contain: `senior`, `staff`, `principal`, `director`, `VP`, `head of`, `lead`, `group`, `program manager`, `project manager`, `marketing` | Exclude senior roles and non-PM roles that share keywords |
| **YOE** | If JD states a minimum, must be ≤ 4 years. If JD states "5+ years" or higher, discard. If no YOE mentioned, pass. | You have ~2.5 years. Up to 4 is a reasonable stretch. |
| **Location** | Must be one of: `Remote`, `Hybrid` in DC/NoVA/MD metro, or any US location if listed as remote-eligible. Discard international-only or on-site-only outside your metro. | You're in Springfield, VA. Remote and local hybrid are viable. |
| **Posting age** | ≤ 3 days old (based on SerpAPI's `detected_extensions.posted_at` field). Anything older is stale. | You want to be early. |
| **Language** | JD must be in English | Practical filter |

**Implementation**: A single Python function `passes_hard_filters(job) -> bool`. No AI needed — pure string matching and date math.

---

## 3. Scoring Rubric: Fixed Weights, No Semantic AI in v1

After hard filters, surviving jobs get a deterministic score. No Claude call for scoring in v1 — it's pure rules-based to keep it fast and free.

| Factor | Points | How to calculate |
|--------|--------|-----------------|
| **Title precision** | 0–25 | `APM` / `associate product manager` / `PM1` = 25. `product manager` (generic) = 20. `growth PM` / `platform PM` = 15. Anything else that passed hard filter = 10. |
| **YOE fit** | 0–20 | 0–2 years required = 20. 1–3 years = 18. 2–4 years = 14. "not specified" = 12. 3–5 years = 8. |
| **Remote/location** | 0–10 | Remote = 10. Hybrid in your metro = 8. On-site in your metro = 6. Remote-eligible but another city = 5. Relocation = 2. |
| **Keyword overlap** | 0–25 | Count how many of your 20 core skills (defined below) appear in the JD snippet. Score = `(match_count / 20) × 25`. |
| **Company on target list** | 0–10 | On your target list = 10. Tech/fintech company = 6. Other = 3. |
| **Posting recency** | 0–10 | Today = 10. Yesterday = 7. 2 days ago = 4. 3 days ago = 2. |

**Total**: 100 points.

**Your 20 core skills** (used for keyword overlap scoring):

```python
CORE_SKILLS = [
    "product management", "roadmap", "A/B testing", "user research",
    "agile", "scrum", "cross-functional", "stakeholder management",
    "SQL", "data analysis", "KPIs", "metrics", "mobile",
    "consumer", "fintech", "Jira", "Figma", "PRD",
    "user stories", "go-to-market"
]
```

**Your target company list** (v1 — add/remove in config):

```python
TARGET_COMPANIES = [
    "Robinhood", "Stripe", "Square", "Block", "Cash App",
    "Coinbase", "Chime", "SoFi", "Plaid", "Affirm",
    "Duolingo", "Spotify", "Notion", "Figma", "Discord",
    "DoorDash", "Instacart", "Airbnb", "Reddit", "Pinterest"
]
```

**Thresholds**:
- **≥ 60**: Generate a tailored resume. Include in digest.
- **40–59**: Include in digest as "worth a look" with link only. No resume generated.
- **< 40**: Discard silently.

---

## 4. Resume Tailoring Scope: What Claude Can and Cannot Do

### What Claude IS allowed to do:

1. **Select** which bullets from your master resume bank to include (drop irrelevant ones).
2. **Reorder** bullets within a role to lead with the most relevant.
3. **Rephrase** a bullet to naturally incorporate a JD keyword, provided the meaning and facts stay identical. Example: "Worked with engineering and design teams" → "Led cross-functional collaboration with engineering and design teams" — only if you actually led it.
4. **Choose** which summary variant to use and make light keyword edits (swap 1–2 phrases).
5. **Reorder** the skills section to front-load JD-relevant skills.
6. **Select** which optional projects to include (if any).

### What Claude is NOT allowed to do:

1. **Invent** any new bullet, accomplishment, project, or responsibility.
2. **Change metrics** — if your bullet says "15% increase," it stays "15% increase." No rounding up, no inflating.
3. **Add skills you don't have** to the skills section.
4. **Claim a title or role you didn't hold.**
5. **Add company names, tools, or technologies you didn't use.**
6. **Generate a "Relevant Coursework" or "Certifications" entry you don't have.**
7. **Merge bullets** from different roles into one (creates a false impression).

### Enforcement mechanism:

Claude's output is a JSON object where every bullet has a `source_id` linking back to the master resume bank. The pipeline validates that every `source_id` exists in the bank. If Claude outputs a bullet with no valid source, it gets flagged and that resume goes to the "needs manual review" bucket instead of the digest.

### The exact Claude system prompt for tailoring:

```
You are a resume tailoring assistant. You will receive:
1. A structured resume bank (JSON) containing the candidate's real experience, bullets, skills, and projects — each with a unique ID.
2. A job description.

Your task: produce a tailored resume by SELECTING and REORDERING content from the resume bank. You may lightly rephrase bullets for keyword alignment, but you must not change facts, metrics, or substance.

Rules:
- Every bullet in your output MUST include a "source_id" matching a bullet in the resume bank.
- Do NOT invent new accomplishments, metrics, or skills.
- Do NOT merge bullets from different roles.
- Do NOT add skills the candidate doesn't have.
- Select 3-4 bullets per role, prioritizing relevance to this specific JD.
- Choose the best summary variant and make minimal keyword edits.
- Reorder the skills section to front-load JD-relevant skills.
- If the JD requires experience the candidate doesn't have, note it in a "gaps" field — do NOT fabricate it.

Output format: JSON matching the schema provided.
```

---

## 5. Human Review Checkpoint: In the Digest, Before You Apply

**The decision**: There is no automated approval step. Every resume goes through you. The pipeline generates everything and delivers it. You review, optionally edit, and manually submit.

**What the review surface looks like** (per job, inside the email digest):

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ROBINHOOD — PM1, Product Manager
Score: 88/100  |  Remote  |  Posted: Today
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

WHY THIS MATCHES:
Consumer fintech, PM1 title, strong keyword overlap (16/20),
your mobile + growth experience maps directly.

WHAT THE RESUME EMPHASIZES:
• Mobile feature launch bullet (b1) — rephrased for "user growth"
• A/B testing + metrics bullet (b2) — unchanged
• Cross-functional leadership bullet (b5) — rephrased for "roadmap"
• Data analysis bullet (b8) — unchanged

GAPS TO KNOW ABOUT:
• JD asks for "experience with crypto/trading products" — you
  don't have this. Your fintech + consumer experience is adjacent.
• JD prefers 3+ years — you have 2.5. Minor gap.

KEYWORD COVERAGE: 16/20 matched
Missing: "trading", "brokerage", "Series 7", "order flow"

ACTIONS:
🔗 View Job Posting    📄 Download Resume (DOCX)
```

**What you do**:
1. Read the match summary (10 seconds per job).
2. Click to download the DOCX if you want to apply.
3. Open it, skim the bullets, make any final tweaks (1–2 minutes).
4. Submit via the job link.

**What triggers a ⚠️ warning flag**:
- Score is 40–59 (borderline match)
- Claude couldn't find a `source_id` for any bullet (tailoring verification failed)
- More than 5 JD keywords are unmatched
- YOE gap is ≥ 2 years

Jobs with warnings are still included but grouped in a separate "Review Carefully" section at the bottom of the digest.

---

## 6. Output Format: DOCX Only, One Template, Fixed Structure

### The decision: DOCX is the only output format in v1.

No PDF generation. No LaTeX. Reasons: most application portals accept DOCX, ATS systems parse DOCX more reliably than PDF, and `python-docx` gives you full control without extra dependencies.

### Template spec:

```
Font:           Calibri
Size:           Name 14pt bold, section headers 11pt bold, body 10.5pt
Margins:        0.7" all sides
Columns:        1 (single column — never two-column)
Sections:       Contact → Summary → Experience → Skills → Education → Projects (optional)
Section headers: ALL CAPS, bold, with a thin bottom border
Bullet style:   Standard round bullet (•), 0.25" indent
Line spacing:   1.0 within sections, 6pt space between bullets
Page target:    1 page (hard constraint — Claude must select fewer bullets if needed)
```

### Section rules:

**Contact**: Name centered, then one line with email | phone | LinkedIn | location. No address.

**Summary**: 2–3 sentences. Chosen from summary variants, lightly edited for the specific role.

**Experience**: Reverse chronological. Company name bold, title italic, dates right-aligned. 3–4 bullets per role. Each bullet starts with a strong action verb and includes a metric where possible.

**Skills**: Single line or two lines. Comma-separated. Grouped as: `Technical: ... | Domain: ... | Tools: ...`

**Education**: School, degree, graduation date. One line. No GPA unless it's 3.7+.

**Projects**: Optional. Include only if relevant to the JD and there's space. Max 1 project, 1–2 bullets.

### File naming convention:

```
Alex_Sample_Resume_Robinhood_PM1.docx
Alex_Sample_Resume_Stripe_APM.docx
```

Pattern: `{FirstName}_{LastName}_Resume_{Company}_{ShortTitle}.docx`

### Where files live:

```
data/resumes/2026-03-20/
├── Alex_Sample_Resume_Robinhood_PM1.docx
├── Alex_Sample_Resume_Stripe_APM.docx
├── Alex_Sample_Resume_Duolingo_GrowthPM.docx
└── ...
```

One flat folder per run date. No nested subfolders per company in v1.

---

## 7. Notification: Gmail Digest — One Email, One Format

### The decision: One email per run via Gmail API. No Slack, no local-only output, no Google Drive sync in v1.

**When it sends**: At the end of each pipeline run. If run via GitHub Actions cron at 7:00 AM ET, you'll have it by ~7:05 AM.

**Subject line**: `PM Jobs — Mar 20 — 8 roles, 6 resumes ready`

**Email structure**:

1. **Header**: Run date, jobs found, resumes generated, pipeline health.
2. **Top Matches** (score ≥ 60, resume generated): Table with company, title, score, location, match rationale (1 line), JD link, and resume attached or linked.
3. **Worth a Look** (score 40–59, no resume): Table with company, title, score, JD link. You decide if any are worth manual effort.
4. **Review Carefully** (warnings flagged): Any resume with verification issues or large gaps.
5. **Footer**: Errors, skipped jobs (with reasons), API cost estimate.

**Resume delivery**: Resumes attached directly to the email as DOCX files. Gmail supports up to 25MB of attachments — even 15 DOCX resumes at ~50KB each is under 1MB. No external links needed.

**Email format**: HTML (rendered from a Jinja2 template). Plain-text fallback included.

---

## 8. v1 Architecture Diagram

```
┌─────────────────────────────────────────────────────────┐
│                    GitHub Actions Cron                    │
│                  (7:00 AM ET, Mon–Fri)                   │
└──────────────────────┬──────────────────────────────────┘
                       │ triggers
                       ▼
┌─────────────────────────────────────────────────────────┐
│                     main.py                              │
│              (orchestrates all stages)                    │
└──────────────────────┬──────────────────────────────────┘
                       │
          ┌────────────┼────────────┬──────────────┐
          ▼            ▼            ▼              ▼
   ┌────────────┐ ┌─────────┐ ┌─────────┐  ┌───────────┐
   │ discovery.py│ │filter.py│ │score.py │  │jd_extract │
   │ (SerpAPI)  │→│(hard    │→│(rubric  │→ │(fetch JD  │
   │ 4 queries  │ │ filters)│ │ 0-100)  │  │ text)     │
   └────────────┘ └─────────┘ └─────────┘  └─────┬─────┘
                                                   │
                                                   ▼
                                           ┌──────────────┐
                                           │ tailor.py    │
                                           │ (Claude API) │
                                           │ select+rephrase│
                                           │ from bank    │
                                           └──────┬───────┘
                                                   │
                                                   ▼
                                           ┌──────────────┐
                                           │ doc_gen.py   │
                                           │ (python-docx)│
                                           │ → .docx      │
                                           └──────┬───────┘
                                                   │
                                                   ▼
                                           ┌──────────────┐
                                           │ digest.py    │
                                           │ (Jinja2 HTML)│
                                           └──────┬───────┘
                                                   │
                                                   ▼
                                           ┌──────────────┐
                                           │ notify.py    │
                                           │ (Gmail API)  │
                                           │ email+attach │
                                           └──────┬───────┘
                                                   │
                                                   ▼
                                           ┌──────────────┐
                                           │ db.py        │
                                           │ (SQLite)     │
                                           │ log run,     │
                                           │ track seen   │
                                           └──────────────┘

Data stores:
  - data/master_resume/resume_bank.json  (your parsed resume — static)
  - db/pipeline.db                        (SQLite — jobs seen, run logs)
  - data/resumes/{date}/                  (generated DOCX files)
  - config/config.yaml                    (queries, skills, target cos)
```

### The exact tech stack (no alternatives):

| Layer | Tool | Version |
|-------|------|---------|
| Language | Python | 3.11+ |
| Job search | SerpAPI | google_jobs engine |
| AI tailoring | Claude API | claude-sonnet-4-20250514 |
| Resume generation | python-docx | latest |
| Database | SQLite3 | stdlib |
| Email templating | Jinja2 | latest |
| Email sending | Gmail API (google-api-python-client) | v2 |
| HTTP requests | httpx | latest |
| HTML parsing (JD extraction) | BeautifulSoup4 | latest |
| Config | PyYAML | latest |
| Scheduling | GitHub Actions | cron |
| Dev/build tool | Claude Code | — |

### Dependencies (requirements.txt):

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

## 9. Repo Structure (Exact)

```
pm-job-pipeline/
├── .github/
│   └── workflows/
│       └── daily_run.yml          # GitHub Actions cron config
├── config/
│   ├── config.yaml                # Queries, skills, target companies, thresholds
│   └── .env.example               # Template for API keys
├── data/
│   ├── master_resume/
│   │   ├── master_resume.docx     # Your source resume
│   │   └── resume_bank.json       # Parsed structured data
│   ├── resumes/                   # Generated resumes (by date)
│   └── digests/                   # Saved digest HTML (by date)
├── db/
│   └── pipeline.db                # SQLite (gitignored, created on first run)
├── src/
│   ├── __init__.py
│   ├── main.py                    # Entry point
│   ├── discovery.py               # SerpAPI job search
│   ├── filtering.py               # Hard filters
│   ├── scoring.py                 # Rubric scoring
│   ├── jd_extractor.py            # Fetch + clean full JDs
│   ├── resume_bank.py             # Parse master resume → JSON
│   ├── tailoring.py               # Claude API resume tailoring
│   ├── doc_generator.py           # python-docx DOCX builder
│   ├── digest.py                  # Jinja2 email assembly
│   ├── notifier.py                # Gmail API send
│   ├── db.py                      # SQLite CRUD
│   └── config.py                  # Load config.yaml + .env
├── templates/
│   ├── resume.py                  # DOCX template (python-docx builder class)
│   └── digest.html                # Email HTML Jinja2 template
├── tests/
│   ├── test_filtering.py
│   ├── test_scoring.py
│   └── test_tailoring.py
├── .env                           # API keys (gitignored)
├── .gitignore
├── requirements.txt
└── README.md
```

**Gitignored**: `.env`, `db/pipeline.db`, `data/resumes/`, `data/digests/`, `logs/`.

---

## 10. Build Order (Exact Sequence)

**Step 1**: Create repo, install deps, write `config.yaml` with queries/skills/companies.

**Step 2**: Build `resume_bank.py` — parse your master resume into `resume_bank.json`. This is the most important artifact. Every bullet tagged, ID'd, and verified by you.

**Step 3**: Build `discovery.py` — call SerpAPI, return normalized job list. Test: run it, confirm 10+ PM jobs come back.

**Step 4**: Build `filtering.py` — apply hard filters. Test: feed in 40 raw jobs, confirm senior/stale/irrelevant ones drop.

**Step 5**: Build `scoring.py` — apply rubric. Test: manually verify scores for 5 known jobs feel right.

**Step 6**: Build `jd_extractor.py` — fetch full JD text from URLs. Test: confirm text extraction works for Lever, Greenhouse, and generic career pages.

**Step 7**: Build `tailoring.py` — Claude API call with the locked system prompt. Test: generate 3 tailored resumes, manually verify every bullet traces back to the bank.

**Step 8**: Build `doc_generator.py` — render tailored JSON into DOCX. Test: open in Word, confirm formatting matches the spec.

**Step 9**: Build `main.py` — wire stages 3–8 together. Build `db.py` for dedup. Test: full end-to-end run, files appear in `data/resumes/`.

**Step 10**: Build `digest.py` + `notifier.py` — assemble HTML digest, send via Gmail. Test: receive an actual email with the right content and attachments.

**Step 11**: Set up `.github/workflows/daily_run.yml` for cron scheduling. Test: trigger manually, confirm it runs and sends the digest.

**Step 12**: Run for 3 consecutive days. Fix bugs. Tune scoring weights based on whether the right jobs are rising to the top.