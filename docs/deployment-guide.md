# Deployment Guide — Railway

## Prerequisites

- GitHub repo with all the latest code pushed
- A Google account (for OAuth setup)

---

## Step 1: Google Cloud OAuth Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create a new project (e.g., "PM Job Pipeline")
3. Go to **APIs & Services > OAuth consent screen**
   - User type: **External**
   - App name: "PM Job Pipeline"
   - Add your email as a test user
   - Add your friends' emails as test users (while in "Testing" mode, only listed emails can sign in)
4. Go to **APIs & Services > Credentials > Create Credentials > OAuth 2.0 Client ID**
   - Application type: **Web application**
   - Authorized JavaScript origins: `https://YOUR-APP.up.railway.app` (update after Railway gives you a URL)
   - Authorized redirect URIs: `https://YOUR-APP.up.railway.app`
5. Copy the **Client ID** and **Client Secret**

---

## Step 2: Generate Secrets

Run these locally to generate the required secrets:

```bash
# Generate JWT secret (random 64-char string)
python -c "import secrets; print(secrets.token_hex(32))"

# Generate Fernet encryption key (for encrypting user API keys at rest)
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Save both values — you'll need them in Step 3.

---

## Step 3: Railway Setup

1. Go to [railway.app](https://railway.app) and sign in with GitHub
2. Click **New Project > Deploy from GitHub Repo** and select your repo
3. Railway will detect the Dockerfile automatically

### Add a persistent volume

4. In your service, go to **Settings > Volumes**
5. Click **Add Volume**
   - Mount path: `/data`
   - Size: 1 GB (free tier)

### Set environment variables

6. Go to **Variables** and add:

| Variable | Value |
|----------|-------|
| `GOOGLE_CLIENT_ID` | From Step 1 |
| `GOOGLE_CLIENT_SECRET` | From Step 1 |
| `JWT_SECRET` | From Step 2 |
| `ENCRYPTION_KEY` | From Step 2 |
| `CLOUD_MODE` | `1` |
| `DB_PATH` | `/data/db/pipeline.db` |
| `DATA_DIR` | `/data` |
| `PORT` | `8000` |

7. Click **Deploy** (or it may auto-deploy)

### Update Google OAuth origins

8. Once Railway gives you a public URL (e.g., `https://pm-pipeline.up.railway.app`), go back to Google Cloud Console and update:
   - Authorized JavaScript origins: `https://YOUR-APP.up.railway.app`
   - Authorized redirect URIs: `https://YOUR-APP.up.railway.app`

---

## Step 4: Test

1. Visit your Railway URL
2. You should see the Google sign-in page
3. Sign in with one of the test emails you added in Step 1
4. Go to **Settings** tab and enter your API keys (SerpAPI, Gemini/Claude)
5. Upload your `resume_bank.json`
6. Try submitting a manual job or running discovery

---

## For Your Friends

Send them the Railway URL and tell them to:

1. Sign in with Google (their email must be in your Google OAuth test users list)
2. Go to Settings and enter their own API keys
3. Upload their own resume_bank.json
4. Start using the pipeline

---

## Troubleshooting

**"Not authenticated" errors**: JWT may have expired (72h). Sign out and back in.

**"ENCRYPTION_KEY not set"**: Make sure the env var is set in Railway Variables.

**"Resume bank not configured"**: User needs to upload their resume_bank.json in Settings.

**Google sign-in not working**: Check that the Railway URL matches the authorized origins in Google Cloud Console exactly (including `https://`).

**App works locally but not on Railway**: Make sure `CLOUD_MODE=1` is set. Without it, the app tries to read local files that don't exist in the container.

---

## Cost

| Service | Free Tier | Your Usage | Cost |
|---------|-----------|------------|------|
| Railway compute | 500 hrs/month | ~100 hrs | $0 |
| Railway volume | 1 GB | ~50 MB | $0 |
| Google Cloud OAuth | Free | Auth only | $0 |
| SerpAPI / Claude / Gemini | Per user's account | User pays | $0 for you |
