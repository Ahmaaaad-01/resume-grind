# Session Handoff 2 — PM Job Pipeline + UI (Updated 2026-03-21)

## 1. What This Project Is

An automated pipeline that discovers entry-level PM job postings via SerpAPI, scores them, tailors resumes via LLM (currently Gemini), generates DOCX resumes, and has a **React/Tailwind web UI** for reviewing jobs and triggering pipeline runs.

Key docs: `docs/Tuning-Round-2.md` (UI plan + discovery audit), `docs/v2-spec.md`

---

## 2. What Is Fully Built and Working

- **Full CLI pipeline**: discovery → filtering → scoring → JD extraction → tailoring → DOCX generation → digest
- **Web UI**: React + Vite + Tailwind dark theme, served by FastAPI
- **347+ tests** across 9 test files
- **All discovered jobs stored in DB** (including rejected ones with `reject_reason`)

### How to Run

**UI (single server — production):**
```
cd ui && npm run build
py -m uvicorn src.api:app --port 8000
# Open http://localhost:8000
```

**UI (dev — hot reload):**
```
# Terminal 1: py -m uvicorn src.api:app --reload --port 8000
# Terminal 2: cd ui && npm run dev
# Open http://localhost:5173
```

**CLI:** `py -m src.main` (live) or `py -m src.main --dry-run`

---

## 3. Current Config State

| Setting | Value | Notes |
|---------|-------|-------|
| Tailoring provider | `gemini` | Changed from claude |
| Gemini model | `gemini-2.5-flash` | |
| Resume threshold | 40 | Changed from 60 |
| Digest threshold | 40 | |
| Pass 1 cutoff | 30/75 | |
| Queries | 6 (5 NYC + 1 remote) | **Approved to change to 4 x 40** |
| Results per query | 10 | **Approved to change to 40** |
| Freshness chip | 3 days | **Approved to change to 7 days** |
| YOE ceiling | 4 years | **Approved to change to 5** |
| Resume bank | Real data at `data/master_resume/resume_bank.json` | |

---

## 4. What Was In Progress — NOT YET CODED

### Discovery Strategy Revision (approved, implementation interrupted)

Full audit and user workshop answers are in `docs/Tuning-Round-2.md` Section 8. Plan file at `C:\Users\fahee\.claude\plans\compiled-shimmying-kernighan.md`.

**Changes to implement:**

1. **config/config.yaml** — Replace 6 queries with 4 new ones:
   - "product manager" — NYC, num=40
   - "product manager" — United States, num=40
   - "associate product manager" — NYC, num=40
   - "product analyst OR growth analyst" — NYC, num=40
   - Set `date_filter: "week"` (7 days)
   - Set YOE ceiling to 5

2. **src/discovery.py** — Read new query config, verify `num=40` works (may need `start` param for pagination)

3. **src/filtering.py** — Update YOE ceiling to 5, fix or remove `check_posting_age()` (currently a no-op — SerpAPI returns relative dates, filter expects ISO)

4. **No changes needed** to main.py, api.py, or UI (they read config dynamically)

---

## 5. Known Bugs

1. **Date hard filter is a no-op** — `check_posting_age()` expects ISO dates but SerpAPI returns "2 days ago". Everything passes. Freshness only enforced by SerpAPI chip.
2. **APM not in title allowlist** — "APM Program" at Robinhood gets rejected. User chose to defer this fix.
3. **DOCX preview quality** — mammoth.js may not perfectly render tab stops / right-aligned dates. Not yet evaluated.
4. **SerpAPI pagination** — Need to verify `num=40` returns 40 results for Google Jobs engine.

---

## 6. Key File Map

```
config/config.yaml              # Queries, filters, scoring, tailoring config
src/api.py                      # FastAPI — jobs API, resume serve, SSE pipeline runs
src/api_models.py               # Pydantic models
src/main.py                     # CLI pipeline orchestrator
src/discovery.py                # SerpAPI queries, normalization, dedup
src/filtering.py                # Title 3-pass, location, YOE, posting age
src/scoring.py                  # Two-pass scoring (0-100)
src/tailoring.py                # LLM resume tailoring (Gemini/Claude)
src/doc_generator.py            # DOCX generation + PDF page-fit loop
src/db.py                       # SQLite schema, CRUD, dedup, reject_reason column
ui/src/App.tsx                  # Main UI — jobs list, actions, modals
ui/src/api.ts                   # Fetch + SSE helpers
docs/Tuning-Round-2.md          # UI plan (sections 1-7) + Discovery audit (section 8)
```

---

## 7. Next Prompt

```
Read docs/Tuning-Round-2.md (Section 8: Discovery Strategy Audit) and docs/session-handoff-2.md.

Then implement the approved discovery strategy revision:

1. Update config/config.yaml:
   - Replace queries with 4 new ones (see Section 8.5 of Tuning-Round-2.md)
   - Set results_per_query: 40
   - Set date_filter: "week"

2. Update src/discovery.py:
   - Read new query config
   - Verify num=40 works with SerpAPI (may need pagination via start param)

3. Update src/filtering.py:
   - Update YOE ceiling from 4 to 5 (check if config-driven or hardcoded)
   - Fix or remove check_posting_age() (currently a no-op)

4. Do NOT change main.py, api.py, or UI (they read config dynamically)

5. Run py -m src.main --dry-run to verify pipeline still works

Do not run live SerpAPI queries without asking first.
```
