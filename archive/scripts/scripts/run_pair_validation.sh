#!/bin/bash
# Phase 12: Sequential Pair Validation
# Runs optimizer once per pair to identify winners

PAIRS=("EURUSD" "GBPUSD" "USDJPY" "AUDUSD" "USDCAD" "NZDUSD" "EURGBP" "EURJPY" "GBPJPY" "AUDJPY")

echo "🚀 Phase 12: Individual Pair Validation"
echo "Testing ${#PAIRS[@]} pairs with EMA 9/15 + Volume template"
echo "Target: Win Rate ≥ 55%, Profit Factor ≥ 1.2"
echo ""

# Create results file
RESULTS_FILE="/Users/danielsuarezsucre/TRADING/trading_agent/logs/phase12_results.txt"
echo "Pair,WinRate,ProfitFactor,MaxDD,Trades,Status" > $RESULTS_FILE

for PAIR in "${PAIRS[@]}"; do
    echo "========================================"
    echo "🧪 TESTING $PAIR"
    echo "========================================"
    
    # Temporarily update optimizer to test single pair
    # (We'll modify strategy_optimizer_loop.py to read from env var)
    export TEST_PAIR=$PAIR
    export GEMINI_API_KEY=AIzaSyA8Fja6nXeuXGpkJHlbk9w56MVq661QBR0
    
    # Run optimizer
    python3 /Users/danielsuarezsucre/TRADING/trading_agent/scripts/strategy_optimizer_loop.py > "/Users/danielsuarezsucre/TRADING/trading_agent/logs/phase12_${PAIR}.log" 2>&1
    
    # Extract results from log
    WR=$(grep "Win Rate:" "/Users/danielsuarezsucre/TRADING/trading_agent/logs/phase12_${PAIR}.log" | tail -n 1 | grep -oE '[0-9]+\.[0-9]+%' | head -n 1 | tr -d '%')
    PF=$(grep "PF:" "/Users/danielsuarezsucre/TRADING/trading_agent/logs/phase12_${PAIR}.log" | tail -n 1 | grep -oE '[0-9]+\.[0-9]+' | head -n 1)
    DD=$(grep "Max DD:" "/Users/danielsuarezsucre/TRADING/trading_agent/logs/phase12_${PAIR}.log" | tail -n 1 | grep -oE '[0-9]+\.[0-9]+%' | head -n 1 | tr -d '%')
    
    # Determine status
    if (( $(echo "$WR >= 55" | bc -l) )) && (( $(echo "$PF >= 1.2" | bc -l) )); then
        STATUS="PASS"
    else
        STATUS="FAIL"
    fi
    
    echo "$PAIR,$WR,$PF,$DD,N/A,$STATUS" >> $RESULTS_FILE
    echo "📊 $PAIR: ${WR}% WR | PF $PF | DD ${DD}% | $STATUS"
    echo ""
done

echo "========================================"
echo "📊 FINAL RESULTS"
echo "========================================"
cat $RESULTS_FILE
echo ""
echo "💾 Results saved to: $RESULTS_FILE"
