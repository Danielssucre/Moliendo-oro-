#!/bin/bash
# Unified Startup for Quantum Trading Dashboard

PROJECT_ROOT=$(pwd)
export PROJECT_ROOT=$PROJECT_ROOT
# Add backend directory to PYTHONPATH
export PYTHONPATH=$PROJECT_ROOT:$PROJECT_ROOT/dashboard/backend

echo "🚀 Launching Quantum Trading Dashboard..."

# 1. Kill any existing services on ports 8000 and 5173/5174
lsof -ti:8000 | xargs kill -9 2>/dev/null
lsof -ti:5173 | xargs kill -9 2>/dev/null
lsof -ti:5174 | xargs kill -9 2>/dev/null

# 2. Start Backend in background
echo "📡 Starting Backend API (Port 8000)..."
nohup ./.venv/bin/python dashboard/backend/app/main.py > logs/dashboard_backend.log 2>&1 &
BACKEND_PID=$!

# 3. Start Frontend
echo "💻 Starting Frontend (Vite)..."
cd dashboard/frontend
nohup npm run dev -- --port 5173 > ../../logs/dashboard_frontend.log 2>&1 &
FRONTEND_PID=$!

echo "✅ Dashboard is now running in the BACKGROUND."
echo "➜ Backend API: http://localhost:8000"
echo "➜ Frontend UI: http://localhost:5173"
echo "-----------------------------------------------"
echo "You can safely CLOSE this terminal window."
echo "To stop the services, run: ./stop_dashboard.sh"
echo "-----------------------------------------------"

# Don't wait, just exit leaving processes running
exit 0
