# Tuning Round 2 — Job Pipeline UI

## 1. UI Understanding

### Goal
Replace the static HTML digest as the primary interface for reviewing pipeline results. The UI is a local web dashboard that shows all discovered jobs, their scores, attached resumes, and provides controls to trigger pipeline stages independently.

### Main User Flows
1. **Review jobs** — Open the UI, scan jobs grouped by run date (most recent first), sorted by score within each group. Expand a job to see score breakdown. Click to preview resume or open the original posting.
2. **Run full pipeline** — Click "Run SerpAPI + Resume Builder". SerpAPI runs first. When discovery completes, the UI shows newly found jobs with checkboxes (auto-selected if eligible). User reviews, unchecks any they don't want, clicks "Approve & Generate Resumes". Resume generation runs only for approved jobs.
3. **Run discovery only** — Click "Run SerpAPI Query". New jobs appear in the list. No resumes generated.
4. **Generate resumes for existing jobs** — Click "Run Resume Builder". UI shows eligible jobs (score >= threshold, no existing resume) with checkboxes. User unchecks unwanted ones, clicks "Approve & Generate". Resumes built for selected jobs only.

---

## 2. Proposed Architecture

### Stack
- **Backend**: FastAPI (Python) — serves API endpoints, triggers pipeline stages, streams progress via SSE (Server-Sent Events)
- **Frontend**: React + Vite + Tailwind CSS — SPA served by FastAPI in production, Vite dev server during development
- **Data**: Existing SQLite DB (`db/pipeline.db`) — no new database. Backend reads/writes via existing `src/db.py` functions
- **Resume preview**: Backend serves DOCX files via an endpoint. Frontend uses a document viewer library (e.g., mammoth.js for DOCX-to-HTML conversion) for in-browser preview

### How the UI connects to the existing pipeline
- FastAPI imports and calls existing pipeline functions directly (`run_discovery`, `tailor_resume`, `generate_docx`, etc.)
- No subprocess spawning — direct Python function calls
- Progress is reported via SSE: the backend wraps pipeline stages and emits stage-level events
- The existing `main.py` CLI flow remains untouched — the UI is a parallel entry point

### File structure
```
src/
  api.py              # FastAPI app — routes, SSE endpoints, file serving
  api_models.py       # Pydantic models for API request/response
ui/
  package.json
  vite.config.ts
  tailwind.config.ts
  index.html
  src/
    main.tsx
    App.tsx
    api.ts            # Fetch helpers for backend endpoints
    components/
      JobList.tsx
      JobRow.tsx
      JobDetail.tsx       # Expandable score breakdown
      ResumePreview.tsx   # In-browser DOCX preview
      ActionBar.tsx       # 3 top-right buttons
      ProgressBar.tsx     # Stage-based progress indicator
      ApprovalModal.tsx   # Checkbox list for job selection before resume gen
      DateToggle.tsx      # 7-day vs all-non-expired toggle
    hooks/
      useJobs.ts
      usePipelineRun.ts   # SSE subscription for progress
    types.ts
```

---

## 3. Data Model / State Needs

### Job fields the UI needs (from SQLite `jobs` table)
| Field | Source | UI Usage |
|-------|--------|----------|
| `dedup_key` | DB primary key | Unique row ID |
| `title_raw` | DB | Display title |
| `company` | DB | Display company name |
| `location` | DB | Location badge |
| `url` | DB | "Open Job" button link |
| `date_posted` | DB | Recency indicator |
| `first_seen_run` | DB | Group-by-date key |
| `last_seen_run` | DB | 7-day filter logic |
| `final_score` | DB | Score badge + sorting |
| `pass1_score` | DB | Score breakdown |
| `score_breakdown` | DB (JSON string) | Expandable detail — title/YOE/location/company/recency/keyword scores |
| `status` | DB | Status badge, resume availability |
| `resume_path` | DB | Resume preview/download link |
| `jd_source` | DB | Score explanation context |
| `jd_word_count` | DB | Short JD warning |
| `title_experimental` | DB | Warning flag |
| `query_source` | DB | NYC vs Remote badge |

### 7-day caching behavior
- **Default view**: Jobs where `last_seen_run >= (today - 7 days)`
- **Toggle "Show all"**: Jobs where `status NOT IN ('expired')` — up to 14 days
- Filter is applied in the API query, not client-side

### Resume presence/absence reasons
The API computes a `resume_status` field for each job:

| Condition | `resume_status` | Display text |
|-----------|-----------------|--------------|
| `resume_path` exists and file is on disk | `"available"` | Resume preview + download buttons |
| `status == 'resume_generated'` but file missing | `"file_missing"` | "Resume file not found" |
| `final_score < threshold` | `"below_threshold"` | "Score {X} — below {threshold} threshold" |
| `status == 'new'` | `"not_processed"` | "Not yet processed" |
| `status == 'scored'` and score >= threshold | `"pending_generation"` | "Eligible — resume not yet built" |
| `jd_source == 'skipped'` | `"no_jd"` | "JD too short to tailor" |
| `score_breakdown` contains validation errors | `"validation_failed"` | "Tailoring validation failed" |

### Score explanation text
The `score_breakdown` field is already stored as a string repr of the pass2 dict. The API will parse this and return a structured breakdown:
```json
{
  "title": 25,
  "yoe": 18,
  "location": 10,
  "company": 10,
  "recency": 7,
  "keywords": 15,
  "keyword_matched": ["SQL", "agile", "roadmap", ...],
  "keyword_missing": ["go-to-market", "PRD", ...],
  "total": 85
}
```
If `score_breakdown` is not parseable (old data), fall back to showing just `final_score` with "Detailed breakdown unavailable."

---

## 4. Action Button Behavior

### Button 1: "Run SerpAPI + Resume Builder"
- **What it does**: Runs SerpAPI discovery (6 queries), then pauses for user approval before generating resumes
- **Backend trigger**: `POST /api/run/discovery-and-resume`
- **Progress stages**: Discovery (querying SerpAPI) -> Filtering -> Scoring -> **Pause for approval** -> Tailoring -> DOCX Generation -> Done
- **UI behavior**:
  1. Button enters loading state. Progress bar appears with stage indicators.
  2. SSE streams stage updates: "Running SerpAPI query 1/6...", "Filtering 42 jobs...", "Scoring..."
  3. When scoring completes, the progress bar pauses at "Awaiting approval". The ApprovalModal opens showing all jobs that scored >= threshold. Each job has a checkbox (pre-checked) with title, company, score.
  4. User unchecks jobs they don't want, clicks "Approve & Generate Resumes".
  5. `POST /api/run/generate-resumes` with selected `dedup_key` list.
  6. Progress bar resumes: "Tailoring resume 1/5...", "Generating DOCX 1/5...", "Done."
  7. Job list auto-refreshes when complete.

### Button 2: "Run SerpAPI Query"
- **What it does**: Runs SerpAPI discovery only — no filtering, scoring, or resume generation beyond what the pipeline normally does (it still filters and scores, just doesn't generate resumes)
- **Backend trigger**: `POST /api/run/discovery`
- **Progress stages**: Discovery -> Filtering -> Scoring -> Done
- **UI behavior**:
  1. Button enters loading state. Progress bar shows 3 stages.
  2. SSE streams updates.
  3. When done, job list refreshes with new jobs visible.
  4. No approval modal — just discovery + scoring.

### Button 3: "Run Resume Builder"
- **What it does**: Finds all jobs in DB that are eligible for resume generation (score >= threshold, no existing resume, not expired/skipped) and presents them for approval
- **Backend trigger**: `GET /api/jobs/eligible` to fetch the list, then `POST /api/run/generate-resumes` with approved keys
- **Progress stages**: Approval -> Tailoring -> DOCX Generation -> Done
- **UI behavior**:
  1. ApprovalModal opens immediately showing eligible jobs with checkboxes.
  2. User reviews, unchecks unwanted, clicks "Approve & Generate".
  3. Progress bar: "Tailoring resume 1/N...", "Generating DOCX...", "Done."
  4. Job list refreshes.

---

## 5. UI Structure

### Page Layout
```
+------------------------------------------------------------------+
| [Logo/Title: PM Job Pipeline]          [SerpAPI+Resume] [SerpAPI] [Resume Builder] |
+------------------------------------------------------------------+
| [7 Days | All Jobs]  toggle                   [X jobs found]      |
+------------------------------------------------------------------+
|                                                                    |
| --- March 21, 2026 ---                                            |
|                                                                    |
| +--------------------------------------------------------------+ |
| | Score  | Title               | Company  | Location | Resume   | |
| |  85    | APM                 | Stripe   | Remote   | [Preview] | |
| |  72    | Product Manager     | Robinhood| NYC      | [Preview] | |
| |  61    | PM - Payments       | FinApp   | Hybrid   | Score 61  | |
| |        |                     |          |          | — pending | |
| |  45    | Product Analyst     | DataCo   | NYC      | Score 45  | |
| |        |                     |          |          | — below   | |
| +--------------------------------------------------------------+ |
|                                                                    |
| --- March 20, 2026 ---                                            |
| ...                                                                |
+------------------------------------------------------------------+
```

### Per-job row
- **Score badge**: Color-coded (green >= 60, yellow 40-59, gray < 40)
- **Title**: Raw title text
- **Company**: Company name. Target companies get a subtle accent indicator.
- **Location**: NYC / Remote / Hybrid badge
- **Actions**:
  - "Open Job" link — opens `url` in new tab
  - Resume column: either a "Preview" button (opens ResumePreview panel) or a text label explaining why no resume exists
- **Expandable detail** (click score badge or row chevron):
  - Score factor breakdown as horizontal stacked bar or labeled list
  - Keyword match/miss summary
  - JD source and word count
  - Warning flags (experimental title, short JD, target company override, etc.)

### Resume Preview Panel
- Slide-in panel or modal
- DOCX rendered to HTML via mammoth.js (backend converts and serves HTML, or frontend converts client-side)
- "Download DOCX" button in the panel header
- "Open Job Posting" button alongside for quick cross-reference

### Progress Bar
- Fixed position at the top of the page (below header) when a run is active
- Shows: `[Discovery] -> [Filtering] -> [Scoring] -> [Approval] -> [Tailoring] -> [Done]`
- Current stage highlighted in accent color, completed stages in green, upcoming in gray
- Below the bar: one-line status text ("Running SerpAPI query 3/6...")
- Disappears when pipeline completes (with a brief "Complete" state)

### Approval Modal
- Full-screen overlay (dark backdrop)
- Title: "Select jobs for resume generation"
- Table of eligible jobs: checkbox, score, title, company, location
- "Select All" / "Deselect All" controls
- Footer: "Generate Resumes for N selected jobs" button + "Cancel"
- Shows total estimated API calls (N Gemini calls)

### Empty / Loading / Error States
- **No jobs**: "No jobs found. Run a SerpAPI query to discover new opportunities."
- **Loading**: Skeleton rows while fetching
- **Pipeline error**: Toast notification with error message. Jobs list remains visible. Failed jobs show error status.
- **No eligible jobs for resume builder**: "No eligible jobs found. All scored jobs either already have resumes or are below the score threshold."

---

## 6. Implementation Plan

### Build Order

#### Phase 1: Backend API (build first — can test with curl)
1. **`src/api.py`** — FastAPI app with these endpoints:
   - `GET /api/jobs` — list jobs with filters (days, status)
   - `GET /api/jobs/{dedup_key}` — single job detail with parsed score breakdown
   - `GET /api/jobs/eligible` — jobs eligible for resume generation
   - `GET /api/resumes/{dedup_key}` — serve DOCX file for download
   - `GET /api/resumes/{dedup_key}/preview` — serve DOCX converted to HTML
   - `POST /api/run/discovery` — run SerpAPI + filter + score (SSE progress)
   - `POST /api/run/generate-resumes` — generate resumes for selected jobs (SSE progress)
   - `POST /api/run/discovery-and-resume` — combined flow (SSE with pause point)
   - `GET /api/config/thresholds` — return current score thresholds
2. **`src/api_models.py`** — Pydantic request/response models
3. **Refactor `main.py`** — Extract pipeline stages into callable functions that accept a progress callback, so the API can report stage-level progress without duplicating orchestration logic

#### Phase 2: Frontend scaffold
4. **`ui/` project init** — Vite + React + TypeScript + Tailwind
5. **Tailwind config** — Set up dark theme tokens from `docs/ui-specs/tokens.json` (colors, fonts, spacing, radius — skip glassmorphism/glow)
6. **`api.ts`** — Fetch helpers + SSE subscription utility
7. **`types.ts`** — TypeScript types matching API response shapes

#### Phase 3: Core UI components
8. **`App.tsx` + `JobList.tsx`** — Main layout, header with action buttons, date-grouped job table
9. **`JobRow.tsx`** — Single job row with score badge, company, location, actions
10. **`JobDetail.tsx`** — Expandable score breakdown panel
11. **`DateToggle.tsx`** — 7-day vs all-non-expired toggle

#### Phase 4: Actions + Resume
12. **`ActionBar.tsx`** — 3 top-right buttons with loading states
13. **`ProgressBar.tsx`** — Stage-based progress indicator with SSE integration
14. **`ApprovalModal.tsx`** — Job selection before resume generation
15. **`ResumePreview.tsx`** — In-browser DOCX preview + download

#### Phase 5: Polish + Integration
16. Wire up all components end-to-end
17. Error handling, empty states, loading skeletons
18. Responsive layout (desktop-first, basic mobile support)
19. Add `py -m src.api` as the entry point (serves both API and built frontend)

### Likely Risks / Blockers
- **DOCX preview quality**: mammoth.js produces decent HTML from simple DOCX but may not perfectly render the resume's formatting (right-aligned dates, tab stops). May need to fall back to PDF preview if quality is poor.
- **SSE on Windows**: FastAPI + SSE should work fine, but test early — Windows can have quirks with streaming responses.
- **Pipeline refactor scope**: Extracting stage-level functions from `main.py` with progress callbacks needs care to avoid breaking the CLI flow. Keep the CLI path untouched; the API calls the same functions but wraps them.
- **Concurrent runs**: If the user clicks two action buttons, the pipeline could run twice simultaneously. Need a simple lock (in-memory flag) to prevent overlapping runs.
- **LibreOffice dependency for PDF**: Resume preview via PDF rendering requires LibreOffice. The mammoth.js approach avoids this dependency for preview, but quality tradeoff exists.

### What to build first
Phase 1 (backend API) is the foundation. It can be tested with curl before any frontend exists. Phase 3 (job list + score breakdown) delivers the core value — seeing all jobs and understanding scores. Phase 4 (action buttons + approval flow) is where the UI becomes more useful than the CLI.

---

## 7. Open Questions

1. **Port number**: Should the local server run on `localhost:8000` (FastAPI default) or a different port? This is minor but worth locking.
2. **Auth**: Since this is local-only, no auth is planned. If you ever want to expose it on a LAN or VPN, we'd need to add basic auth. Confirm local-only is fine for v1.
3. **DOCX preview fallback**: If mammoth.js preview quality is poor for the resume format (tab stops, right-aligned dates), should we fall back to (a) PDF-in-browser via LibreOffice conversion, or (b) just offer download-only and skip preview? We'll evaluate after building.

---

## 8. Discovery Strategy Audit

### 8.1 Current Funnel Analysis

The pipeline has a theoretical ceiling of 60 raw results (6 queries x 10 each). Here's where volume drops:

| Stage | Estimated Count | Drop | Why |
|-------|----------------|------|-----|
| Raw results | 60 max | — | 6 queries x 10 |
| After within-run dedup | ~25-35 | ~40-50% | 5 NYC queries heavily overlap — Google Jobs semantic matching returns the same listings for "associate product manager", "product manager entry level", "junior product manager", and broad "product manager" |
| After cross-run DB dedup | ~15-25 | ~30% on repeat runs | 3-day SerpAPI chip means the same jobs reappear daily. DB marks them as already-processed |
| After title filter | ~8-18 | ~30-40% | Denylist + default-reject is strict. Confirmed false negative: "APM Program" at Robinhood rejected because `\bapm\b` not in allowlist |
| After location filter | ~7-16 | ~5-10% | Mostly redundant — SerpAPI queries already specify NYC/US location |
| After YOE filter | ~6-14 | ~10-15% | Current ceiling of 4 years rejects common "3-5 years" phrasing |
| After date filter | ~6-14 | ~0% | **No-op bug**: SerpAPI returns relative strings ("2 days ago"), but `check_posting_age()` expects ISO dates. Unparseable = pass. |
| After Pass 1 cutoff (30/75) | ~5-12 | ~10% | Moderate cutoff |
| After JD extraction (min 50 words) | ~4-10 | ~10-20% | Some JDs fail fetch or are too short |
| Final scored output | ~3-8 | — | Realistic per-run output |

**Key finding**: Effective unique input is ~25-35 jobs, not 60. The problem is a combination of query overlap, low per-query num, and some filter-level false negatives.

### 8.2 Root Cause Ranking

1. **Top-of-funnel too small and too overlapping (highest impact)** — 5 NYC queries produce ~20-30 unique results because Google Jobs semantic matching returns the same listings for varied phrasings of "product manager." The broad catch-all query (query 5) returns a superset of queries 1-4.

2. **Low per-query result count** — `num: 10` only shows page 1 of Google Jobs. Pages 2-4 contain niche/long-tail listings (exactly where APM programs and startup roles hide). Increasing `num` is free — SerpAPI doesn't charge more per result within a query.

3. **Cross-run dedup in steady state** — With a 3-day SerpAPI freshness chip and daily runs, ~60% of results each day are repeats. Expanding to 7 days doesn't increase repeats (DB dedup handles them) but provides a safety net for sporadic run cadence.

4. **Title filter false negatives** — "APM" abbreviation rejected. Date filter is a no-op. YOE ceiling of 4 rejects realistic "3-5 year" jobs.

5. **Remote underrepresented** — Only 1 of 6 queries targets remote, but target companies (Robinhood, Stripe, Coinbase) are remote-friendly. However, user prefers keeping NYC-heavy focus.

### 8.3 Confirmed Bugs

1. **Date filter is a no-op** — `check_posting_age()` calls `date.fromisoformat()` on SerpAPI's relative date strings like "2 days ago" or "Today". This always fails to parse, so the filter passes everything by default. The freshness constraint only comes from SerpAPI's `date_posted` chip.

2. **APM not in title allowlist** — Any job titled "APM", "APM Program", or similar without spelling out "Associate Product Manager" gets rejected by default. The `normalize_title` function converts "apm" to "product manager" but only runs *after* a title passes the filter. User chose to skip this fix for now.

### 8.4 User Workshop Answers

| Question | Answer |
|----------|--------|
| Recall vs precision | **High recall** — cast a wider net, tolerate some junk |
| Remote ratio | **Keep 83/17 NYC-heavy** — NYC is primary market |
| Query count | **4 queries x 40 results** — bigger funnel, filtered downstream |
| Freshness window | **7 days** — safety net for sporadic runs |
| PM-adjacent roles | **Actively search** — dedicate a query to product analyst, growth, etc. |
| YOE ceiling | **Raise to 5 years** — accept "3-5 years" range jobs |
| APM allowlist fix | **Skip for now** — revisit later |
| Run cadence | **Sporadic** — not daily, wider window matters |

### 8.5 Revised Discovery Strategy

**Query philosophy**: Fewer, broader queries with high `num` to maximize unique results. Let scoring handle ranking instead of relying on narrow queries.

**Revised queries (4 queries x 40 results = 160 raw)**:

| # | Query | Location | num | Purpose |
|---|-------|----------|-----|---------|
| 1 | "product manager" | New York, NY | 40 | Broad NYC PM catch-all. Google returns APM, junior PM, entry-level PM variants naturally. |
| 2 | "product manager" | United States | 40 | Remote + national roles. Distinct location = low overlap with query 1. |
| 3 | "associate product manager" | New York, NY | 40 | Targeted early-career NYC. Some overlap with query 1 but surfaces long-tail results on pages 2-4. |
| 4 | "product analyst OR growth analyst" | New York, NY | 40 | PM-adjacent roles. Experimental allowlist already accepts these titles. |

**Estimated unique results**: ~90-110 per run (vs ~25-35 today). The location split (NYC vs US) ensures queries 1 and 2 have minimal overlap. Queries 3 and 4 target specific niches with some overlap to query 1 on page 1 but unique results on deeper pages.

**SerpAPI cost**: 4 calls per run vs 6 today. Net savings of 2 API calls despite much higher volume.

**Revised filters**:

| Filter | Current | Revised | Why |
|--------|---------|---------|-----|
| SerpAPI freshness chip | 3 days | 7 days | Sporadic run cadence; DB dedup prevents reprocessing |
| Per-query num | 10 | 40 | Free volume; pages 2-4 have long-tail niche roles |
| YOE ceiling | 4 years | 5 years | Accept common "3-5 years" phrasing |
| Date hard filter | 3 days (but bugged) | Remove or fix | Currently a no-op; SerpAPI chip handles freshness |
| APM allowlist | Not included | No change for now | User chose to skip |

**How to judge success**: After implementing these changes, run the pipeline once and compare:
- Raw results (should be ~120-160 vs ~60)
- Unique after dedup (should be ~90-110 vs ~25-35)
- Through full filter funnel (should be ~15-30 vs ~3-8)
- Monitor for 3 runs to confirm steady-state improvement

### 8.6 Implementation Files

| File | Changes |
|------|---------|
| `config/config.yaml` | Update query definitions (4 queries, num: 40, date_filter: "week"), raise yoe_max to 5 |
| `src/discovery.py` | Update to use new query config (fewer queries, higher num) |
| `src/filtering.py` | Fix or remove `check_posting_age()` (currently no-op), update YOE ceiling |
| `src/main.py` | No changes expected (reads config dynamically) |
| `src/api.py` | No changes expected (calls discovery functions) |

### 8.7 Risks

- **Higher volume = more LLM calls for resume tailoring**: With more jobs passing filters, more will hit the resume generation threshold. The approval modal in the UI mitigates this (user manually selects which jobs get resumes).
- **Page 3-4 Google Jobs results are lower quality**: More junk titles may appear, but the title filter + scoring should handle this. Monitor false positive rate after first run.
- **SerpAPI pagination behavior**: Verify that `num=40` actually returns 40 results and not just 10. May need to use `start` parameter for pagination if SerpAPI caps at 10 per request for Google Jobs.
