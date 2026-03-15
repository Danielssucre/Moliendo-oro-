#!/bin/bash
# Stop all Quantum Dashboard services

PROJECT_ROOT=$(pwd)
echo "🛑 Stopping Quantum Trading Dashboard services..."

# Kill Backend
lsof -ti:8000 | xargs kill -9 2>/dev/null
# Kill Frontend
lsof -ti:5173 | xargs kill -9 2>/dev/null
lsof -ti:5174 | xargs kill -9 2>/dev/null

# Optionally kill the bot if running
# We can look for run_live.py
ps aux | grep run_live.py | grep -v grep | awk '{print $2}' | xargs kill -9 2>/dev/null

echo "✅ Services stopped."
