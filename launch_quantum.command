#!/bin/bash

# Navigate to the project directory
cd "/Users/danielsuarezsucre/TRADING/trading_agent"

# Kill any existing dashboard processes to ensure a clean start
lsof -ti:8000 | xargs kill -9 2>/dev/null
lsof -ti:5173 | xargs kill -9 2>/dev/null

# Open the browser immediately (it will load once the server is ready)
open "http://localhost:5173"

# Run the dashboard script
./start_dashboard.sh
