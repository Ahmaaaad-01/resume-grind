# Session Handoff 3 — PM Job Pipeline v1

## 1. What This Project Is

An automated pipeline that discovers entry-level Product Manager job postings daily via SerpAPI, scores them against the user's profile using deterministic rules, tailors a resume for each high-scoring match using an LLM (Gemini or Claude, configurable), generates DOCX resumes, and delivers a local HTML digest for human review before applying.

Source of truth: `docs/spec.md` (v1.2)

---

## 2. Locked Implementation Constraints

Read `docs/spec.md` fully — it is the canonical reference. Key constraints summarized:

- **Local-first execution**: `python -m src.main`. No GitHub Actions in v1. Gmail optional.
- **Public repo privacy**: `data/` and `db/` gitignored entirely. Config committed (no PII). Examples use fictional "Alex Sample."
- **SerpAPI only**: 6 queries per run (5 NYC-localized + 1 remote with `location: "United States"`). 3-day discovery window.
- **SerpAPI response shape** (validated 2026-03-21): `jobs_results[]` with `title`, `company_name`, `location`, `description` (full JD inline), `detected_extensions.posted_at`, `apply_options[].link`, `job_id`, `via`, `share_link`. `date_posted:3days` chip works.
- **3-pass title classification**: Denylist → core allowlist → experimental allowlist (config-driven). Default-reject if no match.
- **Target-company location override**: Jobs at target-list companies bypass location filter. Flagged in digest.
- **Two-pass scoring**: Pass 1 (snippet-based, 0–75 pts, cutoff at 30). Pass 2 adds keyword overlap (0–25 pts) from full JD. Final 0–100.
- **JD extraction fallback chain**: Full page fetch → SerpAPI snippet → skip if < 50 words. `jd_source` stored in DB.
- **Dedup key**: SHA-256 of normalized `company|title|location` (16 hex chars). URL never used for dedup.
- **Decision logic**: `process` / `skip` / `resurface`. Expiration at 14 days. No auto-regeneration.
- **Resume tailoring**: 3 bullet tiers (`selected`, `rephrased`, `derived`). `source_ids` validation. Same-role only for derived.
- **DOCX only**: python-docx, Calibri, 1-page hard constraint. File naming: `{First}_{Last}_Resume_{Company}_{Title}.docx`
- **Notification**: Local HTML digest always generated + opened in browser. Gmail optional via config flag.
- **Tech stack**: Python 3.14, SerpAPI, Google GenAI SDK (`gemini-2.5-flash`), Anthropic SDK (`claude-sonnet-4-20250514`), python-docx, SQLite3, Jinja2, httpx, BeautifulSoup4, PyYAML.
- **Company scoring**: Target list = 10 pts, tech/fintech signal match = 6 pts, other = 3 pts.
- **YOE extraction**: Regex-based from JD text. Undetected = pass. No AI.
- **Resume bank**: Manual JSON authoring. `resume_bank.py` only loads and validates.
- **`py` launcher**: User is on Python 3.14.3 (Windows 11). Use `py` not `python` or `python3`.
- **Never run SerpAPI without asking**: Each live run burns 6 queries from a limited free tier. Always ask before running live mode.

---

## 3. What Has Been Completed

### Phases 1–8: Full Pipeline Build — DONE (Session 1–2)
All pipeline modules built and tested. See `docs/session-handoff-2.md` for details.

### Phase 9: Stabilization — DONE (Session 3)
- **First live end-to-end run** completed successfully (SerpAPI + real resume bank)
- 34 jobs discovered, 15 passed hard filters, 3 scored `generate_resume` (60+), 11 `include_in_digest`
- Resume tailoring initially failed (Anthropic API credits exhausted) — handled gracefully

**Bugs fixed in Session 3:**

1. **Location normalization in dedup** (`src/db.py:71-77`): SerpAPI returns locations like `"Jersey City, NJ"` and `"Jersey City, NJ, United States"` across queries. `normalize_location()` now strips trailing country suffixes and parenthetical extras so these produce the same dedup key.

2. **Resurfaced jobs re-processed every run** (`src/main.py:118`): Jobs with status `"scored"` returned `"resurface"` from `decide_action()` but main.py only skipped on `"skip"`. Fixed by treating `"resurface"` like `"skip"` in the per-job loop — `get_resurfacing_jobs()` handles digest inclusion independently. Third run completed in 5 seconds vs 40+ seconds.

3. **Gemini API integration** (`src/tailoring.py`): Added Google Gemini as an alternative LLM provider since Anthropic credits were exhausted. Provider is configurable via `config.yaml` (`tailoring.provider: "gemini"` or `"claude"`). Both providers share the same system prompt, output schema, and validation logic. Gemini tested live and produced valid tailored resumes with DOCX output.

4. **Skills section restructured** (partially, as start of Tuning Round 1): Removed `"domain"` category from resume bank. Renamed `"methods"` to `"platform"`. Now only two categories: `"technical"` (8 skills) and `"platform"` (6 skills). Updated `resume_bank.py` validation, `doc_generator.py` rendering, example bank, and test fixtures.

### Dedup verification — DONE
- Run 2: all previously-scored jobs skipped correctly via DB dedup
- Run 3: resurfaced jobs no longer re-processed (instant skip)

### Gemini live test — DONE
- iCapital job: Validation PASSED, DOCX generated, summary `sum-fintech` selected correctly, 8 bullets across 2 roles
- JP Morgan job: Also generated (though JD was empty since SerpAPI snippet wasn't cached)
- Both DOCX files in `data/resumes/2026-03-21/`

**Total: 346 tests passing across 9 test files.**

---

## 4. Files Created/Changed

```
Changed (Session 3):
  src/db.py                       # normalize_location() fix for dedup
  src/main.py                     # Resurface skip fix (treat resurface like skip)
  src/tailoring.py                # Multi-provider (Gemini + Claude), 8192 max_output_tokens for Gemini
  src/doc_generator.py            # Skills: 2 categories (technical, platform) instead of 3
  src/resume_bank.py              # Validation: expect (technical, platform) not (technical, domain, methods)
  config/config.yaml              # Added: provider, gemini_model, claude_model under tailoring
  requirements.txt                # Added: google-genai
  .env.example                    # Added: GEMINI_API_KEY placeholder
  data/master_resume/resume_bank.json  # Removed domain category, renamed methods→platform
  examples/resume_bank.example.json    # Same schema update
  tests/fixtures/fake_resume_bank.json # Same schema update
  tests/test_tailoring.py         # Mocks updated for multi-provider (mock _call_claude instead of anthropic.Anthropic)
  tests/test_resume_bank.py       # Updated skills validation tests (domain/methods → platform)
  docs/tuning-round-1.md          # Plan doc for tuning improvements

Created (Session 3):
  docs/session-handoff-3.md       # This file

Unchanged from Session 1–2:
  (all other src/, tests/, config/, templates/ files — see session-handoff-2.md)
```

---

## 5. What Remains — Tuning Round 1

Full plan: `docs/tuning-round-1.md` (7 changes, partially started)

| Change | Status |
|--------|--------|
| 1. Skills section cleanup (technical + platform only) | **DONE** |
| 2. Right-align dates/location in experience headers | NOT STARTED |
| 3. Multi-role company grouping (multiple roles under one heading) | NOT STARTED |
| 4. Include at least one earlier role (optional roles) | NOT STARTED |
| 5. Bullet generation logic (prompt rewrite — less copy-paste, more tailored) | NOT STARTED |
| 6. Bullet line-length optimization (avoid orphan words on second line) | NOT STARTED |
| 7. Page length — fill one full page | NOT STARTED |

Changes 2–3 are `doc_generator.py` formatting work.
Changes 4–7 are primarily `tailoring.py` SYSTEM_PROMPT rewrites (do together as one coherent prompt rewrite) plus `config.yaml` updates (`max_derived_bullets: 5`, `max_bullets_per_role: 5`).

---

## 6. Bugs, Risks, Unfinished Parts

- **No known bugs.** All 346 tests pass.
- **Anthropic API credits exhausted**: `.env` has a real key but the account has no credits. Gemini is the active provider (`tailoring.provider: "gemini"` in config.yaml).
- **SerpAPI free tier budget**: 6 queries/run. User has explicitly asked to never run live SerpAPI without permission. Use `--dry-run` or reuse existing DB data for testing.
- **DB has live data from 3 runs**: 15 scored jobs in `db/pipeline.db` from 2026-03-21. Reuse these for testing tailoring changes (no SerpAPI needed).
- **`normalize_title_for_dedup()` in db.py duplicates `normalize_title()` in filtering.py**: Both implement the same logic. If normalization logic changes, both must be updated.
- **1-page DOCX constraint not programmatically enforced**: `doc_generator.py` builds a single-page layout but doesn't verify fit. Tuning Round 1 Change 7 adds a line-count estimator (logging only).
- **Gemini `max_output_tokens` set to 8192**: At 4096 it truncated JSON. 8192 works but watch for cost if switching to a more expensive model.

---

## 7. Next Prompt

```
Read docs/spec.md (the full spec — it's the source of truth), docs/session-handoff-3.md (what's been built so far), and docs/tuning-round-1.md (the plan for current work).

Then continue Tuning Round 1 — pick up where Session 3 left off.

### What's already done
- Change 1 (skills cleanup) is DONE — resume_bank.json, resume_bank.py, doc_generator.py, tests all updated. 346 tests pass.

### What's next (in order)
1. Change 2: Right-align dates/location in experience headers (doc_generator.py — add tab stop helper, update experience + education rendering)
2. Change 3: Multi-role company grouping (doc_generator.py — group roles by company, render company header + sub-role lines with bullets)
3. Changes 4–7: Rewrite tailoring.py SYSTEM_PROMPT as one coherent prompt covering:
   - Role inclusion rules (at least one earlier role required)
   - Bullet generation philosophy (bank is reference material, not copy-paste source; prefer rephrased/derived)
   - Bullet line-length targets (≤90 chars for 1 line, 140–180 for 2 lines, avoid 91–135 orphan zone)
   - Page fill guidance (fill exactly one page, target content budget)
   - Update config.yaml: max_derived_bullets=5, max_bullets_per_role=5

### Testing
- Run `py -m pytest tests/ -x -q` after each change
- For live Gemini test: reuse existing DB data (do NOT call SerpAPI without asking). Use the same test script pattern from Session 3:
  py -c "from src.config import load_config; from src.resume_bank import load_resume_bank; from src.jd_extractor import extract_jd; from src.tailoring import tailor_resume; from src.doc_generator import generate_docx; config = load_config(); bank = load_resume_bank(); job = {'title_raw': 'Structured Investments Product Manager - Associate', 'company': 'iCapital', 'location': 'New York', 'url': 'https://www.linkedin.com/jobs/view/structured-investments-product-manager-associate-at-icapital-4387420473', 'date_posted': '2 days ago', 'description_snippet': '', 'dedup_key': 'ba6ea94a32e6e46b'}; jd_text, jd_source, jd_wc = extract_jd(job); print(f'JD: {jd_source}, {jd_wc} words'); tailored = tailor_resume(job, jd_text, bank, config); print('Errors:', tailored.get('validation_errors')); docx_path = generate_docx(tailored, bank, job); print(f'DOCX: {docx_path}')"
- Open the generated DOCX and verify formatting visually
```
