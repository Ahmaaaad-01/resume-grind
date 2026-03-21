# Session Handoff 4 — PM Job Pipeline v1

## 1. What This Project Is

An automated pipeline that discovers entry-level Product Manager job postings daily via SerpAPI, scores them against the user's profile using deterministic rules, tailors a resume for each high-scoring match using an LLM (Gemini or Claude, configurable), generates DOCX resumes, and delivers a local HTML digest for human review before applying.

Source of truth: `docs/spec.md` (v1.2)

---

## 2. Locked Implementation Constraints

Read `docs/spec.md` fully — it is the canonical reference. Key constraints summarized:

- **Local-first execution**: `python -m src.main`. No GitHub Actions in v1. Gmail optional.
- **Public repo privacy**: `data/` and `db/` and `.claude/` gitignored entirely. Config committed (no PII). Examples use fictional "Alex Sample." All docs anonymized — no real names, employers, or role IDs.
- **SerpAPI only**: 6 queries per run (5 NYC-localized + 1 remote with `location: "United States"`). 3-day discovery window.
- **3-pass title classification**: Denylist → core allowlist → experimental allowlist (config-driven). Default-reject if no match.
- **Two-pass scoring**: Pass 1 (snippet-based, 0–75 pts, cutoff at 30). Pass 2 adds keyword overlap (0–25 pts) from full JD. Final 0–100.
- **Resume tailoring**: 3 bullet tiers (`selected`, `rephrased`, `derived`). Max 5 derived. `source_ids` validation. Same-role only for derived.
- **DOCX only**: python-docx, Times New Roman 12pt, 0.7" margins, 1-page hard constraint.
- **Tech stack**: Python 3.14, SerpAPI, Google GenAI SDK (`gemini-2.5-flash`), Anthropic SDK (`claude-sonnet-4-20250514`), python-docx, SQLite3, Jinja2, httpx, BeautifulSoup4, PyYAML.
- **`py` launcher**: User is on Python 3.14.3 (Windows 11). Use `py` not `python` or `python3`.
- **Never run SerpAPI without asking**: Each live run burns 6 queries from a limited free tier.

---

## 3. What Has Been Completed

### Phases 1–9: Full Pipeline Build + Stabilization — DONE (Sessions 1–3)
All pipeline modules built, tested, and stabilized with live runs. See `docs/session-handoff-2.md` and `docs/session-handoff-3.md`.

### Tuning Round 1 — MOSTLY DONE (Sessions 3–4)

| Change | Status |
|--------|--------|
| 1. Skills section cleanup (technical + platform only) | **DONE** |
| 2. Right-align dates/location (twips-based tab stops) | **DONE** |
| 3. Multi-role company grouping (multiple roles under one heading) | **DONE** |
| 4. Include TWO optional roles from different companies | **DONE** |
| 5. Bullet generation logic (prompt rewrite — rephrased as default tier) | **DONE** |
| 6. Bullet line-length optimization (≤75 or 120-150, avoid 76-110 orphan zone) | **DONE** |
| 7. Page fill — fill one full page | **DONE** |
| 8. Hard one-page enforcement (overflow prevention) | **IN PROGRESS — estimator still miscalibrated** |
| 9. Bullet reflow (orphan line prevention) | **DONE** |

### Privacy/PII Audit — DONE (Session 4)
All files anonymized for public GitHub. No real names, employers, or personal role IDs in any committed file. `.claude/` added to `.gitignore`. API keys were never in git history — no rotation needed.

### Anthropic Claude API — WORKING (Session 4)
Provider switched from Gemini to Claude. `config.yaml` has `tailoring.provider: "claude"`. Live tests produce valid tailored resumes with zero validation errors.

**Total: 346 tests passing across 9 test files.**

---

## 4. Files Created/Changed (Session 4)

```
Changed:
  src/doc_generator.py            # Major: right-align tab stops (twips), multi-role grouping,
                                  #   page height estimator (replaced point-based with line-count),
                                  #   spacing auto-adjustment, bullet reflow, bullet trimming,
                                  #   skills on separate lines, two-line education layout.
                                  #   Font: Times New Roman 12pt (was Calibri 10.5pt).
  src/tailoring.py                # SYSTEM_PROMPT rewrite: 5-7 bullets/main role, 3-4 optional,
                                  #   TWO optional roles required, bullet tiers, formatting rules.
                                  #   PII removed (no hardcoded role IDs or company names).
                                  #   Gemini max_output_tokens: 16384.
  config/config.yaml              # max_derived_bullets: 5, max_bullets_per_role: 7,
                                  #   provider: "claude"
  .gitignore                      # Added .claude/
  src/resume_bank.py              # Skills validation: (technical, platform)
  docs/v1-addendum-1.md           # PII anonymized (Alex Sample, Example Corp)
  docs/v1-spec.md                 # PII anonymized (Alex_Sample filenames), font updated to TNR 12pt
  docs/session-handoff-2.md       # PII anonymized
  docs/session-handoff-3.md       # PII anonymized
  docs/tuning-round-1.md          # PII anonymized, changes 8-9 added
  tests/test_tailoring.py         # Updated for derived limit 5, prompt string changes
  data/master_resume/resume_bank.json  # Education: added location field, updated degree/graduation

Created:
  docs/session-handoff-4.md       # This file
```

---

## 5. What Remains — One-Page Fit (THE CURRENT BUG)

### The Problem
The resume overflows by ~5 lines onto page 2. This has persisted through multiple calibration attempts.

### History of Attempts
1. **Point-based estimator with LINE_HEIGHT_FACTOR=1.30** → overestimated by ~40% (said 148% when reality was ~107%). Trimmer removed too many bullets → resume too short.
2. **Disabled trimming entirely** → resume overflows with no safety net.
3. **Replaced with line-count estimator** (`_estimate_content_lines`) and set `MAX_CONTENT_LINES=46` (theoretical: 691.2pt/15pt) → still overestimated (70.5 lines for 17 bullets that are really ~51 lines).
4. **Recalibrated to MAX_CONTENT_LINES=65** (empirical: 70.5 - 5 = 65) → trimmed only 1 bullet but **still 5 lines over visually**.

### Why It's Still Wrong
The estimator at MAX=65 trims to 64 estimated lines (99% fill) and reports success, but the DOCX is still 5 lines over. This means the spacing adjustment loop is crushing paragraph spacing (because the initial estimate is >100%), making the doc's spacing artificially tight, but the content still doesn't fit. The estimator's line-counting is overcounting somewhere — likely paragraph spacing being double-converted, or non-bullet paragraphs using a chars-per-line that's too conservative.

### Key Constants (current state in `doc_generator.py`)
```python
FONT_NAME = "Times New Roman"
BODY_SIZE = Pt(12)
NAME_SIZE = Pt(16)
CHARS_PER_LINE = 73
LINE_HEIGHT_PT = 15.0
MAX_CONTENT_LINES = 65.0       # empirically set, but still wrong
USABLE_HEIGHT_PT = 691.2       # (11" - 2*0.7") * 72
RIGHT_TAB_TWIPS = 10224        # 7.1" * 1440
PAGE_FILL_TARGET_LOW = 0.92
PAGE_FILL_TARGET_HIGH = 1.0
```

### Empirical Data Points (CRITICAL — use these to calibrate)
- **10 total bullets** (3+3+2+2) = visually **7-8 lines SHORT** of one page
- **16 total bullets** (after 1 trimmed from 17) at estimated 99% = visually **still ~5 lines OVER**
- **17 total bullets** (6+5+3+3) = visually **~5 lines OVER** (same as 16 — trimming 1 isn't enough)
- **Sweet spot**: ~13-14 total bullets should fill exactly one page
- Each bullet averages ~1.7 rendered lines (mix of 1-line ≤75 chars and 2-line 120-150 chars)
- Non-bullet overhead (headers, contact, summary, skills, education) ≈ ~22 rendered lines

### Recommended Fix Approach
The `_adjust_spacing` loop is counter-productive — it crushes spacing based on a wrong estimate, making the doc look bad without actually fixing the overflow. Consider:

1. **Remove spacing adjustment entirely** — let the document keep its natural spacing
2. **Only use bullet trimming** as the single page-fit mechanism
3. **Calibrate MAX_CONTENT_LINES against the UN-ADJUSTED estimate** — if 17 bullets (unadjusted) = 70.5 estimated lines and is 5 lines over, and each bullet ≈ 2.1 estimated lines, then trimming 3 bullets removes ~6.3 estimated lines → 64.2 lines. Set MAX ≈ 64 and disable spacing adjustment.
4. Or: **completely replace the estimator** with a simple total-bullet-count heuristic: if total bullets > 14, trim from largest group. This avoids the line-counting problem entirely.

### Key Functions in `doc_generator.py`
- `_estimate_content_lines(doc)` — line-count estimator (overcounts by ~20%)
- `_adjust_spacing(doc, fill_ratio)` — crushes/expands paragraph spacing (counter-productive)
- `_trim_bullets_for_overflow(doc)` — removes bullets from largest group (works correctly when triggered)
- `_reflow_bullets(doc)` — trims orphan-zone bullets at clause boundaries (works correctly)
- `_build_doc(tailored, bank)` — builds all sections
- `generate_docx(...)` — orchestrates: build → reflow → spacing adjust (3 passes) → trim → re-adjust → save

---

## 6. Bugs, Risks, Unfinished Parts

- **ACTIVE BUG: Resume overflows by ~5 lines.** The line-count estimator overcounts, and spacing adjustment makes it worse by crushing spacing without actually fixing overflow. See section 5 for details.
- **No other known bugs.** All 346 tests pass.
- **Anthropic Claude API is working.** Provider set to `"claude"` in config.yaml.
- **SerpAPI free tier budget**: Never run live SerpAPI without user permission.
- **DB has live data from 3 runs**: 15 scored jobs in `db/pipeline.db` from 2026-03-21. Reuse for testing.
- **`normalize_title_for_dedup()` in db.py duplicates `normalize_title()` in filtering.py**: If normalization logic changes, both must be updated.

---

## 7. Next Prompt

```
Read docs/spec.md, docs/tuning-round-1.md, and docs/session-handoff-4.md.

Fix the one-page resume overflow bug. The resume currently overflows by ~5 lines.

### The core problem
The `_estimate_content_lines()` function in `src/doc_generator.py` overcounts lines by ~20%, and `_adjust_spacing()` makes it worse by crushing paragraph spacing without actually fixing the overflow.

### Empirical calibration data
- 10 total bullets = 7-8 lines SHORT of a full page
- 17 total bullets = ~5 lines OVER a full page
- Sweet spot: ~13-14 total bullets fills exactly one page
- Each bullet ≈ 1.7 rendered lines on average

### Recommended approach
1. Disable `_adjust_spacing()` entirely — let the document keep natural spacing
2. Use ONLY bullet trimming for page fit
3. Either: calibrate `MAX_CONTENT_LINES` against the unadjusted estimator output, OR replace the estimator with a simple bullet-count ceiling (max 14 total bullets, trim from largest group if over)
4. The SYSTEM_PROMPT already requests 5-7 bullets per main role and 3-4 per optional role, producing 16-22 bullets. The trimmer should cut this down to ~14.

### Testing
- `py -m pytest tests/ -x -q` after changes
- Live test (burns 1 Claude API call):
  py -c "from src.config import load_config; from src.resume_bank import load_resume_bank; from src.jd_extractor import extract_jd; from src.tailoring import tailor_resume; from src.doc_generator import generate_docx; config = load_config(); bank = load_resume_bank(); job = {'title_raw': 'Structured Investments Product Manager - Associate', 'company': 'iCapital', 'location': 'New York', 'url': 'https://www.linkedin.com/jobs/view/structured-investments-product-manager-associate-at-icapital-4387420473', 'date_posted': '2 days ago', 'description_snippet': '', 'dedup_key': 'test_v5'}; jd_text, jd_source, jd_wc = extract_jd(job); tailored = tailor_resume(job, jd_text, bank, config); print('Errors:', tailored.get('validation_errors')); [print(f'  {r[\"role_id\"]}: {len(r.get(\"bullets_selected\", []))} bullets') for r in tailored.get('experience', [])]; docx_path = generate_docx(tailored, bank, dict(job, company='iCapital_v5')); print(f'DOCX: {docx_path}')"
- Open DOCX in Word — must fit exactly one page with no overflow
```
