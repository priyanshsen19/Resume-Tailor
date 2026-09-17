#  Resume Tailor - AI-Powered Resume Generation Tool

Automatically tailor your resume to any job description using **Google Gemini AI** and **LaTeX**. Process 40+ jobs per day with zero token costs from Claude.

**Why Resume Tailor?**
-  **Fast**: Tailor 40+ resumes/day locally
-  **Cheap**: Gemini Free Tier = 1M tokens/day (15 req/min)
-  **Smart**: Preserves LaTeX formatting perfectly
-  **Screenshot Support**: Extract JD text from 3 images per job
-  **Organized**: Auto-saves to `/resumes/Company_Role/`
-  **Web UI**: Simple dashboard + API backend

---

##  Prerequisites

- **Python 3.10+** (backend)
- **Node.js 18+** (frontend)
- **pdflatex** (LaTeX compiler)
- **Gemini API Key** (free at https://ai.google.dev/aistudio)

### Install System Dependencies

**macOS:**
```bash
brew install mactex node@18
```

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install -y texlive-latex-base texlive-latex-extra texlive-fonts-recommended nodejs npm
```

**Windows:**
- Download **MiKTeX** from https://miktex.org/download
- Download **Node.js 18+** from https://nodejs.org

---

##  Quick Start

### Step 1: Clone or Download Project

```bash
cd resume-tailor-project
```

### Step 2: Backend Setup

```bash
cd backend

# Copy .env.example to .env
cp .env.example .env

# Edit .env and add your Gemini API Key
# GEMINI_API_KEY=your_key_here
nano .env  # or open in your editor

# Create Python virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Start backend server
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

**Backend runs at:** `http://localhost:8000`

### Step 3: Frontend Setup (New Terminal)

```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

**Frontend runs at:** `http://localhost:3000`

### Step 4: Open in Browser

Visit `http://localhost:3000` and start tailoring!

---

## 📖 How to Use

1. **Enter Details:**
   - Company name
   - Job role

2. **Provide Job Description:**
   - Paste JD as text, OR
   - Upload up to 3 screenshots (images)

3. **Click "Tailor Resume"** → AI tailors your template within 30 seconds

4. **Download** → Resume saved to `/resumes/Company_Role/resume_TIMESTAMP.pdf`

---

##  Project Structure

```
resume-tailor-project/
├── backend/
│   ├── main.py                    # FastAPI server
│   ├── templates/
│   │   └── default_resume.tex     # Your resume template
│   ├── requirements.txt
│   ├── .env.example
│   └── .env                       # (create this, add API key)
├── frontend/
│   ├── pages/
│   │   ├── index.js               # Main UI
│   │   └── _app.js
│   ├── styles/
│   │   └── Home.module.css        # Styling
│   ├── package.json
│   ├── next.config.js
│   └── .env.local
├── resumes/                       # (auto-created) Output folder
│   ├── Company_Role/
│   │   ├── resume_TIMESTAMP.tex
│   │   └── resume_TIMESTAMP.pdf
└── README.md
```

---

##  Configuration

### Backend (.env)

```ini
GEMINI_API_KEY=your_gemini_api_key_here
BACKEND_HOST=0.0.0.0
BACKEND_PORT=8000
FRONTEND_URL=http://localhost:3000
```

**Get Gemini API Key:**
1. Go to https://ai.google.dev/aistudio
2. Click "Get API Key"
3. Create new API key
4. Copy and paste into `.env`

**Key pool (more requests per day):**

Free-tier keys are limited to roughly 20 requests/day each. Create several keys
(one per Google account / AI Studio project) and list them all:

```ini
GEMINI_API_KEYS=key_one,key_two,key_three,key_four
GEMINI_DAILY_LIMIT_PER_KEY=20   # soft cap per key; 4 keys x 20 = ~80 resumes/day
```

The backend picks the least-used healthy key for every call, marks a key
exhausted when Google returns a daily-quota 429 (it comes back at midnight
Pacific), backs off 60s on per-minute 429s, and disables invalid keys. Usage
counters persist in `backend/key_usage.json`. Check the pool at any time:

```bash
curl http://localhost:8000/keys
```

### Frontend (.env.local)

```ini
NEXT_PUBLIC_BACKEND_URL=http://localhost:8000
```

---

##  Customizing Your Resume Template

The default resume is stored in `backend/templates/default_resume.tex`.

**To use your own LaTeX resume:**
1. Save your `.tex` file as `backend/templates/default_resume.tex`
2. Make sure it's compilable (test with pdflatex locally)
3. Restart the backend

**Important:** Keep all formatting, packages, and structure intact. The AI only modifies the textual content (bullets, summaries, skills).

---

##  Cost Breakdown

| Service | Cost | Notes |
|---------|------|-------|
| **Gemini Free** | $0 | 15 req/min, 1M tokens/day |
| **Gemini Pro** | $0.075/1M tokens | After free tier |
| **LaTeX** | $0 | Open source |
| **Next.js** | $0 | Self-hosted |
| **Total (40 jobs/day)** | **~$0** | Stays within free tier |

Claude API = ~$0.01 per resume. **Gemini = ~$0.0001 per resume.**

---

##  API Endpoints

### Tailor Resume
```http
POST /tailor
Content-Type: multipart/form-data

company: "GitLab"
role: "Senior Backend Engineer"
jd_text: "..." (optional)
jd_images: [file1.png, file2.png, file3.png] (optional, max 3)

Response:
{
  "status": "success",
  "message": "Resume tailored for GitLab - Senior Backend Engineer",
  "output_path": "resumes/GitLab_Senior_Backend_Engineer",
  "pdf_url": "/download/GitLab_Senior_Backend_Engineer/resume_20240116_102030.pdf"
}
```

### Download Resume
```http
GET /download/{folder}/{filename}

Example: GET /download/GitLab_Senior_Backend_Engineer/resume_20240116_102030.pdf
```

### List Resumes
```http
GET /list/{folder}

Example: GET /list/GitLab_Senior_Backend_Engineer

Response:
{
  "folder": "GitLab_Senior_Backend_Engineer",
  "files": [
    {
      "name": "resume_20240116_102030.pdf",
      "size": 245678,
      "created": "2024-01-16T10:20:30"
    }
  ]
}
```

### Health Check
```http
GET /health

Response: { "status": "ok", "service": "Resume Tailor API" }
```

---

##  Tips for Best Results

1. **Paste Full JD** → More context = better tailoring
2. **Screenshots Quality** → Clear, readable images work best
3. **Max 3 Images** → Helps scale to 40+ jobs/day
4. **Keep Default Resume Updated** → Your best resume = your best tailor
5. **Review Output** → Always check before sending (AI isn't perfect)

---

##  Troubleshooting

### "pdflatex not found"
```bash
# macOS
brew install mactex

# Ubuntu
sudo apt-get install texlive-latex-base texlive-latex-extra
```

### "Gemini API error"
- Check `.env` file has valid `GEMINI_API_KEY`
- Verify API key at https://ai.google.dev/aistudio
- Check rate limit (15 req/min, 1M tokens/day)

### "Backend connection refused"
- Ensure backend is running: `uvicorn main:app --reload`
- Check `NEXT_PUBLIC_BACKEND_URL` in frontend `.env.local`
- CORS should be enabled (already configured)

### "PDF compilation failed"
- Ensure LaTeX template is valid
- Test locally: `pdflatex backend/templates/default_resume.tex`
- Check `/tmp/*.log` for LaTeX errors

### "Image processing failed"
- Ensure images are clear, readable JPG/PNG
- Max file size: Gemini accepts up to 4MB per image
- Text should be legible at screen resolution

---

##  Performance

- **Single Resume:** 15–30 seconds
- **Batch (10 resumes):** 2.5–5 minutes
- **Concurrent Requests:** Limited by Gemini (15 req/min free tier)

**For 40 jobs/day:**
```
40 jobs × 25 sec avg = 16.7 minutes of actual processing
(Can parallelize via multiple browser tabs or API calls)
```

---

##  How It Works

1. **You submit:** Company, Role, JD (text + images)
2. **Backend processes:**
   - Extract text from images using Gemini Vision API
   - Send JD + default resume to Gemini LLM
   - Gemini tailors while preserving LaTeX structure
3. **Compile:** pdflatex renders `.tex` → PDF
4. **Save:** `/resumes/Company_Role/resume_TIMESTAMP.pdf`
5. **Download:** Available immediately in UI

---

##  Privacy & Security

- ✅ All processing runs **locally** on your machine
- ✅ Your resume template never leaves your system (sent to Gemini only for tailoring, not stored)
- ✅ No resume history logged
- ✅ Only your Gemini API key connects to external services

---

##  Deployment

**Frontend → Vercel, backend → any Docker host (Render / Railway / Fly.io).**
The API needs `pdflatex`, which serverless platforms can't provide, so it ships
as a container; a [`render.yaml`](render.yaml) Blueprint is included.

Full step-by-step guide: **[DEPLOY.md](DEPLOY.md)**.

Quick version:

1. Push the repo to GitHub.
2. Supabase → run [`supabase/schema.sql`](supabase/schema.sql), enable anonymous sign-ins.
3. Render → *New → Blueprint* → pick the repo → set `GEMINI_API_KEYS`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`.
4. Vercel → *Import* the repo → Root Directory `frontend` →
   env `NEXT_PUBLIC_BACKEND_URL`, `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`.
5. Set `ALLOWED_ORIGINS=https://<project>.vercel.app` on Render.

Local Docker:

```bash
docker compose up --build
```

---

##  License

MIT — Use freely for personal projects.

---

##  Contributing

Found a bug? Want to add features?
1. Fork the repo
2. Create a branch: `git checkout -b feature/my-feature`
3. Commit: `git commit -m "Add my feature"`
4. Push: `git push origin feature/my-feature`
5. Open a Pull Request

---

##  Feedback

Questions? Issues? Suggestions?
- Open an issue in GitHub
- Check existing issues first

---

##  Credits

- **Gemini API** — Google
- **LaTeX** — The LaTeX Project
- **Next.js** — Vercel
- **FastAPI** — Sebastián Ramírez

---

**Happy tailoring!**

For 40 jobs/day: just keep the backend + frontend running, open the web UI, and start submitting JDs. Your resume folder will fill up automatically.
