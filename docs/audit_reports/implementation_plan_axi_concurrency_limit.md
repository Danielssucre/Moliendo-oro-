# Small Capital Concurrent Trade Limit ($13 Recovery)

Prevent "over-exposure" in small accounts by limiting the maximum number of active trades to 5. Also fix a scoping error with the `is_small_cap` variable.

## Proposed Changes

### [MT5 Bot Runner]
#### [MODIFY] [run_live.py](file:///Users/danielsuarezsucre/TRADING/trading_agent/src/scripts/run_live.py)
- **Variable Scoping Fix**: Move `is_small_cap` definition to the start of the signal processing loop to avoid `UnboundLocalError`.
- **Concurrency Limit**: 
    - At the start of each scan, count active MT5 positions.
    - If `is_small_cap` is True and `active_positions >= 5`, block any new trades (Sniper, Chameleon, Kaido, etc.).
    - Log a specific message: `⚠️ [CONCURRENCY LIMIT] 5/5 trades active. Skipping new setups.`

## Verification Plan

### Automated Tests
- Restart the bot and verify no `UnboundLocalError: cannot access local variable 'is_small_cap'` appears in `logs/dashboard_bot.log`.
- Manually open 5 small trades in MT5 and verify the bot logs the concurrency skip message.

### Manual Verification
- Monitor Telegram pulses to ensure "Active Trades" stops at 5 when the limit is reached.
