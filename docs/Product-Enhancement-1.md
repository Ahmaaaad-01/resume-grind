# Product Enhancement 1 — Manual Job Submission

## 1. Enhancement Understanding

### Goal
Allow the user to manually submit a job posting and generate a tailored resume for it — bypassing the SerpAPI discovery/scoring pipeline entirely. This covers jobs found through networking, referrals, or browsing that the automated pipeline didn't surface.

### Main User Flow
1. User clicks **"+ Submit Job"** button in the header.
2. A modal opens with a form: JD text (required), URL (optional), company (optional), title (optional).
3. User pastes JD text and optionally fills in other fields, then clicks **"Generate Resume."**
4. Button shows a loading spinner (~10-30 seconds). Backend infers company/title if not provided, runs tailoring + DOCX generation (no scoring).
5. Modal closes on success. Toast notification confirms: "Resume generated for {company}."
6. User switches to the **"Manual Jobs"** tab to see their submission with Preview/Download actions.
7. User can re-generate the resume, delete the entry, or preview/download the DOCX.

---

## 2. Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Data model | Same `jobs` table + `source` column | Reuses existing DB/API functions. Tab filters by `source='manual'`. Many fields will be null for manual jobs. |
| JD input | Always require pasted JD text | URL is optional metadata only (for "Open Job" link). Avoids scraping failures. |
| Scoring | Skip scoring entirely, keep validation | User already decided the job is worth applying to. Validation still checks source_ids and derived bullet limits. |
| Entry UI | Modal/dialog | Consistent with existing `ApprovalModal` pattern. Stays on the same page. |
| Editability | Re-run only | Can re-generate resume on same JD. No editing of JD/company/title. Submit a new entry if inputs were wrong. |
| Row metadata | Title, Company, Date submitted, Resume actions | No score badge (not applicable). Clean and focused. |
| Deletion | Delete record + DOCX file | With confirmation dialog. Clean removal. |
| Progress UX | Loading spinner on button | Modal closes on completion. Toast for success/failure. No SSE needed for single job. |

**Assumptions:**
- Manual jobs are never picked up by SerpAPI pipeline logic (expiration, resurfacing, dedup checks).
- Manual jobs do not appear in the "eligible jobs" list for batch resume generation.
- The "Manual Jobs" tab is a peer tab alongside "Discovered Jobs" — not a separate page.

---

## 3. Proposed Architecture

### Backend Changes

| Layer | Change |
|-------|--------|
| **DB** | Add `source TEXT DEFAULT 'serpapi'` column to `jobs` table. Add `insert_manual_job()` and `delete_job()` helpers. |
| **API** | 4 new endpoints: submit, list, delete, regenerate manual jobs. |
| **Models** | `ManualJobRequest`, `ManualJobResponse`, `ManualJobListResponse` Pydantic models. Add `source` to existing `JobResponse`. |
| **Inference** | New `src/manual_inference.py` — lightweight regex for company/title extraction from JD text. |

### Frontend Changes

| Layer | Change |
|-------|--------|
| **App.tsx** | Tab navigation between "Discovered Jobs" and "Manual Jobs". Modal trigger state. |
| **ActionBar** | Add "+ Submit Job" button. |
| **New components** | `ManualJobModal`, `ManualJobList`, `ManualJobRow`, `DeleteConfirmModal`. |
| **New hook** | `useManualJobs.ts` — fetch/refresh manual jobs list. |
| **API client** | `submitManualJob()`, `fetchManualJobs()`, `deleteManualJob()`, `regenerateManualJob()`. |

### How It Fits the Existing Pipeline

The manual submission flow calls the **same** tailoring and DOCX modules directly:
- `tailor_resume(job_dict, jd_text, bank, config)` — no changes needed
- `generate_docx(tailored, bank, job_meta)` — no changes needed
- `load_resume_bank()` — no changes needed
- Existing resume endpoints (`/api/resumes/{dedup_key}/download` and `/preview`) work unchanged since they look up by `dedup_key`

The SerpAPI pipeline is unaffected. The `source` column cleanly separates the two job populations.

---

## 4. Data Model / Persistence

### New Column

```sql
ALTER TABLE jobs ADD COLUMN source TEXT DEFAULT 'serpapi';
```

Migration in `init_db()` follows the existing pattern (check if column exists, ALTER if not). All existing rows get `'serpapi'` as default.

### Dedup Key for Manual Jobs

SerpAPI jobs use `make_dedup_key(company, title, location)` — a hash. Manual jobs use a UUID prefix to avoid collisions and allow duplicate JD submissions:

```python
dedup_key = f"manual-{uuid.uuid4().hex[:12]}"
```

### Fields Populated for Manual Jobs

| Field | Value | Notes |
|-------|-------|-------|
| `dedup_key` | `manual-{uuid12}` | UUID-based, not hash |
| `title_raw` | User-provided or inferred | Default: "Product Manager" |
| `title_normalized` | Lowercased title_raw | |
| `company` | User-provided or inferred | Default: "Company" |
| `location` | `"Manual submission"` | Static placeholder |
| `url` | User-provided or `""` | Optional |
| `date_posted` | `None` | Not applicable |
| `first_seen_run` | Today's ISO date | |
| `last_seen_run` | Today's ISO date | |
| `times_seen` | `1` | |
| `pass1_score` | `None` | Scoring skipped |
| `final_score` | `None` | Scoring skipped |
| `status` | `"resume_generated"` | Set after successful generation |
| `resume_path` | Path to DOCX | |
| `jd_text` | Full pasted JD | |
| `jd_source` | `"manual_paste"` | New source value |
| `jd_word_count` | `len(jd_text.split())` | |
| `title_experimental` | `0` | |
| `query_source` | `None` | Not applicable |
| `score_breakdown` | `None` | Scoring skipped |
| `gaps` | From tailoring output | |
| `source` | `"manual"` | New column |

### Pipeline Isolation

Existing queries need `WHERE source != 'manual'` (or `source = 'serpapi'`) to exclude manual jobs from:
- `GET /api/jobs` (discovered jobs list)
- `GET /api/jobs/eligible` (batch resume generation candidates)
- `expire_old_jobs()` — manual jobs should not expire
- `decide_action()` — should never see manual jobs

The `_compute_resume_status()` function needs a manual-job code path: if `source == 'manual'`, skip score-based logic and return status based purely on whether `resume_path` exists and the file is on disk.

---

## 5. UX / UI Structure

### Entry Point

A **"+ Submit Job"** button added to the `ActionBar`, visually distinct from the pipeline action buttons (separated by a divider or positioned on the left).

### Tab Navigation

Below the header, above the view toggle area:

```
[ Discovered Jobs ]  [ Manual Jobs (3) ]
```

- **Discovered Jobs** — current behavior (SerpAPI pipeline jobs)
- **Manual Jobs** — manually submitted jobs with resumes
- Count badge shows total manual jobs
- The "Last 7 Days / All Jobs" toggle only appears on the Discovered tab

### ManualJobModal Layout

```
+----------------------------------------------------+
|  Submit Job for Resume Generation              [X]  |
|----------------------------------------------------|
|                                                     |
|  Job Description *                                  |
|  +------------------------------------------------+|
|  |  (textarea, ~10 rows)                          ||
|  |                                                 ||
|  +------------------------------------------------+|
|  Word count: 342                                    |
|                                                     |
|  Company (optional)                                 |
|  [____________________________]                     |
|  Leave blank to auto-detect from JD                 |
|                                                     |
|  Job Title (optional)                               |
|  [____________________________]                     |
|  Leave blank to auto-detect from JD                 |
|                                                     |
|  Job URL (optional)                                 |
|  [____________________________]                     |
|  For "Open Job" link only                           |
|                                                     |
|  [Cancel]                [Generate Resume (spinner)]|
+----------------------------------------------------+
```

### Form States

| State | Behavior |
|-------|----------|
| **Empty** | Generate button disabled until JD text >= 50 words |
| **Valid** | Generate button enabled, word count shown |
| **Loading** | Button shows spinner + "Generating...", all fields disabled |
| **Success** | Modal closes, toast: "Resume generated for {company}" |
| **Failure** | Red error banner at bottom of modal, form stays open for retry |

### Manual Jobs Tab Layout

```
| Title / Company        | Date Submitted  | Resume        | Actions          |
|------------------------|-----------------|---------------|------------------|
| Product Manager        | Mar 21, 2026    | [Preview] [DL]| [Open] [Re-gen] [Del] |
|   Stripe               |                 |               |                  |
| Product Manager        | Mar 20, 2026    | [Preview] [DL]| [Re-gen] [Del]   |
|   Company              |                 |               |                  |
```

- **Title/Company**: Title bold, company muted below
- **Date Submitted**: `created_at` formatted
- **Resume**: Preview / Download buttons (reuses existing `ResumePreview` modal)
- **Actions**: "Open Job" (if URL provided, grayed out if not), "Re-generate" button, "Delete" button (red, triggers confirmation)

### Delete Confirmation Modal

```
+------------------------------------------+
|  Delete Manual Job?                       |
|                                           |
|  This will permanently delete the job     |
|  record and its generated resume file.    |
|                                           |
|  Product Manager at Stripe                |
|                                           |
|  [Cancel]                 [Delete (red)]  |
+------------------------------------------+
```

### Empty State (Manual Jobs Tab)

> No manual jobs yet. Click "+ Submit Job" to generate a tailored resume from any job description.

---

## 6. Processing Flow

### Manual JD Submission (`POST /api/manual-jobs`)

```
1. Receive: { jd_text, url?, company?, title? }
2. Validate: jd_text >= 50 words → 422 if too short
3. Infer company (if blank):
   - Regex patterns: "Company: X", "About X", "X is hiring"
   - Default: "Company"
4. Infer title (if blank):
   - Regex patterns: "Job Title: X", "Position: X", first line with PM-like keywords
   - Default: "Product Manager"
5. Generate dedup_key: f"manual-{uuid.uuid4().hex[:12]}"
6. Load config + resume bank
7. Build job dict for tailoring pipeline
8. tailor_resume(job, jd_text, bank, config)
9. validate_tailored_output(tailored, bank) — log errors but proceed
10. generate_docx(tailored, bank, job_meta)
11. Insert record into DB (source='manual', status='resume_generated')
12. Return ManualJobResponse with job data + resume_path
```

### Re-generation (`POST /api/manual-jobs/{dedup_key}/regenerate`)

```
1. Look up job by dedup_key, verify source='manual'
2. Delete existing DOCX file (if any)
3. Re-run tailor_resume with stored jd_text
4. Re-run generate_docx
5. Update DB record (new resume_path, updated_at)
6. Return updated ManualJobResponse
```

### Deletion (`DELETE /api/manual-jobs/{dedup_key}`)

```
1. Look up job, verify source='manual'
2. Delete DOCX file from disk (if exists)
3. Delete DB record
4. Return 204 No Content
```

### Company/Title Inference (`src/manual_inference.py`)

Lightweight regex-based — no LLM calls:

```python
def infer_company(jd_text: str) -> str:
    """Extract company name from JD text. Returns 'Company' if not found."""
    patterns = [
        r"(?:Company|Employer|Organization):\s*(.+?)(?:\n|$)",
        r"(?:About|Join)\s+([A-Z][A-Za-z0-9\s&]+?)(?:\n|\.)",
        r"([A-Z][A-Za-z0-9\s&]+?)\s+is\s+(?:hiring|looking|seeking)",
    ]
    # First match wins → clean up → return
    # Fallback: "Company"

def infer_title(jd_text: str) -> str:
    """Extract job title from JD text. Returns 'Product Manager' if not found."""
    patterns = [
        r"(?:Job Title|Position|Role):\s*(.+?)(?:\n|$)",
        # First line heuristic for titles containing PM-like keywords
    ]
    # First match wins → clean up → return
    # Fallback: "Product Manager"
```

---

## 7. File/Module Impact

### Backend — Files to Modify

| File | Changes |
|------|---------|
| [db.py](src/db.py) | Add `source` column migration in `init_db()`. Add `insert_manual_job()` and `delete_job()` helpers. Add `WHERE source != 'manual'` to existing queries that shouldn't include manual jobs. |
| [api.py](src/api.py) | Add 4 endpoints: `POST /api/manual-jobs`, `GET /api/manual-jobs`, `DELETE /api/manual-jobs/{dedup_key}`, `POST /api/manual-jobs/{dedup_key}/regenerate`. Update `_compute_resume_status()` for manual jobs. Update `_row_to_job()` to include `source` field. Filter manual jobs from `GET /api/jobs` and `GET /api/jobs/eligible`. |
| [api_models.py](src/api_models.py) | Add `ManualJobRequest`, `ManualJobResponse`, `ManualJobListResponse`. Add `source` field to existing `JobResponse`. |

### Backend — New Files

| File | Purpose |
|------|---------|
| [manual_inference.py](src/manual_inference.py) | `infer_company()` and `infer_title()` regex heuristics. ~50 lines. |

### Frontend — Files to Modify

| File | Changes |
|------|---------|
| [App.tsx](ui/src/App.tsx) | Add tab state + tab bar. Conditional rendering of `JobList` vs `ManualJobList`. `ManualJobModal` open/close state. Toast handling for manual operations. |
| [ActionBar.tsx](ui/src/components/ActionBar.tsx) | Add "+ Submit Job" button with `onSubmitJob` callback. |
| [api.ts](ui/src/api.ts) | Add `submitManualJob()`, `fetchManualJobs()`, `deleteManualJob()`, `regenerateManualJob()`. |
| [types.ts](ui/src/types.ts) | Add `ManualJobRequest`, `ManualJob`, `ManualJobListResponse` interfaces. |

### Frontend — New Files

| File | Purpose |
|------|---------|
| [ManualJobModal.tsx](ui/src/components/ManualJobModal.tsx) | Submission form modal with JD textarea, optional fields, Generate button, spinner. |
| [ManualJobList.tsx](ui/src/components/ManualJobList.tsx) | List view for manual jobs (different columns from discovered jobs). |
| [ManualJobRow.tsx](ui/src/components/ManualJobRow.tsx) | Row component: Title/Company, Date, Resume actions, Delete. |
| [DeleteConfirmModal.tsx](ui/src/components/DeleteConfirmModal.tsx) | Confirmation dialog for deletion. |
| [useManualJobs.ts](ui/src/hooks/useManualJobs.ts) | Hook to fetch/refresh manual jobs list. |

---

## 8. Implementation Plan

### Phase 1: Backend Foundation

**Step 1.1 — DB migration + inference module**
- Add `source` column migration to `init_db()` in `src/db.py`
- Add `insert_manual_job()` helper to `src/db.py`
- Add `delete_job()` helper to `src/db.py`
- Create `src/manual_inference.py` with `infer_company()` and `infer_title()`
- Test: run `init_db()` against existing DB, verify migration works

**Step 1.2 — API models + endpoints**
- Add Pydantic models to `src/api_models.py`
- Add `source` field to existing `JobResponse`
- Add 4 new endpoints to `src/api.py`
- Update `_compute_resume_status()` and `_row_to_job()` for manual job awareness
- Add isolation filters (`WHERE source != 'manual'`) to existing discovered-job queries
- Test: curl/httpie to submit a manual job, verify DB record + DOCX creation

### Phase 2: Frontend — Tab Navigation + List

**Step 2.1 — Types + API client**
- Add new types to `types.ts`
- Add new API functions to `api.ts`

**Step 2.2 — Tab navigation**
- Add `activeTab` state to `App.tsx`
- Render tab bar, conditionally render `JobList` vs `ManualJobList`
- Move "Last 7 Days / All Jobs" toggle to Discovered tab only

**Step 2.3 — Manual jobs list + row**
- Create `useManualJobs.ts` hook
- Create `ManualJobList.tsx` and `ManualJobRow.tsx`
- Wire Preview/Download to existing `ResumePreview` modal

### Phase 3: Frontend — Submit + Delete Modals

**Step 3.1 — ManualJobModal**
- Create form modal (reference `ApprovalModal` patterns)
- JD textarea with live word count, optional fields
- Submit handler → spinner → success (close + toast) / error (inline)

**Step 3.2 — DeleteConfirmModal**
- Simple confirmation modal
- On confirm: call delete endpoint, refresh list, show toast

**Step 3.3 — Wire up in App.tsx**
- "+ Submit Job" button in ActionBar
- Modal open/close state management
- Re-generate flow (call regenerate, spinner on row, refresh on completion)
- End-to-end test: submit → appears in tab → preview → download → delete

### Phase 4: Polish + Edge Cases

- Handle re-generate spinner state on individual rows
- Handle DOCX file deleted externally (show "file_missing" status)
- Verify `expire_old_jobs()` and `decide_action()` do not affect manual jobs
- Verify existing resume preview/download endpoints work for manual dedup keys
- Ensure the manual submission endpoint uses `asyncio.to_thread()` to avoid blocking the event loop

### Risks / Blockers

| Risk | Mitigation |
|------|------------|
| Synchronous LLM call blocks Uvicorn (10-30s) | Wrap in `asyncio.to_thread()`. Acceptable for single-user local tool. |
| Resume bank not found at submission time | Return clear 500 error with setup instructions. |
| Inference regex misidentifies company/title | Defaults ("Company" / "Product Manager") are safe fallbacks. User can also just fill in the fields. |
| Existing queries accidentally include manual jobs | Add `WHERE source != 'manual'` to all SerpAPI-related queries in Phase 1. |

### What to Build First
Phase 1 (backend) is the foundation — can be tested with curl before any frontend exists. Phase 2 (tab + list) provides visibility. Phase 3 (modals) makes the feature usable end-to-end.

---

## 9. Open Questions

1. **Async wrapping**: The manual submit endpoint runs a synchronous LLM call for ~10-30 seconds. Should this be wrapped in `asyncio.to_thread()` to avoid blocking the event loop? **Recommendation: yes**, small change, prevents the UI from hanging on other requests during generation.

2. **Tab badge**: Should the Manual Jobs tab show a count badge (e.g., "Manual Jobs (3)")? **Recommendation: yes**, provides useful context at a glance. Count from `ManualJobListResponse.total`.

3. **Minimum JD length**: Should manual submissions enforce the same 50-word minimum as the automated pipeline? **Recommendation: yes** — JDs shorter than 50 words will produce poor-quality tailored resumes regardless of source.
