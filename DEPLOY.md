# Deploying Resume Tailor

## Architecture

```
 Browser ──► Vercel (Next.js frontend)  ──► Docker host (FastAPI + pdflatex + Gemini)
             frontend/                        backend/   e.g. Render / Railway / Fly.io
```

**Why not everything on Vercel?** The backend shells out to `pdflatex`. Vercel's
serverless functions can't install TeX Live (≈1–2 GB) and are capped at 250 MB,
so the API runs as a container on any Docker host. The frontend is a static
Next.js app and deploys to Vercel in one click.

---

## 0. Push the repo to GitHub

Both Vercel and Render deploy from a Git repo. From the project root:

```bash
git init -b main && git add -A && git commit -m "Resume Tailor"
```

Then create an empty repo on GitHub and:

```bash
git remote add origin git@github.com:<you>/resume-tailor.git && git push -u origin main
```

`.gitignore` already excludes `.env`, `venv/`, `resumes/`, `key_usage.json`.

---

## 1. Supabase (per-user resume history)

Each visitor gets an anonymous Supabase user; their resumes (`.tex` + `.pdf`)
are stored in a private bucket and listed under *Recent resumes* on any device
that shares that browser session. Everything is deleted **24 h** after creation.

1. Create a project at https://supabase.com (free tier is plenty).
2. **SQL Editor → New query** → paste and run [`supabase/schema.sql`](supabase/schema.sql).
3. **Authentication → Sign In / Providers → Allow anonymous sign-ins → ON**.
4. From **Project Settings → API** copy:
   - Project URL → `SUPABASE_URL` (backend) and `NEXT_PUBLIC_SUPABASE_URL` (frontend)
   - `anon public` key → `NEXT_PUBLIC_SUPABASE_ANON_KEY` (frontend only)
   - `service_role` key → `SUPABASE_SERVICE_ROLE_KEY` (**backend only**, never expose it)

If you skip this step the app still works in single-user mode, storing files on
the backend's (ephemeral) disk.

> Later, to let people keep history across devices, add an email/Google
> provider and call `supabase.auth.linkIdentity()` — the data model doesn't change.

---

## 2. Backend → Render (free)

The repo contains a [`render.yaml`](render.yaml) Blueprint.

1. Render dashboard → **New → Blueprint** → pick the repo → **Apply**.
2. When prompted for env vars:
   | Variable | Value |
   |---|---|
   | `GEMINI_API_KEYS` | `key1,key2,key3,key4` — your pool of Gemini keys |
   | `SUPABASE_URL` | from step 1 |
   | `SUPABASE_SERVICE_ROLE_KEY` | from step 1 |
   | `ALLOWED_ORIGINS` | leave blank for now; fill in after step 3 |
3. First build takes **10–15 min** (TeX Live install). The Dockerfile runs
   `selftest_latex.py`, which compiles your template inside the image — if a
   TeX package were missing the build would fail rather than your first request.
4. Note the service URL, e.g. `https://resume-tailor-api.onrender.com`.
   Check `https://…/health` → `{"status":"ok"}` and `https://…/keys` for the pool.

**Free-plan caveats**

- The instance sleeps after 15 min idle; the first request then takes ~1 min.
  The UI shows a *Waking up the server…* pill and keeps retrying, so this is handled.
- The disk is ephemeral, which is why resume history lives in Supabase. Only
  the key-pool usage counters are on disk (`/app/data`); losing them on a
  restart just means the pool re-learns today's usage from Google's 429s.

### Alternatives (same Dockerfile)

- **Railway**: New Project → Deploy from GitHub → set *Root Directory* `backend`.
  Railway detects the Dockerfile and injects `PORT` automatically. Add a
  Volume at `/app/resumes` if you want persistence.
- **Fly.io**: `cd backend && fly launch` (accept the Dockerfile), then
  `fly secrets set GEMINI_API_KEYS=… ALLOWED_ORIGINS=…`.
- **Any VPS**: `docker compose up -d --build backend`.

---

## 3. Frontend → Vercel

1. Vercel → **Add New → Project** → import the GitHub repo.
2. **Root Directory**: `frontend` (click *Edit* next to it). Framework is
   auto-detected as Next.js.
3. **Environment Variables**:
   | Name | Value |
   |---|---|
   | `NEXT_PUBLIC_BACKEND_URL` | `https://resume-tailor-api.onrender.com` (no trailing slash) |
   | `NEXT_PUBLIC_SUPABASE_URL` | from step 1 |
   | `NEXT_PUBLIC_SUPABASE_ANON_KEY` | from step 1 (the *anon* key, not service_role) |
4. **Deploy**. Vercel gives you `https://<project>.vercel.app`.

Or with the CLI:

```bash
cd frontend && npx vercel --prod
```

(`vercel` will ask for the env var on first run, or add it with
`npx vercel env add NEXT_PUBLIC_BACKEND_URL production`.)

> `NEXT_PUBLIC_*` variables are baked in at build time — after changing one,
> trigger a redeploy.

---

## 4. Lock down CORS

Back on Render, set `ALLOWED_ORIGINS` to your Vercel URL(s):

```
ALLOWED_ORIGINS=https://<project>.vercel.app,http://localhost:3000
```

Preview deployments (`https://*.vercel.app`) are allowed automatically via
`ALLOWED_ORIGIN_REGEX`. Leaving `ALLOWED_ORIGINS` unset allows every origin,
which is fine for a personal tool but not recommended.

---

## 5. Verify

- Open the Vercel URL → the top-right pill shows *N left today* (the key pool).
  A *Waking up the server…* pill appears only while a sleeping backend boots.
- Tailor a resume; the result panel previews the PDF inline and it appears
  under *Recent resumes* (with its 24 h countdown).
- `GET <backend>/health` reports `"storage": "supabase"` when history is on.

---

## Environment reference (backend)

| Variable | Default | Purpose |
|---|---|---|
| `GEMINI_API_KEYS` | — | Comma-separated pool of keys (or single `GEMINI_API_KEY`) |
| `GEMINI_DAILY_LIMIT_PER_KEY` | `20` | Soft per-key daily cap |
| `GEMINI_MODEL` | `gemini-3.6-flash` | Model for tailoring, OCR and repair |
| `MAX_LATEX_REPAIR_ATTEMPTS` | `2` | Gemini repair rounds if pdflatex fails |
| `ALLOWED_ORIGINS` | `*` | CORS allow-list (comma-separated) |
| `ALLOWED_ORIGIN_REGEX` | `https://.*\.vercel\.app` | Extra CORS regex (only when `ALLOWED_ORIGINS` is set) |
| `SUPABASE_URL` | — | Enables per-user history when set with the key below |
| `SUPABASE_SERVICE_ROLE_KEY` | — | Server-side Supabase key |
| `SUPABASE_BUCKET` | `resumes` | Private storage bucket name |
| `RESUME_TTL_HOURS` | `24` | Resumes older than this are purged hourly |
| `RESUMES_DIR` | `resumes` | Local scratch / single-user storage |
| `GEMINI_USAGE_FILE` | `key_usage.json` | Persisted per-key daily counters |
| `PORT` | `8000` | Injected by the host |
| `TEST_MODE` | `false` | Skip Gemini, compile the template as-is |
