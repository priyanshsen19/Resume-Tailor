#!/bin/bash

set -e

echo "🎯 Resume Tailor - Quick Setup"
echo "=============================="
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 not found. Please install Python 3.10+"
    exit 1
fi
echo "✅ Python found: $(python3 --version)"

# Check Node
if ! command -v node &> /dev/null; then
    echo "❌ Node.js not found. Please install Node.js 18+"
    exit 1
fi
echo "✅ Node.js found: $(node --version)"

# Check pdflatex
if ! command -v pdflatex &> /dev/null; then
    echo "❌ pdflatex not found. Install LaTeX:"
    echo "   macOS: brew install mactex"
    echo "   Ubuntu: sudo apt-get install texlive-latex-base texlive-latex-extra"
    echo "   Windows: Download MiKTeX from https://miktex.org/download"
    exit 1
fi
echo "✅ pdflatex found"

echo ""
echo "📦 Setting up backend..."

# Backend setup
cd backend
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "✅ Virtual environment created"
fi

source venv/bin/activate
pip install -q -r requirements.txt
echo "✅ Backend dependencies installed"

# Create .env if doesn't exist
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "✅ Created .env file"
    echo "⚠️  Please edit backend/.env and add your GEMINI_API_KEY"
fi

deactivate
cd ..

echo ""
echo "📦 Setting up frontend..."

# Frontend setup
cd frontend
if [ ! -d "node_modules" ]; then
    npm install -q
    echo "✅ Frontend dependencies installed"
fi

# Create .env.local if doesn't exist
if [ ! -f ".env.local" ]; then
    cp .env.example .env.local
    echo "✅ Created .env.local file"
fi

cd ..

echo ""
echo "✅ Setup complete!"
echo ""
echo "🚀 Next steps:"
echo ""
echo "1. Edit your API key:"
echo "   nano backend/.env"
echo "   # Add: GEMINI_API_KEY=your_key_here"
echo ""
echo "2. Start backend (Terminal 1):"
echo "   make backend"
echo ""
echo "3. Start frontend (Terminal 2):"
echo "   make frontend"
echo ""
echo "4. Open browser:"
echo "   http://localhost:3000"
echo ""
echo "Or use Docker:"
echo "   make docker"
echo ""
