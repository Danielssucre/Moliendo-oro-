#!/bin/bash
# Script to run the trading agent with 'caffeinate' to prevent Mac sleep.
# It uses the absolute path to the virtual environment's python.

# Absolute path to the project root
PROJECT_ROOT="/Users/danielsuarezsucre/TRADING/trading_agent"
cd "$PROJECT_ROOT"

echo "🚀 Starting Hybrid Trading Agent in ALWAYS-ON mode (Caffeinate)..."
echo "ℹ️  Note: Keep your Mac connected to power for best results with the lid closed."

caffeinate -dis "$PROJECT_ROOT/.venv/bin/python3" "$PROJECT_ROOT/src/scripts/run_live.py" --capital 100000
