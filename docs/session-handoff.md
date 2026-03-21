# Session Handoff — PM Job Pipeline v1

## 1. What This Project Is

An automated pipeline that discovers entry-level Product Manager job postings daily via SerpAPI, scores them against the user's profile using deterministic rules, tailors a resume for each high-scoring match using Claude API, generates DOCX resumes, and delivers a local HTML digest for human review before applying.

Source of truth: `docs/spec.md` (v1.2)

---

## 2. Locked Implementation Constraints

Read `docs/spec.md` fully — it is the canonical reference. Key constraints summarized:

- **Local-first execution**: `python -m src.main`. No GitHub Actions in v1. Gmail optional.
- **Public repo privacy**: `data/` and `db/` gitignored entirely. Config committed (no PII). Examples use fictional "Alex Sample."
- **SerpAPI only**: 6 queries per run (5 NYC-localized + 1 remote with `location: "United States"`). 3-day discovery window.
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

**Total: 191 tests passing across 2 test files.**

---

## 4. Files Created/Changed

```
Created:
  .gitignore
  .env.example
  requirements.txt
  config/config.yaml              # Includes tech_fintech_signals list
  config/config.example.yaml
  src/__init__.py
  src/config.py                   # Config loading, path validation, dir creation
  src/db.py                       # SQLite schema, CRUD, dedup, decide_action, expire
  src/filtering.py                # 3-pass title, location filter, YOE, posting age
  src/scoring.py                  # Two-pass scoring rubric (0-100)
  examples/resume_bank.example.json
  tests/__init__.py
  tests/conftest.py               # fake_config and fake_resume_bank fixtures
  tests/fixtures/fake_resume_bank.json
  tests/test_filtering.py         # 108 tests
  tests/test_scoring.py           # 83 tests
  docs/spec.md                    # Consolidated v1.2 spec (source of truth)
  docs/session-handoff.md         # This file

Not yet created (per spec Section 11):
  src/discovery.py
  src/jd_extractor.py
  src/resume_bank.py
  src/tailoring.py
  src/doc_generator.py
  src/digest.py
  src/notifier.py
  src/main.py
  templates/resume.py
  templates/digest.html
```

---

## 5. What Remains

Full build order from the plan (`C:\Users\fahee\.claude\plans\elegant-swimming-babbage.md`):

| Phase | Status |
|-------|--------|
| Phase 0: SerpAPI validation | NOT DONE — must validate response shape before building discovery.py |
| Phase 1: Skeleton + Config + DB | DONE |
| Phase 2: Filtering + Scoring | DONE |
| Phase 3: Discovery + JD Extraction | NOT STARTED |
| Phase 4: Tailoring + Validation | NOT STARTED |
| Phase 5: DOCX generation | NOT STARTED |
| Phase 6: Digest + Notification | NOT STARTED |
| Phase 7: Orchestration (main.py) | NOT STARTED |
| Phase 8: Stabilization (multi-day runs) | NOT STARTED |

**Next up is Phase 3**: `discovery.py` (SerpAPI integration) and `jd_extractor.py` (fallback chain).

---

## 6. Bugs, Risks, Unfinished Parts

- **No known bugs.** All 191 tests pass.
- **SerpAPI response shape unvalidated**: The spec warns to run a real SerpAPI query before building `discovery.py` (Step 0). Field names like `detected_extensions.posted_at`, `apply_url`, `description` are assumed but unverified. The `chips: "date_posted:3days"` param may not be valid — fallback is `date_posted:week`.
- **SerpAPI free tier budget risk**: 6 queries/run × 22 weekday runs = 132/month, exceeding the 100 free tier. May need to reduce queries or upgrade.
- **`normalize_title_for_dedup()` in db.py duplicates `normalize_title()` in filtering.py**: Both functions implement the same logic. `db.py` has its own copy to avoid circular imports. If the normalization logic changes, both must be updated. Consider extracting to a shared utils module if this becomes a maintenance issue.
- **Python 3.14**: User is on Python 3.14.3 (bleeding edge). All deps installed fine. `py` launcher is the working command (not `python` or `python3`).

---

## 7. Next Prompt

```
Read docs/spec.md (the full spec — it's the source of truth) and docs/session-handoff.md (what's been built so far).

Then build Phase 3:

### Ticket 4: SerpAPI Discovery + JD Extraction

**Goal**: Build discovery.py (SerpAPI integration, 6-query strategy, response normalization) and jd_extractor.py (fallback chain: URL fetch → snippet → skip).

**Files to create**:
- src/discovery.py
- src/jd_extractor.py
- tests/fixtures/fake_serpapi_response.json
- tests/fixtures/fake_jd.md

**Key spec sections**: Section 1 (Source Strategy), Section 3c (JD Extraction Fallback Chain), Section 4 (Dedup — for response normalization)

**Constraints**:
- 6 queries: 5 NYC-localized + 1 remote (location: "United States")
- Tag each result with query_source ('nyc' or 'remote')
- Dedup across queries before returning
- date_posted chip: try "date_posted:3days", fall back to "date_posted:week" if unavailable
- JD fallback chain: full page fetch (httpx + BeautifulSoup) → SerpAPI snippet → skip if < 50 words
- Return (jd_text, jd_source, word_count) from jd_extractor
- Normalize SerpAPI response into a standard job dict matching what filtering.py and scoring.py expect
- Handle missing fields gracefully (no crashes on sparse API responses)

**Important**: Before building, check if a SerpAPI key exists in .env. If not, build the modules to work with the fixture data and add a --dry-run path that uses fake_serpapi_response.json instead of live API calls.

Run tests when done. Show me the final file tree and test results.
```
