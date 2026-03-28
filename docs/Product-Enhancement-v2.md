# Product Enhancement v2 — Cloud Deployment (Multi-Tenant)

## Context

The PM Job Pipeline is a fully functional local application (FastAPI + React + SQLite) that discovers PM jobs, scores them, and generates tailored resumes. The goal is to **deploy it publicly** on Railway so that 2-5 friends can each create an account (Google sign-in), enter their own API keys, upload their resume bank, and use the full pipeline independently — all from the same hosted URL.

### User Requirements Summary
- **Hosting**: Railway (single deploy — FastAPI serves frontend + API)
- **Auth**: Google sign-in only (no passwords)
- **Multi-tenant**: Each user has their own jobs, resumes, keys, and resume bank
- **API keys**: Users enter their own SerpAPI/Claude/Gemini keys in a Settings page
- **Resume bank**: Users upload their own resume_bank.json via the UI
- **File storage**: Generated DOCX resumes stored as BLOBs in the database
- **Database**: Keep SQLite (on Railway persistent volume)
- **Scale**: 2-5 users
- **Budget**: $0 (free tiers only)

---

## 1. Deployment Goal

**Publicly hosted multi-tenant web app.** One Railway URL, Google sign-in, each user brings their own API keys and resume bank. All data isolated per user. Zero cost on free tiers.

---

## 2. Recommended Deployment Approach

**Single Railway service** running FastAPI (serves React SPA + API). SQLite on a persistent volume. Google OAuth for auth. JWT sessions. DOCX files stored as BLOBs in SQLite.

**Why this fits:**
- One thing to deploy and maintain (not separate frontend/backend/DB services)
- Railway free tier: 500 hours/month of compute + 1GB persistent volume — plenty for 2-5 users
- SQLite is fine at this scale and avoids a separate DB service
- Google sign-in means no password management, no email service needed
- Storing DOCX in DB means no separate file storage service

**Trade-off acknowledged:** If you later grow past ~10 concurrent users, you'd want to migrate to Postgres + proper file storage. But for MVP with 2-5 users, this is the right call.

---

## 3. System Architecture for Deployment

```
Users access: https://your-app.up.railway.app
                    │
                    ▼
┌──────────────────────────────────────────────────┐
│          Railway Service (FastAPI + Uvicorn)       │
│                                                    │
│  ┌──────────────┐    ┌─────────────────────────┐  │
│  │  React SPA   │    │     REST API + SSE       │  │
│  │  (ui/dist/)  │    │                          │  │
│  │              │    │  /api/auth/*   (Google)   │  │
│  │  - Login     │    │  /api/settings/* (keys)  │  │
│  │  - Dashboard │    │  /api/jobs/*              │  │
│  │  - Settings  │    │  /api/run/*   (pipeline)  │  │
│  └──────────────┘    └─────────────────────────┘  │
│                           │                        │
│              ┌────────────┴────────────┐           │
│              ▼                         ▼           │
│  ┌─────────────────────┐  ┌────────────────────┐  │
│  │  SQLite (volume)     │  │  Outbound APIs     │  │
│  │  - users             │  │  - SerpAPI         │  │
│  │  - jobs (per user)   │  │  - Claude/Gemini   │  │
│  │  - user_settings     │  │  - Google OAuth    │  │
│  │  - resume_files      │  │                    │  │
│  └─────────────────────┘  └────────────────────┘  │
│         │                                          │
│  Railway Persistent Volume (1GB)                   │
└──────────────────────────────────────────────────┘
```

---

## 4. Data / Privacy / Secrets Strategy

### App-level secrets (Railway env vars — you set these once)
| Secret | Purpose |
|--------|---------|
| `GOOGLE_CLIENT_ID` | Google OAuth client ID |
| `GOOGLE_CLIENT_SECRET` | Google OAuth client secret |
| `JWT_SECRET` | Signs auth tokens (generate a random 64-char string) |
| `ENCRYPTION_KEY` | Encrypts user API keys at rest (Fernet key) |

### Per-user secrets (entered in Settings UI, stored encrypted in DB)
| Secret | Purpose |
|--------|---------|
| `serpapi_key` | User's SerpAPI key |
| `anthropic_api_key` | User's Claude API key |
| `gemini_api_key` | User's Gemini API key |

### Encryption approach
- Use Python's `cryptography.fernet` module
- One `ENCRYPTION_KEY` env var (set on Railway)
- All user API keys encrypted before DB storage, decrypted only when making API calls
- If the encryption key is lost, users re-enter their keys (not catastrophic)

### Resume bank
- Uploaded as JSON via Settings page
- Stored in `user_settings.resume_bank_json` column (TEXT, can be large)
- Validated on upload (same validation as current `validate_resume_bank()`)

### Generated DOCX files
- Stored in `resume_files` table as BLOBs
- Linked to user_id + dedup_key
- Downloaded via API endpoint (auth-protected)

---

## 5. Database Schema Changes

### New tables

```sql
-- Users (from Google OAuth)
CREATE TABLE users (
    id TEXT PRIMARY KEY,              -- UUID
    email TEXT UNIQUE NOT NULL,
    name TEXT,
    google_id TEXT UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Per-user settings and API keys
CREATE TABLE user_settings (
    user_id TEXT PRIMARY KEY REFERENCES users(id),
    serpapi_key_enc TEXT,              -- Fernet-encrypted
    anthropic_key_enc TEXT,           -- Fernet-encrypted
    gemini_key_enc TEXT,              -- Fernet-encrypted
    resume_bank_json TEXT,            -- Full resume bank JSON
    tailoring_provider TEXT DEFAULT 'gemini',  -- 'claude' or 'gemini'
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Resume file storage (BLOBs)
CREATE TABLE resume_files (
    id TEXT PRIMARY KEY,              -- UUID
    user_id TEXT NOT NULL REFERENCES users(id),
    dedup_key TEXT NOT NULL,
    filename TEXT NOT NULL,
    content BLOB NOT NULL,
    content_type TEXT DEFAULT 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, dedup_key)
);
```

### Modified table: `jobs`
```sql
-- Add user_id column to jobs table
ALTER TABLE jobs ADD COLUMN user_id TEXT REFERENCES users(id);
CREATE INDEX idx_jobs_user ON jobs(user_id);
```

Every query against `jobs` must now filter by `user_id`.

---

## 6. New API Endpoints

### Auth endpoints
| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/api/auth/google` | Receive Google ID token, verify, create/find user, return JWT |
| `GET` | `/api/auth/me` | Return current user info (from JWT) |
| `POST` | `/api/auth/logout` | Client-side only (discard JWT) |

### Settings endpoints
| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/api/settings` | Get current user's settings (keys masked) |
| `PUT` | `/api/settings/keys` | Update API keys (encrypted before storage) |
| `PUT` | `/api/settings/resume-bank` | Upload/update resume bank JSON |
| `GET` | `/api/settings/resume-bank` | Download current resume bank |
| `GET` | `/api/settings/status` | Check which keys are configured (boolean flags, not values) |

### Modified endpoints (add auth)
All existing `/api/jobs/*`, `/api/manual-jobs/*`, `/api/run/*`, `/api/resumes/*` endpoints need:
- JWT auth middleware (extract user_id from token)
- Filter all DB queries by user_id
- Use user's API keys (from user_settings) instead of env vars

---

## 7. Frontend Changes

### New pages/components

| Component | Purpose |
|-----------|---------|
| `LoginPage.tsx` | Google sign-in button, landing page for unauthenticated users |
| `SettingsPage.tsx` | Form for API keys (masked input fields) + resume bank upload |
| `OnboardingGuard.tsx` | Checks if user has keys + resume bank configured; redirects to Settings if not |
| `AuthProvider.tsx` | React context for auth state (JWT, user info, login/logout methods) |
| `ProtectedRoute.tsx` | Wrapper that redirects to login if not authenticated |

### Auth flow
1. User visits the app → sees `LoginPage` with "Sign in with Google" button
2. Google OAuth popup → returns ID token
3. Frontend sends token to `POST /api/auth/google` → gets JWT back
4. JWT stored in localStorage, sent as `Authorization: Bearer <jwt>` header on all API calls
5. On load, check JWT validity via `GET /api/auth/me`

### Navigation changes
- Add "Settings" tab/link in the header (alongside existing "Discovered" and "Manual" tabs)
- Add user avatar/name + "Sign out" button in header
- First-time users see a banner: "Set up your API keys and resume bank to get started"

### Google OAuth frontend library
- Use `@react-oauth/google` npm package
- Configure with `GOOGLE_CLIENT_ID` (passed via a `/api/config/client` endpoint or embedded at build time)

---

## 8. Backend Auth Implementation

### JWT middleware
- Use `python-jose` (or `PyJWT`) for token creation/verification
- Token contains: `user_id`, `email`, `exp` (24h expiry)
- Middleware extracts token from `Authorization` header, verifies, attaches `user_id` to request state
- Unauthenticated requests to `/api/*` (except `/api/auth/*` and `/api/config/client`) return 401

### Google token verification
- Use `google-auth` library's `id_token.verify_oauth2_token()`
- Verify against your `GOOGLE_CLIENT_ID`
- Extract `email`, `name`, `sub` (Google user ID)
- Find or create user in `users` table

### Per-user API key usage
- When pipeline runs, load user's encrypted keys from `user_settings`
- Decrypt with Fernet
- Pass to discovery/tailoring functions instead of reading from env vars
- Current code reads keys via `os.getenv()` — needs refactoring to accept keys as parameters

---

## 9. Railway Deployment Setup

### Railway configuration

**Dockerfile** (new file):
```dockerfile
FROM python:3.12-slim

WORKDIR /app

# Install Node.js for frontend build
RUN apt-get update && apt-get install -y nodejs npm && rm -rf /var/lib/apt/lists/*

# Install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Build frontend
COPY ui/package*.json ui/
RUN cd ui && npm install
COPY ui/ ui/
RUN cd ui && npm run build

# Copy backend
COPY src/ src/
COPY config/ config/
COPY templates/ templates/
COPY examples/ examples/

# Persistent volume mount point
RUN mkdir -p /data/db

EXPOSE 8000
CMD ["python", "-m", "uvicorn", "src.api:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Railway settings:**
- Persistent volume: mount at `/data` (1GB free)
- SQLite path: `/data/db/pipeline.db`
- Resume files + user data all in SQLite on the volume
- Environment variables: `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `JWT_SECRET`, `ENCRYPTION_KEY`

### Config changes for deployment
- `DB_PATH` env var (default: `db/pipeline.db` for local, `/data/db/pipeline.db` on Railway)
- `DATA_DIR` env var (default: `data/` for local, `/data/` on Railway)
- Keep `config/config.yaml` for scoring/search defaults (not user-specific)
- Per-user config overrides stored in `user_settings` table

---

## 10. Operational Workflow

### For you (the maintainer)
| Action | How |
|--------|-----|
| Deploy | Push to GitHub → Railway auto-deploys |
| View logs | Railway dashboard → Logs tab |
| Check DB | Railway shell → `sqlite3 /data/db/pipeline.db` |
| Update code | Push to main → auto-redeploy |
| Monitor usage | Railway dashboard shows compute/memory/volume usage |
| Roll back | Railway dashboard → Deployments → click "Rollback" |

### For users
| Action | How |
|--------|-----|
| Sign up | Visit URL → "Sign in with Google" |
| First-time setup | Settings page → paste API keys → upload resume bank |
| Discover jobs | Click "SerpAPI + Resume" on dashboard |
| Download resume | Click download icon on any job row |
| Update resume bank | Settings page → re-upload JSON |

---

## 11. File / Module Impact

### New files to create

| File | Purpose |
|------|---------|
| `src/auth.py` | Google OAuth verification, JWT creation/validation, auth middleware |
| `src/encryption.py` | Fernet encrypt/decrypt helpers for API keys |
| `src/auth_models.py` | Pydantic models for auth requests/responses |
| `Dockerfile` | Railway deployment config |
| `.dockerignore` | Exclude unnecessary files from Docker build |
| `ui/src/pages/LoginPage.tsx` | Google sign-in page |
| `ui/src/pages/SettingsPage.tsx` | API keys + resume bank management |
| `ui/src/context/AuthProvider.tsx` | Auth state management |
| `ui/src/components/OnboardingGuard.tsx` | Redirects unconfigured users to Settings |
| `ui/src/components/ProtectedRoute.tsx` | Auth gate wrapper |

### Files to modify

| File | Changes |
|------|---------|
| `src/db.py` | Add `users`, `user_settings`, `resume_files` tables; add `user_id` to `jobs`; update all query functions to filter by user_id |
| `src/api.py` | Add auth middleware to all endpoints; add auth + settings endpoints; refactor pipeline functions to accept user keys as params; change resume download to serve from DB BLOBs |
| `src/api_models.py` | Add auth/settings Pydantic models |
| `src/discovery.py` | Accept `serpapi_key` as parameter instead of reading from env |
| `src/tailoring.py` | Accept `api_key` as parameter instead of reading from env |
| `src/config.py` | Support `DB_PATH` and `DATA_DIR` env vars for Railway |
| `src/doc_generator.py` | Return DOCX bytes (for BLOB storage) in addition to file path |
| `ui/src/App.tsx` | Add auth context, routing, Settings tab |
| `ui/src/api.ts` | Add auth header to all requests; add auth + settings API functions |
| `ui/src/types.ts` | Add User, Settings, AuthState types |
| `ui/package.json` | Add `@react-oauth/google` dependency |
| `requirements.txt` | Add `python-jose`, `cryptography`, `google-auth` |

### Files unchanged
- `src/filtering.py` — no user-specific logic
- `src/scoring.py` — no user-specific logic
- `src/jd_extractor.py` — no user-specific logic
- `src/digest.py` — may need user_id filter but low priority
- `src/resume_bank.py` — validation logic stays the same, just called with user's JSON
- `config/config.yaml` — stays as shared defaults
- `tests/` — existing tests stay, add new auth/settings tests

---

## 12. Implementation Plan (Build Order)

### Phase 1: Auth + User System (backend)
1. Add `users` and `user_settings` tables to `src/db.py`
2. Create `src/auth.py` — Google token verification + JWT
3. Create `src/encryption.py` — Fernet key encrypt/decrypt
4. Add auth middleware to `src/api.py`
5. Add `/api/auth/google` and `/api/auth/me` endpoints
6. Add `/api/settings/*` endpoints (keys + resume bank CRUD)

### Phase 2: Multi-Tenancy (backend)
7. Add `user_id` column to `jobs` table + migration logic
8. Update all `src/db.py` query functions to accept and filter by `user_id`
9. Update all `src/api.py` endpoints to pass `user_id` from auth context
10. Refactor `src/discovery.py` to accept `serpapi_key` as parameter
11. Refactor `src/tailoring.py` to accept API key as parameter
12. Add `resume_files` table; update resume download/preview to serve from DB

### Phase 3: Auth + Settings UI (frontend)
13. Add `@react-oauth/google` to `ui/package.json`
14. Create `AuthProvider.tsx` + `ProtectedRoute.tsx`
15. Create `LoginPage.tsx` with Google sign-in
16. Create `SettingsPage.tsx` (API key form + resume bank upload)
17. Create `OnboardingGuard.tsx`
18. Update `App.tsx` with auth routing and Settings tab
19. Update `api.ts` to include JWT in all requests

### Phase 4: Deployment
20. Update `src/config.py` to support `DB_PATH` / `DATA_DIR` env vars
21. Create `Dockerfile`
22. Create `.dockerignore`
23. Create Railway project, set env vars, attach persistent volume
24. Set up Google Cloud OAuth credentials (consent screen + client ID)
25. Deploy and test end-to-end

### Phase 5: Polish (post-deploy)
26. Add "Setup incomplete" banner for users without keys/resume bank
27. Add loading states and error messages for auth flows
28. Test with a friend (real user)

### Likely blockers / risks
- **Google OAuth setup**: Requires a Google Cloud project, OAuth consent screen (can stay in "Testing" mode for <100 users), and authorized redirect URIs pointing to Railway URL
- **Railway free tier limits**: 500 execution hours/month. If the app runs 24/7, that's ~21 days. Fine if traffic is low, but the app should handle cold starts gracefully
- **SQLite concurrent writes**: With 2-5 users, WAL mode should be fine. If two users run pipelines simultaneously, one may briefly block. Acceptable at this scale
- **Encryption key rotation**: If you ever change `ENCRYPTION_KEY`, all stored API keys become unreadable. Document this risk
- **DOCX generation on Linux**: The Dockerfile uses Python slim image. LibreOffice won't be installed. Page-fit PDF validation will fall back to heuristic mode. This is acceptable for MVP

---

## 13. Verification Plan

1. **Local testing**: Run the full app locally with auth enabled (use Google OAuth test mode)
2. **Auth flow**: Sign in with Google → verify JWT → verify user created in DB
3. **Settings flow**: Add API keys → verify encrypted in DB → verify decrypted when pipeline runs
4. **Resume bank**: Upload JSON → verify stored → verify used in tailoring
5. **Multi-tenant isolation**: Sign in as two different Google accounts → verify each sees only their own jobs/resumes
6. **Railway deploy**: Push to GitHub → verify Railway builds and deploys → verify app accessible at public URL
7. **End-to-end**: Sign in → add keys → add resume bank → run discovery → generate resumes → download DOCX
8. **File persistence**: Deploy an update → verify DB and files survive the redeploy (persistent volume working)

---

## 14. Google OAuth Setup (Step-by-Step for a PM)

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create a new project (e.g., "PM Job Pipeline")
3. Go to **APIs & Services → OAuth consent screen**
   - User type: External
   - App name: "PM Job Pipeline"
   - Add your email as test user
   - Add friends' emails as test users (while in "Testing" mode, only listed users can sign in)
4. Go to **APIs & Services → Credentials → Create Credentials → OAuth 2.0 Client ID**
   - Application type: Web application
   - Authorized JavaScript origins: `https://your-app.up.railway.app`
   - Authorized redirect URIs: `https://your-app.up.railway.app`
5. Copy the **Client ID** and **Client Secret** → set as Railway env vars

---

## 15. Cost Summary

| Service | Free Tier | Expected Usage | Cost |
|---------|-----------|----------------|------|
| Railway (compute) | 500 hrs/month | ~100 hrs (on-demand use) | $0 |
| Railway (volume) | 1GB | ~50MB (DB + DOCX BLOBs) | $0 |
| Google Cloud (OAuth) | Free | Auth only | $0 |
| SerpAPI | 100 searches/month | Per user, their own account | User pays |
| Claude/Gemini API | Per usage | Per user, their own account | User pays |

**Total hosting cost: $0/month** (within free tier limits)

---

## 16. Open Questions

1. **Resume bank onboarding**: Should we provide an in-app resume bank builder (form-based) instead of requiring users to write JSON manually? The JSON schema is complex for non-technical users. Could be a later enhancement.
2. **Config per user**: Should scoring weights, search queries, and location preferences be customizable per user? Currently they're in shared `config.yaml`. For MVP, shared defaults are fine — revisit if users want customization.
3. **Email notifications**: The current system has optional Gmail integration. Should this be exposed per-user in Settings? Not for MVP — the UI dashboard replaces the need for email digests.
