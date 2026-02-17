# Multi-Pair Precision Strategy - Quick Start Guide

## Phase 14: EURUSD + GBPUSD + USDJPY Portfolio

### Portfolio Configuration

**Validated Pairs (3):**
- EURUSD: 62.5% WR (Phase 11)
- GBPUSD: 66.7% WR (Phase 14.1)
- USDJPY: 66.7% WR (Phase 14.2)

**Capital Allocation:**
- 33% per pair (equal weight)
- 0.25% risk per trade (of allocated capital)
- Max 1 trade/pair/day

**Expected Performance:**
- Average Win Rate: 63.6%
- Expected Signals: 24/month (~6/week)
- Frequency: 1-2 signals/day

---

## Quick Start

### 1. Single Scan (Manual Trading)

```bash
cd /Users/danielsuarezsucre/TRADING/trading_agent
python3 run_multi_pair.py --capital 100000
```

**Output:** Analyzes all 3 pairs and displays signals if found.

### 2. Continuous Scan Mode

```bash
python3 run_multi_pair.py --capital 100000 --continuous --interval 60
```

**Scans every 60 minutes** and displays new signals.

### 3. Custom Capital

```bash
python3 run_multi_pair.py --capital 50000
```

Adjusts allocation automatically (50k × 33% = $16,667 per pair).

---

## Execution Workflow

### When Signal Appears:

1. **Review Signal Details:**
   - Direction (BUY/SELL)
   - Entry Price
   - Stop Loss
   - Take Profit
   - Risk Amount

2. **Execute Manually in MT4/MT5:**
   - Place LIMIT order at entry price
   - Set SL and TP as shown
   - Use calculated lot size

3. **Track Trade:**
   - Monitor via MT4/MT5
   - Max 1 trade/pair/day
   - Close manually if needed

### Daily Limits:

- **Max 3 trades/day** (1 per pair)
- **Max daily risk:** 0.75% of total capital
- **Stop after 2 consecutive losses** (optional safeguard)

---

## Parameters (Phase 11 Optimal)

```python
OPTIMAL_CONFIG = {
    "strategy_template": "lit_ema_9_15_vol",  # EMA 9/15 + Volume
    "hurst_trending_threshold": 0.60,
    "hurst_meanrev_threshold": 0.40,
    "ml_stop_hunt_threshold": 0.80,
    "soft_decision_threshold": 0.60,
    "monte_carlo_threshold": 0.45,
    "adx_threshold": 20,
    "min_risk_reward": 1.0,  # 1:1 R:R
    "sl_atr_multiplier": 1.0,
    "tp_atr_multiplier": 1.0,
    "max_lookahead": 44,  # 11h for M15
}
```

---

## Example Output

```
╔══════════════════════════════════════════════════════════════╗
║         🎯 MULTI-PAIR PRECISION STRATEGY                    ║
║         Phase 14: EURUSD + GBPUSD + USDJPY                  ║
╚══════════════════════════════════════════════════════════════╝

📊 PORTFOLIO CONFIGURATION:
   Pairs: EURUSD, GBPUSD, USDJPY
   Capital Allocation: 33% per pair
   Risk per Trade: 0.25% of allocated capital

💰 CAPITAL ALLOCATION:
   Total Capital: $100,000.00
   Capital per Pair: $33,333.33
   Risk per Trade: $83.33

🔍 ANALYZING PORTFOLIO...

🎯 SIGNAL FOUND: GBPUSD
──────────────────────────────────────────────────────────────
Direction: BUY
Entry: 1.27450
Stop Loss: 1.27320 (13.0 pips)
Take Profit: 1.27580 (13.0 pips)
Risk/Reward: 1:1.0
Lot Size: 0.64
Risk Amount: $83.33

📊 Portfolio Context:
   Allocated Capital: $33,333.33
   Daily Trades for GBPUSD: 1/1
──────────────────────────────────────────────────────────────

📊 PORTFOLIO SCAN COMPLETE
Signals Found: 1/3
Total Daily Risk: $83.33
```

---

## Troubleshooting

### No Signals Found?

**Normal!** The strategy is selective (63.6% WR requires quality setups).

**Expected frequency:** 1-2 signals/day across all 3 pairs.

**Recommendation:** Run continuous scan mode and wait.

### Too Many Signals?

**Unlikely** with current parameters, but if it happens:
- Increase `soft_decision_threshold` to 0.65
- Increase `ml_stop_hunt_threshold` to 0.85

### API Rate Limits?

**Solution:** Increase scan interval:
```bash
python3 run_multi_pair.py --continuous --interval 120  # 2 hours
```

---

## Next Steps

1. **Test with Demo Account** (2-4 weeks)
2. **Validate 55%+ WR in real-time**
3. **Go Live** if demo confirms performance

**Good luck!** 🎯
