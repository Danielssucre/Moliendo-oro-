#!/bin/bash
#
# RESTART BOT
# Simple script to restart the trading bot cleanly
#

cd /Users/danielsuarezsucre/TRADING/trading_agent

echo "=========================================="
echo "🔄 RESTARTING TRADING BOT"
echo "=========================================="

# Kill existing process
echo "1. Killing existing processes..."
pkill -f "run_live.py" 2>/dev/null
sleep 2

# Clean PID file
rm -f logs/bot.pid 2>/dev/null

# Start bot
echo "2. Starting bot..."
source .venv/bin/activate
nohup python3 src/scripts/run_live.py >> logs/dashboard_bot.log 2>&1 &
BOT_PID=$!
echo $BOT_PID > logs/bot.pid

echo "3. Bot started with PID: $BOT_PID"
echo "=========================================="
echo "Logs: tail -f logs/dashboard_bot.log"
echo "=========================================="
