.PHONY: help setup install backend frontend docker clean

help:
	@echo "Resume Tailor - Makefile Commands"
	@echo "=================================="
	@echo "make setup       - Setup backend and frontend"
	@echo "make install    - Install all dependencies"
	@echo "make backend    - Run backend server only"
	@echo "make frontend   - Run frontend server only"
	@echo "make docker     - Run with Docker Compose"
	@echo "make clean      - Remove build artifacts and cache"
	@echo "make logs       - Show Docker logs"

setup: install
	@echo "✅ Setup complete!"
	@echo ""
	@echo "Next steps:"
	@echo "1. Edit backend/.env and add your GEMINI_API_KEY"
	@echo "2. Run 'make backend' in one terminal"
	@echo "3. Run 'make frontend' in another terminal"
	@echo "4. Open http://localhost:3000"

install: install-backend install-frontend
	@echo "✅ All dependencies installed!"

install-backend:
	@echo "📦 Installing backend dependencies..."
	cd backend && python3 -m venv venv
	cd backend && . venv/bin/activate && pip install -r requirements.txt

install-frontend:
	@echo "📦 Installing frontend dependencies..."
	cd frontend && npm install

backend:
	@echo "🚀 Starting backend server..."
	@echo "📍 Backend at http://localhost:8000"
	cd backend && . venv/bin/activate && uvicorn main:app --reload --host 0.0.0.0 --port 8000

frontend:
	@echo "🚀 Starting frontend server..."
	@echo "📍 Frontend at http://localhost:3000"
	cd frontend && npm run dev

docker:
	@echo "🐳 Starting with Docker Compose..."
	@echo "📍 Frontend at http://localhost:3000"
	@echo "📍 Backend at http://localhost:8000"
	docker-compose up --build

docker-down:
	@echo "🛑 Stopping Docker containers..."
	docker-compose down

logs:
	docker-compose logs -f

clean:
	@echo "🧹 Cleaning up..."
	rm -rf backend/venv
	rm -rf backend/__pycache__
	rm -rf backend/*.log
	rm -rf frontend/node_modules
	rm -rf frontend/.next
	rm -rf frontend/out
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	@echo "✅ Cleanup complete!"

.DEFAULT_GOAL := help
