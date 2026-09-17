"""
FastAPI backend for AI-powered resume tailoring using Gemini API.
Accepts JDs (text/images), tailors resume template, compiles PDF.
"""

import os
import json
import base64
import subprocess
import tempfile
import shutil
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional, List
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor  

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Header, Depends
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import google.generativeai as genai
from PIL import Image
import io

from latex_utils import prepare_tex, latex_error_from_log
from gemini_pool import pool_from_env, AllKeysExhausted
from resume_store import store_from_env, AuthError, ResumeRecord

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

executor = ThreadPoolExecutor(max_workers=2)

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
# How many times to ask Gemini to fix its own LaTeX if pdflatex rejects it.
MAX_LATEX_REPAIR_ATTEMPTS = int(os.getenv("MAX_LATEX_REPAIR_ATTEMPTS", "2"))


class LatexCompileError(Exception):
    """pdflatex rejected the document; `.detail` holds the first error + context."""

    def __init__(self, detail: str):
        super().__init__(f"LaTeX compilation error: {detail}")
        self.detail = detail


def _tex_env() -> dict:
    """Environment with every known TeX Live / MacTeX bin dir prepended to PATH."""
    env = os.environ.copy()
    candidates = ["/Library/TeX/texbin"]
    candidates += sorted((str(p) for p in Path("/usr/local/texlive").glob("*/bin/*")), reverse=True)
    existing = [c for c in candidates if Path(c).is_dir()]
    env["PATH"] = ":".join(existing + [env.get("PATH", "")])
    return env

TEST_MODE = os.getenv("TEST_MODE", "false").lower() == "true"

# Pool of Gemini keys (GEMINI_API_KEYS=k1,k2,... and/or GEMINI_API_KEY) with
# per-key daily accounting and automatic rotation on quota errors.
key_pool = pool_from_env()

# Per-user persistence (Supabase). Falls back to ./resumes when not configured.
store = store_from_env()
RESUME_FILE_PREFIX = os.getenv("RESUME_FILE_PREFIX", "Resume_Priyansh")

app = FastAPI(title="Resume Tailor API", version="1.0.0")

# CORS. In production set ALLOWED_ORIGINS to the Vercel URL(s), e.g.
#   ALLOWED_ORIGINS=https://resume-tailor.vercel.app,http://localhost:3000
# Vercel preview deployments (*.vercel.app) are allowed via regex by default.
_allowed_origins = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "*").split(",") if o.strip()]
_wildcard = "*" in _allowed_origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_origin_regex=None if _wildcard else os.getenv("ALLOWED_ORIGIN_REGEX", r"https://.*\.vercel\.app"),
    allow_credentials=not _wildcard,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Paths. RESUMES_DIR lets a host mount a persistent disk (default: ./resumes).
TEMPLATE_DIR = Path(__file__).parent / "templates"
OUTPUT_DIR = Path(os.getenv("RESUMES_DIR", "resumes"))
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Read default resume template
DEFAULT_RESUME_PATH = TEMPLATE_DIR / "default_resume.tex"

if not DEFAULT_RESUME_PATH.exists():
    raise FileNotFoundError(f"Default resume template not found at {DEFAULT_RESUME_PATH}")

with open(DEFAULT_RESUME_PATH, "r") as f:
    DEFAULT_RESUME = f.read()


class TailorRequest(BaseModel):
    company: str
    role: str
    jd_text: Optional[str] = None


class ResumeOut(BaseModel):
    id: str
    company: str
    role: str
    folder: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    expires_at: Optional[str] = None
    pdf_url: Optional[str] = None            # inline/preview
    pdf_download_url: Optional[str] = None   # attachment
    tex_url: Optional[str] = None


class StatusResponse(BaseModel):
    status: str
    message: str
    resume: Optional[ResumeOut] = None


def extract_text_from_image(image_data: bytes) -> str:
    """Use Gemini vision to extract text from JD screenshot."""
    try:
        image = Image.open(io.BytesIO(image_data))
        
        # Resize if too large to save tokens
        max_size = 1024
        if image.width > max_size or image.height > max_size:
            image.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
        
        response = key_pool.generate(
            GEMINI_MODEL,
            [
                "Extract all text from this job description screenshot. Return only the clean, readable text.",
                image,
            ],
            generation_config=genai.types.GenerationConfig(max_output_tokens=2000),
        )
        return response.text
    except AllKeysExhausted as e:
        raise HTTPException(status_code=429, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Image processing failed: {str(e)}")


def tailor_resume_with_gemini(jd_text: str, company: str, role: str) -> str:
    """Use Gemini to tailor the resume based on JD, preserving LaTeX structure."""
    
    # TEST MODE - skip Gemini, save tokens
    if TEST_MODE:
        print("[TEST MODE] Skipping Gemini, using default resume")
        return prepare_tex(DEFAULT_RESUME, DEFAULT_RESUME, use_template_preamble=True)
    
    prompt = f"""You are an expert resume tailor and LaTeX editor. Return a complete, clean, valid LaTeX resume file.

CRITICAL REQUIREMENTS:
1. Return COMPLETE LaTeX from \\documentclass to \\end{{document}}
2. Do NOT wrap the output in markdown code blocks (```)
3. Do NOT add ANY explanation, preamble, commentary, or text outside the LaTeX file
4. Return ONLY raw .tex content
5. Preserve the original LaTeX structure, packages, commands, formatting, and custom macros exactly
6. Modify ONLY the resume text content required for tailoring
7. NEVER modify, remove, reorder, or recreate LaTeX commands unless required to keep the file valid
8. No blank lines inside \\item lists, resume sections, or other LaTeX environments
9. Keep each resume bullet as a single logical line; do not insert unnecessary line breaks inside bullets
10. Keep formatting clean and consistent throughout the file
11. Escape LaTeX special characters only when they are part of normal text: & → \\&, % → \\%, _ → \\_
12. NEVER double-escape characters that are already correctly escaped
13. Never break LaTeX commands, environments, or arguments across lines

COMPANY: {company}
ROLE: {role}

JOB DESCRIPTION:
{jd_text}

---

ORIGINAL RESUME (complete LaTeX file - preserve its structure exactly):
{DEFAULT_RESUME}

---

TAILORING RULES:
1. Parse the ENTIRE JD before tailoring, regardless of formatting.
2. Identify the most relevant skills, responsibilities, technologies, qualifications, and ATS keywords internally.
3. Match JD terminology where it is truthfully supported by the original resume.
4. Never add fake experience, skills, technologies, responsibilities, achievements, metrics, or qualifications.
5. Rewrite existing content to emphasize the strongest relevant experience and measurable impact.
6. Keep content concise and ATS-friendly without keyword stuffing.
7. Keep each bullet concise, ideally within 2-3 rendered lines.
8. Preserve all existing factual information including company names, job titles, dates, education, and metrics.
9. Do not add new sections, remove sections, change formatting, or add packages.
10. Keep every existing \\item command intact.
11. Do not introduce Markdown, HTML, Unicode formatting, or unsupported LaTeX syntax.

FINAL CLEANUP AND VALIDATION:
Before returning the resume, internally verify:
- Output starts with \\documentclass and ends with \\end{{document}}
- All {{}} braces are balanced
- All \\begin{{...}} / \\end{{...}} environments are balanced
- All \\item commands remain valid
- No blank lines exist inside lists or resume environments
- No LaTeX commands were accidentally modified
- No characters were unnecessarily double-escaped
- No Markdown or explanatory text is present
- The result is clean, compact, consistent, and valid LaTeX

Return ONLY the COMPLETE cleaned and tailored LaTeX resume:"""

    try:
        raw = _gemini_text(prompt, max_output_tokens=16000)
        print(f"[DEBUG] Gemini response length: {len(raw)} characters")

        # Strip fences/chatter, normalise Unicode, keep ONLY the body from
        # Gemini (preamble always comes from the template), escape specials.
        tailored_tex = prepare_tex(raw, DEFAULT_RESUME, use_template_preamble=True)

        print("[SUCCESS] Gemini returned usable LaTeX resume body")
        return tailored_tex

    except HTTPException:
        raise
    except AllKeysExhausted as e:
        raise HTTPException(status_code=429, detail=str(e))
    except Exception as e:
        error_msg = str(e)
        print(f"[ERROR] Gemini tailor error: {error_msg}")
        raise HTTPException(status_code=500, detail=f"Resume tailoring failed: {error_msg}")


def _gemini_text(prompt: str, max_output_tokens: int) -> str:
    """Call Gemini and return the concatenated text of all parts."""
    response = key_pool.generate(
        GEMINI_MODEL,
        prompt,
        generation_config=genai.types.GenerationConfig(max_output_tokens=max_output_tokens),
    )
    if hasattr(response, "parts") and response.parts:
        text = "".join(part.text for part in response.parts if hasattr(part, "text"))
    elif hasattr(response, "text"):
        text = response.text
    else:
        raise Exception("Gemini returned invalid response format")
    text = (text or "").strip()
    if not text:
        raise Exception("Gemini returned an empty response")
    return text


def repair_latex_with_gemini(tex_content: str, error_detail: str) -> str:
    """Ask Gemini to fix a document that pdflatex rejected. Returns cleaned LaTeX."""
    prompt = f"""You are a LaTeX expert. The resume below FAILED to compile with pdflatex.

ERROR (from the pdflatex log, `l.NN` is the failing line number):
{error_detail}

Fix ONLY what is necessary for the file to compile. Do not rewrite or reword content.
Typical causes: unbalanced {{}} braces, a broken \\begin/\\end pair, a stray $ or &,
a macro called with the wrong number of arguments, a blank line inside a list.

Return the COMPLETE corrected LaTeX file from \\documentclass to \\end{{document}}.
No markdown fences. No commentary. Only raw .tex content.

{tex_content}"""
    raw = _gemini_text(prompt, max_output_tokens=16000)
    return prepare_tex(raw, DEFAULT_RESUME, use_template_preamble=True)



def _compile_tex_sync(tex_content: str, output_tex_path: Path) -> Path:
    """Write `tex_content` (already prepared) and compile it with pdflatex."""

    output_tex_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_tex_path, "w", encoding="utf-8", errors="replace") as f:
        f.write(tex_content)
    print(f"[COMPILE] LaTeX file written: {output_tex_path}")

    # Stale PDF from a previous run must not be mistaken for this run's output.
    pdf_path = output_tex_path.with_suffix(".pdf")
    if pdf_path.exists():
        pdf_path.unlink()

    try:
        print(f"[COMPILE] Starting pdflatex compilation for {output_tex_path.name}")
        result = subprocess.run(
            [
                "pdflatex",
                "-interaction=nonstopmode",
                "-halt-on-error",
                "-output-directory=" + str(output_tex_path.parent),
                str(output_tex_path),
            ],
            capture_output=True,
            timeout=90,
            text=True,
            env=_tex_env(),
        )
    except subprocess.TimeoutExpired:
        raise LatexCompileError("PDF compilation timed out (>90s)")
    except FileNotFoundError:
        raise LatexCompileError("pdflatex not found. Install MacTeX or `brew install --cask basictex`")

    if result.returncode != 0 or not pdf_path.exists():
        log_file = output_tex_path.with_suffix(".log")
        detail = "pdflatex compilation failed"
        if log_file.exists():
            try:
                with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
                    detail = latex_error_from_log(f.read())
            except Exception as log_err:
                print(f"[DEBUG] Could not read log file: {log_err}")
        print(f"[ERROR] LaTeX compilation failed:\n{detail}")
        raise LatexCompileError(detail)

    print(f"[SUCCESS] PDF compiled successfully: {pdf_path}")
    return pdf_path


def _cleanup_aux_files(output_tex_path: Path) -> None:
    for ext in [".aux", ".log", ".out"]:
        aux_file = output_tex_path.with_suffix(ext)
        if aux_file.exists():
            try:
                aux_file.unlink()
            except Exception as e:
                print(f"[DEBUG] Could not delete {aux_file}: {e}")


async def compile_tex_to_pdf(tex_content: str, output_tex_path: Path) -> Path:
    """Compile once; raises LatexCompileError (not HTTPException) on failure."""
    loop = asyncio.get_event_loop()
    pdf_path = await loop.run_in_executor(executor, _compile_tex_sync, tex_content, output_tex_path)
    _cleanup_aux_files(output_tex_path)
    return pdf_path


async def compile_with_repair(tex_content: str, output_tex_path: Path) -> Path:
    """Compile; on failure ask Gemini to repair the LaTeX and retry.

    The .tex on disk always reflects the last attempt, so a failed run can be
    inspected or fixed by hand and recompiled.
    """
    loop = asyncio.get_event_loop()
    last_error: Optional[LatexCompileError] = None

    for attempt in range(MAX_LATEX_REPAIR_ATTEMPTS + 1):
        try:
            return await compile_tex_to_pdf(tex_content, output_tex_path)
        except LatexCompileError as e:
            last_error = e
            if TEST_MODE or attempt == MAX_LATEX_REPAIR_ATTEMPTS:
                break
            print(f"[REPAIR] Attempt {attempt + 1}/{MAX_LATEX_REPAIR_ATTEMPTS}: asking Gemini to fix LaTeX")
            try:
                tex_content = await loop.run_in_executor(
                    executor, repair_latex_with_gemini, tex_content, e.detail
                )
            except Exception as repair_err:
                print(f"[REPAIR] Gemini repair failed: {repair_err}")
                break

    _cleanup_aux_files(output_tex_path)
    raise HTTPException(status_code=500, detail=str(last_error))


# ---------------------------------------------------------------------------
# Auth + persistence helpers
# ---------------------------------------------------------------------------

async def run_sync(fn, *args):
    return await asyncio.get_event_loop().run_in_executor(executor, fn, *args)


async def current_user(authorization: Optional[str] = Header(None)) -> Optional[str]:
    """Supabase user id from the Bearer token; None in local (no-Supabase) mode."""
    if not store.enabled:
        return None
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Sign-in required")
    token = authorization.split(" ", 1)[1].strip()
    try:
        return await run_sync(store.verify_user, token)
    except AuthError as e:
        raise HTTPException(status_code=401, detail=str(e))


def _safe_name(value: str) -> str:
    return "".join(c if c.isalnum() or c == " " else "" for c in value).strip().replace(" ", "_")


def _local_resume_out(folder: Path) -> Optional[ResumeOut]:
    tex_files = list(folder.glob("*.tex"))
    if not tex_files:
        return None
    tex = max(tex_files, key=lambda f: f.stat().st_mtime)
    pdfs = list(folder.glob("*.pdf"))
    pdf = max(pdfs, key=lambda f: f.stat().st_mtime) if pdfs else None
    parts = folder.name.split("_", 1)
    return ResumeOut(
        id=folder.name,
        company=parts[0].replace("_", " "),
        role=(parts[1] if len(parts) > 1 else "").replace("_", " "),
        folder=folder.name,
        updated_at=datetime.fromtimestamp(tex.stat().st_mtime).isoformat(),
        created_at=datetime.fromtimestamp(tex.stat().st_ctime).isoformat(),
        pdf_url=f"/download/{folder.name}/{pdf.name}?inline=true" if pdf else None,
        pdf_download_url=f"/download/{folder.name}/{pdf.name}" if pdf else None,
        tex_url=f"/download/{folder.name}/{tex.name}",
    )


def _record_out(rec: ResumeRecord) -> ResumeOut:
    return ResumeOut(
        id=rec.id, company=rec.company, role=rec.role, folder=rec.folder,
        created_at=rec.created_at, updated_at=rec.updated_at, expires_at=rec.expires_at,
        **store.urls_for(rec),
    )


async def _persist(user_id: Optional[str], company: str, role: str, folder: Path,
                   tex_path: Path, pdf_path: Path, resume_id: Optional[str] = None) -> ResumeOut:
    """Supabase mode: upload + row, then drop the local scratch copy. Local mode: describe the folder."""
    if not store.enabled:
        return _local_resume_out(folder)
    rec = await run_sync(store.save, user_id, company, role, folder.name, tex_path, pdf_path, resume_id)
    shutil.rmtree(folder, ignore_errors=True)
    return _record_out(rec)


async def _purge_loop():
    """Hourly: delete resumes past their expiry (rows + storage objects)."""
    while True:
        try:
            await run_sync(store.purge_expired)
        except Exception as e:
            print(f"[STORE] purge failed: {e}")
        await asyncio.sleep(3600)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    task = asyncio.create_task(_purge_loop()) if store.enabled else None
    yield
    if task:
        task.cancel()


app.router.lifespan_context = lifespan


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.post("/tailor", response_model=StatusResponse)
async def tailor_resume(
    company: str = Form(...),
    role: str = Form(...),
    jd_text: Optional[str] = Form(None),
    jd_images: Optional[List[UploadFile]] = File(None),
    user_id: Optional[str] = Depends(current_user),
):
    """Tailor the template to a JD (text and/or screenshots), compile, persist."""
    if not jd_text and not jd_images:
        raise HTTPException(status_code=400, detail="Provide JD as text or images")

    extracted_texts = []
    if jd_images:
        if len(jd_images) > 3:
            raise HTTPException(status_code=400, detail="Maximum 3 images per JD")
        for img in jd_images:
            img_data = await img.read()
            extracted_texts.append(await run_sync(extract_text_from_image, img_data))

    final_jd = jd_text or ""
    if extracted_texts:
        final_jd = "\n\n---\n\n".join(([final_jd] if final_jd else []) + extracted_texts)
    if not final_jd.strip():
        raise HTTPException(status_code=400, detail="No JD content found")

    print(f"[TAILOR] Starting Gemini API call for {company} - {role}")
    tailored_tex = await run_sync(tailor_resume_with_gemini, final_jd, company, role)
    print("[TAILOR] Gemini API call completed")

    safe_company, safe_role = _safe_name(company), _safe_name(role)
    output_folder = OUTPUT_DIR / f"{safe_company}_{safe_role}"
    output_folder.mkdir(parents=True, exist_ok=True)
    output_tex_path = output_folder / f"{RESUME_FILE_PREFIX}_{safe_company}.tex"

    pdf_path = await compile_with_repair(tailored_tex, output_tex_path)
    resume = await _persist(user_id, company, role, output_folder, output_tex_path, pdf_path)

    return StatusResponse(status="success", message=f"Resume tailored for {company} - {role}", resume=resume)


@app.post("/recompile", response_model=StatusResponse)
async def recompile_resume(
    resume_id: Optional[str] = Form(None),
    tex_file: Optional[UploadFile] = File(None),
    company: Optional[str] = Form(None),
    role: Optional[str] = Form(None),
    user_id: Optional[str] = Depends(current_user),
):
    """
    Recompile an existing resume (optionally with an edited .tex), or compile a
    brand-new uploaded .tex when `resume_id` is omitted (company + role required).
    """
    uploaded_tex = (await tex_file.read()).decode("utf-8", errors="replace") if tex_file else None

    if resume_id:
        if store.enabled:
            rec = await run_sync(store.get, user_id, resume_id)
            if not rec:
                raise HTTPException(status_code=404, detail="Resume not found (it may have expired)")
            company, role, folder_name = rec.company, rec.role, rec.folder
            tex_content = uploaded_tex or await run_sync(store.download_tex, rec)
            tex_name = Path(rec.tex_path).name
        else:
            folder = (OUTPUT_DIR / resume_id).resolve()
            if OUTPUT_DIR.resolve() not in folder.parents or not folder.is_dir():
                raise HTTPException(status_code=404, detail=f"Folder not found: {resume_id}")
            tex_files = sorted(folder.glob("*.tex"), key=lambda f: f.stat().st_mtime, reverse=True)
            if not tex_files and not uploaded_tex:
                raise HTTPException(status_code=404, detail="No .tex file in that folder")
            existing = _local_resume_out(folder)
            company, role, folder_name = existing.company, existing.role, folder.name
            tex_name = tex_files[0].name if tex_files else (tex_file.filename or f"{RESUME_FILE_PREFIX}.tex")
            tex_content = uploaded_tex or tex_files[0].read_text(encoding="utf-8", errors="replace")
    else:
        if not uploaded_tex or not company or not role:
            raise HTTPException(status_code=400, detail="Upload a .tex file and give company + role, or pick an existing resume")
        folder_name = f"{_safe_name(company)}_{_safe_name(role)}"
        tex_name = f"{RESUME_FILE_PREFIX}_{_safe_name(company)}.tex"
        tex_content = uploaded_tex

    # Keep the file's own (possibly hand-edited) preamble; sanitise the body.
    tex_content = prepare_tex(tex_content, DEFAULT_RESUME, use_template_preamble=False)

    output_folder = OUTPUT_DIR / folder_name
    output_folder.mkdir(parents=True, exist_ok=True)
    output_tex_path = output_folder / tex_name

    pdf_path = await compile_with_repair(tex_content, output_tex_path)
    resume = await _persist(user_id, company, role, output_folder, output_tex_path, pdf_path, resume_id)

    return StatusResponse(status="success", message="Resume recompiled successfully", resume=resume)


@app.get("/resumes")
async def list_resumes(user_id: Optional[str] = Depends(current_user)):
    """The caller's recent resumes (newest first), with fresh signed URLs."""
    if store.enabled:
        recs = await run_sync(store.list, user_id)
        return {"resumes": [_record_out(r).model_dump() for r in recs]}

    items = []
    if OUTPUT_DIR.exists():
        for folder in OUTPUT_DIR.iterdir():
            if folder.is_dir():
                out = _local_resume_out(folder)
                if out:
                    items.append(out.model_dump())
    items.sort(key=lambda r: r["updated_at"] or "", reverse=True)
    return {"resumes": items}


@app.delete("/resumes/{resume_id}")
async def delete_resume(resume_id: str, user_id: Optional[str] = Depends(current_user)):
    if store.enabled:
        ok = await run_sync(store.delete, user_id, resume_id)
    else:
        folder = (OUTPUT_DIR / resume_id).resolve()
        ok = OUTPUT_DIR.resolve() in folder.parents and folder.is_dir()
        if ok:
            shutil.rmtree(folder, ignore_errors=True)
    if not ok:
        raise HTTPException(status_code=404, detail="Resume not found")
    return {"status": "deleted", "id": resume_id}


@app.get("/download/{folder}/{filename}")
async def download_resume(folder: str, filename: str, inline: bool = False):
    """Local-mode file serving (Supabase mode uses signed URLs instead)."""
    file_path = (OUTPUT_DIR / folder / filename).resolve()
    if OUTPUT_DIR.resolve() not in file_path.parents or not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    media_type = "application/pdf" if file_path.suffix == ".pdf" else "text/plain; charset=utf-8"
    return FileResponse(
        file_path,
        media_type=media_type,
        filename=filename,
        content_disposition_type="inline" if inline else "attachment",
    )


@app.get("/keys")
async def key_pool_status():
    """Per-key usage for today and how many requests remain across the pool."""
    return key_pool.status()


@app.get("/")
async def root():
    return {"service": "Resume Tailor API", "docs": "/docs", "health": "/health"}


@app.get("/health")
async def health():
    return {"status": "ok", "service": "Resume Tailor API", "storage": "supabase" if store.enabled else "local"}


if __name__ == "__main__":
    import uvicorn
    # Hosts like Render/Railway inject PORT; fall back to BACKEND_PORT / 8000.
    port = int(os.getenv("PORT") or os.getenv("BACKEND_PORT") or 8000)
    uvicorn.run(app, host=os.getenv("BACKEND_HOST", "0.0.0.0"), port=port)
