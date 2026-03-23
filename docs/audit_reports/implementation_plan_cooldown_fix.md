# FIX: Basket Profit Leakage & Overtrading

## Background
The Axi account is experiencing "Flat Equity" ($32-$33) despite 5 successful basket locks today. Forensic audit shows the bot is re-entering the market instantly after a lock, often with **6 concurrent trades** due to a race condition in the closure sync.

## Proposed Changes

### [Axi Execution Engine]
#### [MODIFY] [run_live.py](file:///Users/danielsuarezsucre/TRADING/trading_agent/src/scripts/run_live.py)
1. **Implement `LAST_BASKET_RELEASE_TIME`**: A global timestamp set after every successful Basket Lock.
2. **Add Cooldown Check**: At the start of the signal scanner, block all new entries if `current_time - LAST_BASKET_RELEASE_TIME < 1800` (30 minutes).
3. **Hard Concurrency Clamp**: Ensure `max_concurrent` is strictly enforced to 2-3 for accounts < $100.
4. **MT5 Sync Delay**: Add a 5-second `time.sleep` after the Basket Lock's mass-closure to allow the MT5 terminal to update the position list.

## Verification Plan
1. Restart the `run_live.py` process to ensure the latest code (with `max_concurrent = 3`) is active.
2. Monitor `dashboard_bot.log` after the next basket lock to verify the 30-min silence period.
