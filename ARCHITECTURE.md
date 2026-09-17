# Resume Tailor - Architecture & Design

## System Overview

```
┌─────────────────┐
│  Browser (UI)   │
│  (Next.js)      │
└────────┬────────┘
         │ HTTP/REST
         ▼
┌─────────────────────────────────────┐
│  FastAPI Backend                    │
│  - File upload handling             │
│  - Form parsing                     │
│  - Response management              │
└────────┬────────────────────────────┘
         │
         ├──► Gemini Vision API (Extract text from images)
         │    └─ Fast vision understanding
         │    └─ < 1 sec per image
         │
         ├──► Gemini LLM API (Tailor resume)
         │    └─ Prompt: JD + Resume template
         │    └─ Output: Tailored LaTeX
         │    └─ ~10 seconds per request
         │
         └──► pdflatex (Compile PDF)
              └─ Convert .tex to .pdf
              └─ ~3-5 seconds per request

         ▼
┌─────────────────────────────────┐
│  Filesystem Storage             │
│  /resumes/Company_Role/         │
│  ├─ resume_TIMESTAMP.tex        │
│  ├─ resume_TIMESTAMP.pdf        │
│  └─ ...                         │
└─────────────────────────────────┘
```

---

## Component Breakdown

### 1. Frontend (Next.js React)

**Files:**
- `pages/index.js` - Main UI with form
- `styles/Home.module.css` - Component styling
- `pages/_app.js` - App wrapper
- `styles/globals.css` - Global CSS

**Responsibilities:**
- Accept company name, role, JD text, and images
- Validate input before sending
- Send multipart/form-data to backend
- Display results and download links
- Show loading states and errors

**Technologies:**
- React 18 (hooks)
- Next.js 14 (SSR, API routes)
- Axios (HTTP client)
- CSS Modules (styling)

**Flow:**
1. User fills form → Validate input
2. Click "Tailor Resume" → multipart/form-data POST to `/tailor`
3. Show loading spinner (120s timeout)
4. Display success → link to download
5. Download PDF directly

---

### 2. Backend (FastAPI Python)

**Files:**
- `main.py` - FastAPI application
- `requirements.txt` - Dependencies
- `.env.example` - Config template
- `templates/default_resume.tex` - Resume template

**Responsibilities:**
- Accept multipart file uploads
- Extract text from images using Gemini Vision
- Call Gemini LLM to tailor resume
- Compile LaTeX to PDF
- Serve downloads
- Manage file organization

**Key Endpoints:**

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/tailor` | POST | Tailor resume |
| `/download/{folder}/{filename}` | GET | Download PDF |
| `/list/{folder}` | GET | List resumes |
| `/health` | GET | Health check |

**Technologies:**
- FastAPI (async web framework)
- Pydantic (validation)
- google-generativeai (Gemini API)
- Pillow (image processing)
- subprocess (pdflatex execution)

**Flow:**
1. Receive multipart form data
2. Extract images → Gemini Vision API → Extract text
3. Combine JD text + extracted text
4. Send to Gemini LLM with prompt + resume template
5. Receive tailored LaTeX
6. Write .tex file to disk
7. Run `pdflatex` → generates PDF
8. Clean up auxiliary files
9. Return response with download URL

---

### 3. Gemini API Integration

#### Vision (Extract Text from Screenshots)

```python
model = genai.GenerativeModel("gemini-2.0-flash")
response = model.generate_content([
    "Extract all text from this JD screenshot.",
    image_object,
])
```

**Cost:** ~100 tokens per image (free tier = 1M tokens/day)
**Speed:** ~2 seconds per image

#### LLM (Tailor Resume)

```python
prompt = f"""
You are a resume tailor. Tailor this LaTeX resume to match the JD.
Rules:
- Preserve all LaTeX structure
- Only modify textual content
- Never add experiences not in original
- Use JD terminology where truthful

JD: {jd_text}
RESUME: {resume_template}
"""

response = model.generate_content(prompt)
```

**Cost:** ~3,500 tokens per request (free tier = 1M tokens/day)
**Speed:** ~15 seconds per request

---

### 4. LaTeX Compilation

**Tool:** pdflatex (TeX Live or MiKTeX)

**Process:**
1. Write tailored `.tex` to temp file
2. Run: `pdflatex -interaction=nonstopmode output.tex`
3. Capture output directory
4. Verify PDF exists
5. Delete auxiliary files (.aux, .log, .out)
6. Return PDF path

**Time:** ~3-5 seconds per document
**Space:** ~500KB-2MB per PDF

---

## Data Flow Example

```
INPUT:
  Company: "GitLab"
  Role: "Senior Backend Engineer"
  JD Text: "Ruby on Rails... microservices..."
  Images: [screenshot1.png, screenshot2.png]

STEP 1: Extract from Images
  Image 1 → Gemini Vision → "Authorization team... policy engine..."
  Image 2 → Gemini Vision → "Work with authentication teams..."

STEP 2: Combine JD
  JD = "Ruby on Rails... microservices..." + 
       "Authorization team... policy engine..." +
       "Work with authentication teams..."

STEP 3: Tailor Resume
  Input: {jd + template}
  Gemini LLM → Output tailored .tex

STEP 4: Compile PDF
  pdflatex resume_20240116_102030.tex
  Output: resume_20240116_102030.pdf

OUTPUT:
  Path: /resumes/GitLab_Senior_Backend_Engineer/
  Files: [resume_20240116_102030.tex, resume_20240116_102030.pdf]
  Download URL: /download/GitLab_Senior_Backend_Engineer/resume_20240116_102030.pdf
```

---

## Error Handling

### Frontend
- **Invalid input:** Show form validation errors
- **Backend down:** Show connection error
- **API error:** Show Gemini API error message
- **Timeout:** 120-second limit for compilation

### Backend
- **Missing JD:** Reject with 400
- **Image processing fail:** Gemini Vision error → 400
- **Gemini API fail:** Gemini error → 500
- **LaTeX compilation fail:** Show stderr → 500
- **File not found:** 404 on download

### Gemini API
- **Rate limit:** 15 req/min (free tier)
- **Token limit:** 1M tokens/day (free tier)
- **Model errors:** Return in response

---

## Performance Optimization

### For 40 Resumes/Day

**Timeline per resume:**
- Form submission: 0.5 sec
- Image extraction (if 2 images): 4 sec
- Gemini tailoring: 15 sec
- LaTeX compilation: 5 sec
- Total: ~25 seconds

**Throughput:**
- Sequential: 40 jobs × 25 sec = 16.7 minutes
- Parallel (5 concurrent): 40 jobs ÷ 5 = 8 jobs × 25 sec = 3.3 minutes
- Practical: Keep browser/API open, submit jobs as they arrive

**Token usage:**
- Per resume: 2-3 images (200 tokens) + tailoring (3,500 tokens) = 3,700 tokens
- 40 resumes: 148,000 tokens
- Free tier: 1M tokens/day → ✅ Plenty of headroom

**Caching:**
- Default resume loaded once at startup
- Images processed in-memory (no disk write)
- PDFs stored to disk only after compilation

---

## Security Considerations

### Data Privacy
- ✅ All processing local (no logging)
- ✅ Resume sent to Gemini only for tailoring (not stored by Google)
- ✅ No resume history kept
- ⚠️ API key stored in `.env` (never commit)

### Input Validation
- ✅ File size limits on images
- ✅ File type validation (images only)
- ✅ Max 3 images per JD
- ✅ Company/Role name sanitization
- ✅ Timeout on LaTeX execution (30s)

### Output Safety
- ✅ Temp files cleaned up
- ✅ No shell injection (using subprocess array)
- ✅ PDF filename controlled by system
- ✅ CORS enabled for frontend

---

## Scaling Considerations

### For 100+ Resumes/Day

1. **Parallel Processing:**
   ```python
   # Use asyncio + concurrent.futures
   with ThreadPoolExecutor(max_workers=3):
       futures = [executor.submit(tailor_resume, jd) for jd in jds]
   ```

2. **Queue System:**
   - Redis queue + Celery for background jobs
   - Frontend submits → Queue → Worker processes → Callback

3. **Gemini Rate Limits:**
   - Free: 15 req/min
   - Pro: Higher limits (paid)
   - Implement exponential backoff

4. **Storage:**
   - Currently: Local filesystem
   - For scale: S3 / GCS / MinIO

5. **LaTeX Compilation:**
   - Compile in Docker containers
   - Sandbox for security

---

## Deployment Options

### Option 1: Local (Current)
- Backend: `uvicorn main:app --reload`
- Frontend: `npm run dev`
- Storage: Local `/resumes/` folder

### Option 2: Docker Compose
- Backend container with pdflatex
- Frontend container
- Shared volume for `/resumes/`
- Simple: `docker-compose up`

### Option 3: Cloud (Advanced)
- **Backend:** Heroku / Railway / AWS Lambda / Google Cloud Run
- **Frontend:** Vercel / Netlify
- **Storage:** S3 / Google Cloud Storage
- **API Key:** Environment variable in cloud console

---

## Testing

### Unit Tests
```python
# Test resume tailoring logic
def test_tailor_preserves_structure():
    result = tailor_resume(jd, template)
    assert "\\begin{document}" in result
    assert "\\end{document}" in result
```

### Integration Tests
```python
# Test full flow
def test_end_to_end():
    response = client.post("/tailor", data={
        "company": "Test Co",
        "role": "Engineer",
        "jd_text": "...",
    })
    assert response.status_code == 200
    assert "output_path" in response.json()
```

### Performance Tests
```bash
# Load test for 40 concurrent requests
ab -n 40 -c 5 http://localhost:8000/health
```

---

## Future Enhancements

1. **Batch API:** Submit 40 JDs → Get results as CSV
2. **Resume Versioning:** Compare & merge multiple versions
3. **ATS Scoring:** Score resume against JD
4. **Interview Prep:** Generate cover letter
5. **Analytics:** Track which resume versions perform best
6. **Mobile App:** iOS/Android companion
7. **Collaboration:** Share resume templates with team
8. **ML Tuning:** Fine-tune Gemini on your resume samples

---

## Monitoring & Logging

### Current
- FastAPI logs to console
- PDF compilation errors logged
- Frontend shows errors to user

### Recommended for Production
- ELK stack (Elasticsearch, Logstash, Kibana)
- Sentry for error tracking
- Prometheus for metrics
- CloudWatch / GCP Logs

---

## License & Attribution

- **Gemini API:** Google (API key required)
- **LaTeX:** The LaTeX Project (open source)
- **Next.js:** Vercel (React framework)
- **FastAPI:** Sebastián Ramírez (async web framework)
- **Project:** MIT License

---

**Last Updated:** 2024-01-16
**Version:** 1.0.0
