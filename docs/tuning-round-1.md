# Tuning Improvements Round 1

## Context

First live pipeline run produced DOCX resumes that need formatting and content quality improvements. The resumes look underfilled, have flat copy-pasted bullets, no date alignment, and redundant skills categories. These 7 changes make the output recruiter-ready.

---

## Changes

### 1. Skills Section Cleanup
**Files:** `data/master_resume/resume_bank.json`, `src/resume_bank.py`, `src/doc_generator.py`

- In `resume_bank.json`: delete the `"domain"` category entirely. Rename `"methods"` to `"platform"`. Keep `"technical"` as-is.
  - **Technical (8):** SQL, Jira, Figma, Excel/Google Sheets, Google Apps Script, HTML, Salesforce, API Design & Integration
  - **Platform (6):** Agile/Scrum, A/B Testing & Experimentation, User Research, Roadmap Planning, Stakeholder Management, PRDs & User Stories
- In `resume_bank.py`: update validation to expect `("technical", "platform")` instead of `("technical", "domain", "methods")`
- In `doc_generator.py` `_add_skills_section()`: render two categories `"Technical: ... | Platform: ..."` instead of three

### 2. Right-Align Dates & Location in Experience Headers
**Files:** `src/doc_generator.py`

- Add a helper `_add_right_tab_stop(paragraph, position)` that inserts a right-aligned tab stop via XML (`w:tabs` / `w:tab` with `w:val="right"`)
- Position: `Inches(7.1)` from left margin (page width 8.5" minus 2x0.7" margins = 7.1" usable)
- In experience headers: render `Company -- Title` as left-aligned runs, then `\t` tab character, then `Date Range | Location` right-aligned
- Apply same technique to education entries (right-align graduation year)

### 3. Multi-Role Company Grouping
**Files:** `src/doc_generator.py`, `src/tailoring.py`

- In `_add_experience_section()`: before rendering, group consecutive roles by `company` name (preserving order)
- **Single-role group:** render as today (company bold + title italic on one line, right-aligned dates/location)
- **Multi-role group (primary employer):** render as:
  ```
  Primary Employer                                     City, ST
    Product Manager, Team A                                Aug 2024 - Present
      * bullet...
    Product Manager, Team B                                Aug 2023 - Aug 2024
      * bullet...
    Intern                                                 Jun 2022 - Aug 2022
      * bullet...
  ```
  - Company line: bold company name left, location right-aligned via tab stop
  - Each sub-role line: italic title left, date range right-aligned via tab stop
  - Bullets indented under their respective sub-role
- In `tailoring.py` SYSTEM_PROMPT: mention primary employer roles will be grouped, so LLM should return them in reverse-chronological order

### 4. Include at Least One Earlier Role
**Files:** `src/tailoring.py`

- Add to SYSTEM_PROMPT under a new "ROLE INCLUSION RULES" section:
  - Always include all `include_always: true` roles
  - Always include **at least one** non-`include_always` role, picking the most JD-relevant. Include more if they help fill the page.
- Add to `_build_user_prompt()` constraints
- Add validation in `validate_tailored_output()`: check at least one role with `include_always == false` is present; add warning (not hard error) if missing

### 5. Bullet Generation Logic (Prompt Rewrite)
**Files:** `src/tailoring.py`, `config/config.yaml`

- Rewrite SYSTEM_PROMPT bullet tier framing:
  - Shift from "SELECT, REPHRASE, optionally DERIVE" to "use the bank as evidence to write tailored bullets"
  - `selected`: use sparingly -- only when a bank bullet already reads perfectly for the JD
  - `rephrased`: the **default** tier. Rephrase for JD keywords, emphasis, and framing. Facts/metrics stay identical.
  - `derived`: synthesize from 1-3 same-role bullets. Increase cap from 3 to 5.
  - Add: "The output should feel tailored and natural, not like copy-paste from a template."
- In `config.yaml`: change `max_derived_bullets: 3` to `max_derived_bullets: 5`
- Update validation cap accordingly

### 6. Bullet Line-Length Optimization
**Files:** `src/tailoring.py`

- Add to SYSTEM_PROMPT a "BULLET LENGTH" rule:
  - Target: <=90 characters (one clean line at Calibri 10.5pt, 6.85" text width)
  - If longer: aim for 140-180 characters (fills ~1.5-2 lines)
  - **Avoid** 91-135 characters -- these wrap to a second line with just a few orphaned words
  - Shorter is better when possible

### 7. Page Length -- Fill One Full Page
**Files:** `src/tailoring.py`, `src/doc_generator.py`

- Add to SYSTEM_PROMPT a "PAGE FILL" rule:
  - The resume must fill exactly one page. Underfilled resumes look weak.
  - Target: 2 main roles with 4-5 bullets each + 1-2 earlier roles with 2-3 bullets each + 2-sentence summary
  - Increase `max_bullets_per_role` from 4 to 5 in config
- In `doc_generator.py`: add `_estimate_line_count(doc)` that counts approximate lines based on character lengths of paragraphs. Log a warning if estimated fill is <80% or >100% of one page (~47 lines at Calibri 10.5pt single-spaced with 0.7" margins). This is informational only -- no auto-adjustment in round 1.

### 8. Hard One-Page Enforcement (Overflow Prevention)
**Files:** `src/doc_generator.py`

- After spacing adjustment passes, if estimated height still >100% of usable page:
  - **Trim bullets**: remove the last bullet from the role with the most bullets, re-estimate. Repeat until ≤100%.
  - This is deterministic post-processing — no LLM re-call needed.
  - Order: spacing tightening → bullet trimming. Spacing is cheaper so it runs first.
- Tab stop position fixed: was passing EMUs (6,492,240) to `w:pos` which expects twips (10,224). Now correct.

### 9. Bullet Reflow (Orphan Line Prevention)
**Files:** `src/doc_generator.py`

- Post-generation pass `_reflow_bullets()` checks each bullet's character count against CHARS_PER_LINE (75):
  - **≤75 chars**: OK (1 clean line)
  - **76-110 chars** (orphan zone): trim trailing clause at natural break (comma, "and", "including", etc.) to get ≤75 chars
  - **111+ chars**: OK (fills 2 lines meaningfully)
- Applied after document build, before spacing adjustment and overflow trimming.
- Font changed to Times New Roman 12pt (from Calibri 10.5pt). Prompt bullet length targets updated to match.

---

## Implementation Order

1. **Skills cleanup** (change 1) -- touches bank schema, do first
2. **Right-align dates** (change 2) -- independent formatting, enables change 3
3. **Multi-role company grouping** (change 3) -- depends on tab stop helper from change 2
4. **Earlier role inclusion** (change 4) -- prompt change, independent
5. **Bullet generation logic** (change 5) -- prompt rewrite, independent
6. **Bullet line-length** (change 6) -- prompt addition, independent
7. **Page fill** (change 7) -- integration, do last

Changes 4-6 are all `tailoring.py` SYSTEM_PROMPT edits and will be done together as one coherent prompt rewrite.

---

## Files Modified

| File | Changes |
|------|---------|
| `data/master_resume/resume_bank.json` | Remove domain category, rename methods to platform |
| `src/resume_bank.py` | Update validation for new skill categories |
| `src/doc_generator.py` | Tab-stop alignment, multi-role grouping, skills rendering, page-fill estimation |
| `src/tailoring.py` | SYSTEM_PROMPT rewrite (bullet philosophy, role inclusion, line-length, page fill) |
| `config/config.yaml` | `max_derived_bullets: 5`, `max_bullets_per_role: 5` |
| `tests/test_tailoring.py` | Update mocks if validation logic changes |
| `tests/test_doc_generator.py` | Update skills rendering tests |
| `tests/test_resume_bank.py` | Update validation tests for new categories |

---

## Verification

1. `py -m pytest tests/ -x -q` -- all tests pass after each change
2. Run tailoring test script (reuse existing DB data, no SerpAPI)
3. Open generated DOCX in Word/LibreOffice and verify:
   - Dates/location right-aligned
   - Primary employer roles grouped under one heading
   - Skills show only "Technical: ... | Platform: ..."
   - At least one earlier role present
   - Bullets read naturally (not copy-pasted)
   - No orphan-word line wraps
   - Page is full (not short)
4. No live SerpAPI calls -- reuse existing DB job data for testing
