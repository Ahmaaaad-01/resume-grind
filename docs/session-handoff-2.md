# Session Handoff 2 — PM Job Pipeline v1

## 1. What This Project Is

An automated pipeline that discovers entry-level Product Manager job postings daily via SerpAPI, scores them against the user's profile using deterministic rules, tailors a resume for each high-scoring match using Claude API, generates DOCX resumes, and delivers a local HTML digest for human review before applying.

Source of truth: `docs/spec.md` (v1.2)

---

## 2. Locked Implementation Constraints

Read `docs/spec.md` fully — it is the canonical reference. Key constraints summarized:

- **Local-first execution**: `python -m src.main`. No GitHub Actions in v1. Gmail optional.
- **Public repo privacy**: `data/` and `db/` gitignored entirely. Config committed (no PII). Examples use fictional "Alex Sample."
- **SerpAPI only**: 6 queries per run (5 NYC-localized + 1 remote with `location: "United States"`). 3-day discovery window.
- **SerpAPI response shape** (validated 2026-03-21): `jobs_results[]` with `title`, `company_name`, `location`, `description` (full JD inline, not just snippet), `detected_extensions.posted_at`, `apply_options[].link`, `job_id`, `via`, `share_link`. `date_posted:3days` chip works.
- **3-pass title classification**: Denylist → core allowlist → experimental allowlist (config-driven). Default-reject if no match.
- **Target-company location override**: Jobs at target-list companies bypass location filter. Flagged in digest.
- **Two-pass scoring**: Pass 1 (snippet-based, 0–75 pts, cutoff at 30). Pass 2 adds keyword overlap (0–25 pts) from full JD. Final 0–100.
- **JD extraction fallback chain**: Full page fetch → SerpAPI snippet → skip if < 50 words. `jd_source` stored in DB.
- **Dedup key**: SHA-256 of normalized `company|title|location` (16 hex chars). URL never used for dedup.
- **Decision logic**: `process` / `skip` / `resurface`. Expiration at 14 days. No auto-regeneration.
- **Resume tailoring**: 3 bullet tiers (`selected`, `rephrased`, `derived`). Max 3 derived per resume. Same-role only. `source_ids` validation.
- **DOCX only**: python-docx, Calibri, 1-page hard constraint. File naming: `{First}_{Last}_Resume_{Company}_{Title}.docx`
- **Notification**: Local HTML digest always generated + opened in browser. Gmail optional via config flag.
- **Tech stack**: Python 3.14, SerpAPI, Anthropic SDK (`claude-sonnet-4-20250514`), python-docx, SQLite3, Jinja2, httpx, BeautifulSoup4, PyYAML.
- **Company scoring**: Target list = 10 pts, tech/fintech signal match (via `tech_fintech_signals` config list) = 6 pts, other = 3 pts.
- **YOE extraction**: Regex-based from JD text. Undetected = pass. No AI.
- **Resume bank**: Manual JSON authoring. `resume_bank.py` only loads and validates.
- **`py` launcher**: User is on Python 3.14.3 (Windows 11). Use `py` not `python` or `python3`.

---

## 3. What Has Been Completed

### Ticket 1: Repo Scaffolding + Config + DB — DONE
- Project skeleton, .gitignore, .env.example, requirements.txt
- Config loading with path validation and auto-directory creation
- SQLite schema (23 columns matching spec Section 4)
- Dedup key generation, upsert, decide_action, expire_old_jobs
- Example resume bank (fictional "Alex Sample")

### Ticket 2: Hard Filters + Tests — DONE
- 3-pass title classification (denylist → core allowlist → experimental allowlist)
- Config-driven location filter with target-company override
- `is_target_company_override()` for digest flagging
- Regex-based YOE extraction and check
- Posting age check
- Master `passes_hard_filters()` with metadata and short-circuit logic
- 108 tests — all passing

### Ticket 3: Two-Pass Scoring + Tests — DONE
- `score_title()`, `score_yoe()`, `score_location()`, `score_company()`, `score_recency()`
- `score_keywords()` with match count and matched skills list
- `score_pass1()` aggregating non-keyword factors (0–75)
- `passes_pass1_cutoff()` with configurable threshold
- `score_pass2()` adding keyword overlap for final 0–100
- `classify_score()` mapping to `generate_resume` / `include_in_digest` / `discard`
- 83 tests — all passing

### Ticket 4: SerpAPI Discovery + JD Extraction — DONE
- Phase 0: Validated real SerpAPI `google_jobs` response shape (field names, `date_posted:3days` chip confirmed)
- `discovery.py`: 6-query strategy (5 NYC + 1 remote), response normalization, cross-query dedup, dry-run mode
- `jd_extractor.py`: Fallback chain (URL fetch via httpx+BS4 → SerpAPI snippet → skip), word count threshold (50 min)
- Fixture: `fake_serpapi_response.json` with 7 realistic jobs (dupes, short JD, target company, remote)
- 37 tests — all passing

### Ticket 5: Resume Bank Loader — DONE
- `resume_bank.py`: Loads and validates `resume_bank.json` — checks required fields, ID uniqueness, summary count/length (2–5, ≤350 chars), bullet minimums for `include_always` roles (≥3)
- Helper functions: `get_all_bullet_ids()`, `get_role_bullet_ids()`
- 41 tests — all passing

### Ticket 6: Resume Tailoring + Validation — DONE
- `tailoring.py`: Claude API integration with system prompt from spec Section 6
- `validate_tailored_output()`: source_id checks, derived bullet rules (1–3 sources, same role, rationale required, max 3 total), selected/rephrased must have exactly 1 source_id, summary_used validation
- Markdown fence stripping for Claude responses
- 26 tests — all passing (all using mocked Claude API)

### Ticket 7: DOCX Generation — DONE
- `doc_generator.py`: python-docx builder with Calibri font, 0.7" margins, section headers with bottom borders
- Sections: Contact (centered) → Summary → Experience (company bold, title italic, date range) → Skills (grouped, reordered) → Education → Projects (optional)
- File naming: `{First}_{Last}_Resume_{Company}_{Title}.docx`
- 24 tests — all passing

### Ticket 8: Digest + Notification — DONE
- `digest.py`: Jinja2 HTML rendering with warning flag logic (short JD, experimental title, target-company override, validation errors, keyword gaps)
- `templates/digest.html`: Full HTML template with Top Matches, Worth a Look, Reminder: Still Open, Review Carefully sections + footer stats
- `notifier.py`: Save local HTML + open browser + optional Gmail (placeholder, not implemented)
- 21 tests — all passing

### Ticket 9: Orchestration (main.py) — DONE
- `main.py`: Full pipeline flow — discovery → dedup → hard filters → Pass 1 → JD extraction → Pass 2 → tailoring → DOCX → digest → notify → expire
- CLI: `--dry-run` flag for fixture-based runs
- Key mapping: discovery dict (`title_raw`, `description_snippet`) → filtering/scoring dict (`title`, `description`)
- Dry-run tested end-to-end: 6 jobs discovered, filters applied, scoring works, digest generated and opens in browser
- 7 tests — all passing

### Real Resume Bank Created — DONE
- `data/master_resume/resume_bank.json` (gitignored): candidate's real resume data
- 5 roles across multiple companies, 52 bullets total
- 5 summary variants (general, platform, growth/data, fintech, AI/automation)
- 19 skills across technical/domain/methods
- Education: UVA McIntire

**Total: 347 tests passing across 9 test files.**

---

## 4. Files Created/Changed

```
Created (Session 2):
  src/discovery.py                # SerpAPI integration, 6-query strategy, dedup, dry-run
  src/jd_extractor.py             # JD fallback chain: URL fetch → snippet → skip
  src/resume_bank.py              # Load + validate resume_bank.json
  src/tailoring.py                # Claude API tailoring + output validation
  src/doc_generator.py            # DOCX generation via python-docx
  src/digest.py                   # Jinja2 HTML digest builder
  src/notifier.py                 # Local HTML save + browser open + Gmail placeholder
  src/main.py                     # Pipeline orchestrator with --dry-run
  templates/digest.html           # Full HTML digest template
  tests/fixtures/fake_serpapi_response.json  # 7-job fixture with dedup/edge cases
  tests/fixtures/fake_jd.md       # Sample JD text
  tests/test_discovery.py         # 20 tests
  tests/test_jd_extractor.py      # 17 tests
  tests/test_resume_bank.py       # 41 tests
  tests/test_tailoring.py         # 26 tests
  tests/test_doc_generator.py     # 24 tests
  tests/test_digest.py            # 21 tests
  tests/test_main.py              # 7 tests
  data/master_resume/resume_bank.json  # Real resume bank (gitignored)

Created (Session 1 — unchanged):
  .gitignore
  .env.example
  requirements.txt
  config/config.yaml
  config/config.example.yaml
  src/__init__.py
  src/config.py
  src/db.py
  src/filtering.py
  src/scoring.py
  examples/resume_bank.example.json
  tests/__init__.py
  tests/conftest.py
  tests/fixtures/fake_resume_bank.json
  tests/test_filtering.py         # 108 tests
  tests/test_scoring.py           # 83 tests
  docs/spec.md
  docs/session-handoff.md

Not yet created (per spec Section 11):
  templates/resume.py             # Spec lists this but doc_generator.py covers it
  .github/workflows/daily_run.yml # Placeholder — not active in v1
```

---

## 5. What Remains

| Phase | Status |
|-------|--------|
| Phase 0: SerpAPI validation | DONE |
| Phase 1: Skeleton + Config + DB | DONE |
| Phase 2: Filtering + Scoring | DONE |
| Phase 3: Discovery + JD Extraction | DONE |
| Phase 4: Resume Bank Loader | DONE |
| Phase 5: Tailoring + Validation | DONE |
| Phase 6: DOCX Generation | DONE |
| Phase 7: Digest + Notification | DONE |
| Phase 8: Orchestration (main.py) | DONE |
| Phase 9: Stabilization (multi-day runs) | NOT STARTED |

**All code is built. Next up is Phase 9**: Set a real Anthropic API key, run live with SerpAPI, and stabilize over 3–5 days.

---

## 6. Bugs, Risks, Unfinished Parts

- **No known bugs.** All 347 tests pass. Dry-run completes end-to-end.
- **Anthropic API key is placeholder**: `.env` has `ANTHROPIC_API_KEY=your_anthropic_key_here`. Tailoring will fail with 401 until a real key is set. The pipeline handles this gracefully — logs the error, skips DOCX generation, continues to the next job.
- **Gmail not implemented**: `notifier.py._send_gmail()` raises `NotImplementedError`. Config has `gmail_enabled: false`. Non-blocking.
- **`normalize_title_for_dedup()` in db.py duplicates `normalize_title()` in filtering.py**: Both implement the same logic. `db.py` has its own copy to avoid circular imports. If the normalization logic changes, both must be updated.
- **`passes_hard_filters()` and `score_pass1()` expect different key names than discovery.py produces**: `main.py` maps `title_raw` → `title` and `description_snippet` → `description` before calling them. If you call these functions directly outside `main.py`, remember the key mapping.
- **SerpAPI free tier budget risk**: 6 queries/run × 22 weekday runs = 132/month, exceeding the 100 free tier. May need to reduce queries or upgrade.
- **1-page DOCX constraint is not programmatically enforced**: `doc_generator.py` builds a single-page layout but doesn't verify the output fits on one page. With 3–4 bullets per role and compact formatting it should fit, but very long bullets could overflow.
- **`templates/resume.py` from spec not created**: The spec lists this file but `doc_generator.py` covers all DOCX logic directly. No separate template class was needed.
- **SerpAPI `description` field contains full JD text**: This was a positive discovery — the `serpapi_snippet` fallback in `jd_extractor.py` often has rich content (not just a 2-sentence snippet). This means fewer jobs will be skipped for insufficient JD length.

---

## 7. Next Prompt

```
Read docs/spec.md (the full spec — it's the source of truth) and docs/session-handoff-2.md (what's been built so far).

Then run Phase 9: Stabilization

### Goal
Run the pipeline live and fix anything that breaks. This is the first real end-to-end run with live SerpAPI + Claude API.

### Prerequisites
1. Confirm .env has a real ANTHROPIC_API_KEY (not the placeholder)
2. Confirm .env has the SERPAPI_KEY (already validated — working)
3. Confirm data/master_resume/resume_bank.json exists (already created — real data)

### Steps
1. Run `py -m src.main` (live mode, not dry-run)
2. Fix any errors that come up
3. Inspect the generated digest HTML — verify all sections render correctly
4. Inspect any generated DOCX files — verify formatting matches spec (Calibri, margins, sections)
5. Check the SQLite DB: `py -c "import sqlite3; conn = sqlite3.connect('db/pipeline.db'); print([dict(r) for r in conn.execute('SELECT dedup_key, title_raw, company, final_score, status FROM jobs').fetchall()])"`
6. Run a second time to verify dedup works (same jobs should be skipped or resurfaced, not reprocessed)

### After first successful run, monitor over 3-5 days:
- Is Pass 1 cutoff filtering >2 jobs/run? If not, lower to 20 or remove.
- Is the remote query adding unique jobs not in NYC results?
- Are experimental titles surfacing anything useful?
- Are target-company overrides firing?
- How often does JD extraction fall back to snippet vs full fetch?

### Known issues to watch for:
- Claude may return JSON with unexpected structure — tailoring.py strips markdown fences but other quirks may appear
- Some job apply URLs may redirect or require auth — jd_extractor handles this gracefully but log any patterns
- SerpAPI rate limiting if running multiple times in quick succession
```
