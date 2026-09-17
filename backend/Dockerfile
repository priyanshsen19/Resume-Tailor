# Resume Tailor API - FastAPI + Gemini + pdflatex
# Deploy anywhere that runs a container: Render, Railway, Fly.io, a VPS.
FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8000 \
    RESUMES_DIR=/app/resumes \
    GEMINI_USAGE_FILE=/app/data/key_usage.json

# TeX Live. fonts-extra is large but provides fontawesome5 + cfr-lm, which the
# template requires; pictures provides tikz for tcolorbox's `most` libraries.
RUN apt-get update && apt-get install -y --no-install-recommends \
        texlive-latex-base \
        texlive-latex-recommended \
        texlive-latex-extra \
        texlive-fonts-recommended \
        texlive-fonts-extra \
        texlive-pictures \
        curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# Fail the build if the template cannot be compiled in this image.
RUN python selftest_latex.py

RUN mkdir -p /app/resumes /app/data

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS "http://localhost:${PORT}/health" || exit 1

# Shell form so $PORT (injected by Render/Railway/Fly) is honoured.
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
