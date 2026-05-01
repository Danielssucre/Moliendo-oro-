#!/bin/bash
# Unified Startup for Quantum Trading Dashboard

PROJECT_ROOT=$(pwd)
export PROJECT_ROOT=$PROJECT_ROOT
# [FIX] Asegurar que npm/node estén en el PATH para despliegue en macOS
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
# Add backend directory to PYTHONPATH
export PYTHONPATH=$PROJECT_ROOT:$PROJECT_ROOT/dashboard/backend

echo "🚀 Launching Quantum Trading Dashboard..."

# 0. LAUNCH METATRADER 5 AUTOMATICALLY (must be first)
echo "📊 Opening MetaTrader 5..."
if ! pgrep -f "MetaTrader 5" > /dev/null 2>&1; then
    open -a "MetaTrader 5"
    echo "⏳ Waiting for MetaTrader 5 to load (10s)..."
    sleep 10
else
    echo "✅ MetaTrader 5 is already running."
fi

# 0b. LAUNCH THE RPYC BRIDGE (siliconmetatrader5 port 18812)
WINE_BIN="/Applications/MetaTrader 5.app/Contents/SharedSupport/wine/bin/wine64"
WINE_PREFIX="$HOME/Library/Application Support/net.metaquotes.wine.metatrader5"
MT5_DIR="$WINE_PREFIX/drive_c/Program Files/MetaTrader 5"

if ! lsof -i :18812 | grep -q LISTEN 2>/dev/null; then
    echo "🔌 Starting RPyC Bridge on port 18812..."
    export WINEPREFIX="$WINE_PREFIX"
    export WINEDEBUG="-all"
    "$WINE_BIN" "C:\\Program Files\\MetaTrader 5\\python.exe" "C:\\Program Files\\MetaTrader 5\\rpyc_start.py" > /dev/null 2>&1 &
    
    echo "⏳ Waiting for bridge to open port 18812..."
    for i in $(seq 1 20); do
        if lsof -i :18812 | grep -q LISTEN 2>/dev/null; then
            echo "✅ RPyC Bridge is live on port 18812 (${i}s)"
            break
        fi
        sleep 1
    done
else
    echo "✅ RPyC Bridge already listening on port 18812."
fi

# 1. Kill any existing services on ports 8000 and 5173/5174
lsof -ti:8000 | xargs kill -9 2>/dev/null
lsof -ti:5173 | xargs kill -9 2>/dev/null
lsof -ti:5174 | xargs kill -9 2>/dev/null

# 2. Start Backend in background
echo "📡 Starting Backend API (Port 8000)..."
nohup ./.venv/bin/python dashboard/backend/app/main.py > logs/dashboard_backend.log 2>&1 &
BACKEND_PID=$!

# 2b. Start Quantum Bridge Server (Port 8080)
echo "🌉 Starting Quantum Bridge (Port 8080)..."
export PYTHONPATH=$PYTHONPATH:$PROJECT_ROOT/src
nohup ./.venv/bin/python src/scripts/bridge_server.py > logs/bridge_server.log 2>&1 &
BRIDGE_PID=$!

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
