# 🚀 Resume Tailor - Quick Start (5 Minutes)

## TL;DR

```bash
# 1. Clone the repo
git clone <repo-url> && cd resume-tailor-project

# 2. Run setup script
bash setup.sh

# 3. Add Gemini API key
nano backend/.env
# GEMINI_API_KEY=your_key_from_https://ai.google.dev/aistudio

# 4. Start backend (Terminal 1)
make backend

# 5. Start frontend (Terminal 2)
make frontend

# 6. Open browser
open http://localhost:3000
```

Done! Start tailoring resumes.

---

## Step-by-Step (Windows/Mac/Linux)

### Prerequisites Check

Before starting, verify you have everything installed:

```bash
# Python 3.10+
python3 --version

# Node.js 18+
node --version

# pdflatex
pdflatex --version
```

**Missing something?** See "System Setup" below.

---

### Option A: Automated Setup (Mac/Linux)

```bash
# 1. Navigate to project
cd resume-tailor-project

# 2. Run setup script
chmod +x setup.sh
bash setup.sh

# Follow prompts to add API key
```

Then jump to "Running the Application".

---

### Option B: Manual Setup (All Platforms)

#### Backend

```bash
# Navigate to backend
cd resume-tailor-project/backend

# Create Python virtual environment
python3 -m venv venv

# Activate virtual environment
# Mac/Linux:
source venv/bin/activate

# Windows (PowerShell):
venv\Scripts\Activate.ps1

# Windows (CMD):
venv\Scripts\activate.bat

# Install Python dependencies
pip install -r requirements.txt

# Create .env file
cp .env.example .env

# Edit .env (use any text editor)
# Add: GEMINI_API_KEY=your_key_here
```

#### Frontend

```bash
# Navigate to frontend (new terminal/tab)
cd resume-tailor-project/frontend

# Install Node dependencies
npm install

# Create .env.local (optional, already defaults to localhost:8000)
cp .env.example .env.local
```

---

### Running the Application

#### Terminal 1: Backend

```bash
cd resume-tailor-project/backend

# Activate virtual environment (if not already active)
source venv/bin/activate  # Mac/Linux
# or
venv\Scripts\activate.bat  # Windows

# Start server
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

**Expected output:**
```
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Application startup complete
```

#### Terminal 2: Frontend

```bash
cd resume-tailor-project/frontend

# Start development server
npm run dev
```

**Expected output:**
```
> ready - started server on 0.0.0.0:3000, url: http://localhost:3000
```

#### Open Browser

Go to **http://localhost:3000** 🎉

---

### Your First Tailor

1. **Fill Form:**
   - Company: `GitLab`
   - Role: `Senior Backend Engineer`

2. **Paste JD:**
   - Copy-paste a job description from any posting
   - (Or upload a screenshot)

3. **Click "Tailor Resume"**
   - Wait 25-30 seconds
   - See your tailored resume!

4. **Download PDF**
   - Green "Download PDF" link appears
   - File saved to: `resumes/GitLab_Senior_Backend_Engineer/`

---

## System Setup

### macOS

```bash
# Install Homebrew (if not already installed)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install dependencies
brew install python@3.11 node mactex

# Verify
python3 --version
node --version
pdflatex --version
```

### Ubuntu / Debian

```bash
# Update package manager
sudo apt-get update

# Install dependencies
sudo apt-get install -y python3.11 python3.11-venv nodejs npm texlive-latex-base texlive-latex-extra texlive-fonts-recommended

# Verify
python3 --version
node --version
pdflatex --version
```

### Windows

1. **Python:**
   - Download from https://www.python.org/downloads/
   - Install with "Add Python to PATH" checked

2. **Node.js:**
   - Download from https://nodejs.org/
   - LTS version recommended

3. **LaTeX (MiKTeX):**
   - Download from https://miktex.org/download
   - Run installer (adds `pdflatex` to PATH)

4. **Verify in PowerShell:**
   ```powershell
   python --version
   node --version
   pdflatex --version
   ```

---

## Get Gemini API Key

1. Visit https://ai.google.dev/aistudio
2. Click **"Get API Key"** (top left)
3. Click **"Create API Key"**
4. Copy the key
5. Paste into `backend/.env`:
   ```
   GEMINI_API_KEY=your_key_here
   ```

**Free tier:** 1M tokens/day, 15 requests/min → Enough for 40+ resumes/day

---

## Troubleshooting

### "pdflatex not found"

**Solution:**
- macOS: `brew install mactex`
- Ubuntu: `sudo apt-get install texlive-latex-extra`
- Windows: Download and install MiKTeX

### "ModuleNotFoundError: No module named 'fastapi'"

**Solution:**
```bash
cd backend
pip install -r requirements.txt
```

### "npm: command not found"

**Solution:** Reinstall Node.js from https://nodejs.org

### "Backend connection refused"

**Solution:**
- Ensure backend is running: `uvicorn main:app --reload`
- Check backend is on port 8000
- Check `NEXT_PUBLIC_BACKEND_URL=http://localhost:8000` in frontend

### "Gemini API error: Invalid API key"

**Solution:**
- Get a new key from https://ai.google.dev/aistudio
- Update `backend/.env`
- Restart backend

### "PDF compilation failed"

**Solution:**
- Test LaTeX locally: `pdflatex backend/templates/default_resume.tex`
- Check for LaTeX errors in the output
- Verify resume template is valid

---

## Using Docker (Alternative)

If you prefer Docker:

```bash
# Requires Docker and Docker Compose installed

cd resume-tailor-project

# Add API key to .env
nano backend/.env

# Start all services
docker-compose up --build

# Open browser
open http://localhost:3000
```

**Stops:**
```bash
docker-compose down
```

---

## Common Commands

```bash
# Backend only
make backend

# Frontend only
make frontend

# Both (with Docker)
make docker

# Clean up
make clean

# View help
make help
```

---

## Next Steps

- ✅ **Tailor your first resume** (5 min)
- 📚 **Read README.md** for full docs
- 🏗️ **Read ARCHITECTURE.md** for technical deep dive
- 📝 **Customize `backend/templates/default_resume.tex`** with your own resume
- 🚀 **Process 40+ jobs/day** efficiently
- 🐳 **Deploy to cloud** (optional)

---

## Support

- 📖 **Docs:** See README.md
- 🏗️ **Architecture:** See ARCHITECTURE.md
- 🐛 **Issues:** Check GitHub issues
- 💬 **Questions:** Open a GitHub discussion

---

## Pro Tips

1. **Customize Your Default Resume:**
   - Edit `backend/templates/default_resume.tex`
   - Keep all LaTeX commands intact
   - Only change the resume content

2. **For 40+ Jobs/Day:**
   - Keep browser tab open
   - Submit 5-10 jobs, let them process
   - Download in batches
   - Backend stays running all day

3. **Screenshot Tips:**
   - Take clear photos of JD sections
   - 3 images per job works great
   - Better than long text paste for some users

4. **Review Before Sending:**
   - Always check tailored resume
   - AI isn't perfect
   - Fix any odd phrasings manually

5. **Organize Your Outputs:**
   - Resumes auto-sorted by Company_Role
   - Use timestamps to find latest version
   - Archive old versions if needed

---

**Happy tailoring! 🚀**

Get your Gemini API key and start in 5 minutes.
