#!/bin/bash
#
# GUARDIAN WATCHDOG
# ===================
# Auto-restart script for Nanobot Trading System
# Monitors bot health and restarts if:
# 1. Bot process dies
# 2. Log file doesn't change for 5 minutes (frozen)
#
# Usage: ./watchdog.sh
#

BOT_NAME="run_live.py"
BOT_SCRIPT="src/scripts/run_live.py"
LOG_FILE="logs/dashboard_bot.log"
PID_FILE="logs/bot.pid"
RESTART_DELAY=10
LOG_CHECK_TIMEOUT=300  # 5 minutes

cd /Users/danielsuarezsucre/TRADING/trading_agent

echo "=========================================="
echo "🛡️ GUARDIAN WATCHDOG - Starting..."
echo "=========================================="
echo "Bot: $BOT_NAME"
echo "Log: $LOG_FILE"
echo "Restart Delay: ${RESTART_DELAY}s"
echo "Log Timeout: ${LOG_CHECK_TIMEOUT}s"
echo "=========================================="

restart_bot() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 🛡️ GUARDIAN: Restarting bot..."
    
    # Kill existing process if any
    if [ -f "$PID_FILE" ]; then
        OLD_PID=$(cat "$PID_FILE")
        if ps -p $OLD_PID > /dev/null 2>&1; then
            echo "[$(date '+%Y-%m-%d %H:%M:%S')] 🛡️ Killing old process: $OLD_PID"
            kill -9 $OLD_PID 2>/dev/null
        fi
        rm -f "$PID_FILE"
    fi
    
    # Also kill any stray processes
    pkill -f "$BOT_SCRIPT" 2>/dev/null
    
    sleep 2
    
    # Start bot with virtual environment
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 🚀 Starting bot..."
    source .venv/bin/activate
    nohup python3 "$BOT_SCRIPT" >> "$LOG_FILE" 2>&1 &
    NEW_PID=$!
    echo $NEW_PID > "$PID_FILE"
    
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ✅ Bot started with PID: $NEW_PID"
    
    sleep 5
    
    # Verify bot started successfully
    if ps -p $NEW_PID > /dev/null 2>&1; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] ✅ Bot health check PASSED"
        return 0
    else
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] ❌ Bot health check FAILED"
        return 1
    fi
}

# Initial start
restart_bot

# Main monitoring loop
LAST_LOG_SIZE=0
STALL_COUNT=0

while true; do
    sleep 30
    
    CURRENT_PID=""
    if [ -f "$PID_FILE" ]; then
        CURRENT_PID=$(cat "$PID_FILE")
    fi
    
    # Check 1: Is bot process running?
    if [ -n "$CURRENT_PID" ]; then
        if ! ps -p $CURRENT_PID > /dev/null 2>&1; then
            echo "[$(date '+%Y-%m-%d %H:%M:%S')] 💀 Bot process DEAD (PID: $CURRENT_PID)"
            restart_bot
            continue
        fi
    else
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] 💀 No PID file found"
        restart_bot
        continue
    fi
    
    # Check 2: Is log file being updated?
    if [ -f "$LOG_FILE" ]; then
        CURRENT_LOG_SIZE=$(stat -f%z "$LOG_FILE" 2>/dev/null || stat -c%s "$LOG_FILE" 2>/dev/null)
        
        if [ "$CURRENT_LOG_SIZE" == "$LAST_LOG_SIZE" ]; then
            STALL_COUNT=$((STALL_COUNT + 1))
            if [ $STALL_COUNT -ge 10 ]; then  # 5 minutes (30s * 10)
                echo "[$(date '+%Y-%m-%d %H:%M:%S')] 🧊 Bot FROZEN (log not updating for 5+ min)"
                echo "[$(date '+%Y-%m-%d %H:%M:%S')] 🛡️ Initiating restart..."
                restart_bot
                STALL_COUNT=0
            fi
        else
            STALL_COUNT=0
        fi
        
        LAST_LOG_SIZE=$CURRENT_LOG_SIZE
    fi
    
    # Check 3: Memory usage (warning if > 1GB)
    MEM_MB=$(ps -o rss= -p $CURRENT_PID 2>/dev/null | awk '{print $1/1024}')
    if (( $(echo "$MEM_MB > 1024" | bc -l 2>/dev/null || echo 0) )); then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] ⚠️ High memory usage: ${MEM_MB}MB"
    fi
    
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 💚 Bot alive (PID: $CURRENT_PID) | Log: ${CURRENT_LOG_SIZE:-0} bytes"
    
done
