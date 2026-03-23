# Plan to Fix Bot "Disconnection" and Silent Crashes

The user is experiencing periods where the bot stops logging. This is caused by two separate issues:
1. **Silent Exception**: An `Iter Error` occurs because `symbol` is used instead of `pair` on line 2357 of `run_live.py`.
2. **Aggressive Safety Protocols**: The `HARD FUSE` (Daily Loss Protection) triggers a 24-hour `time.sleep` when equity reaches a threshold. For a $27 account with 26 active trades, small fluctuations trigger this, making the bot appear disconnected.

## Proposed Changes

### Trading Logic Fixes
#### [MODIFY] [run_live.py](file:///Users/danielsuarezsucre/TRADING/trading_agent/src/scripts/run_live.py)
- **Variable Fix**: Update `execute_mt5_trade` calls and surrounding logic to use `pair` consistently instead of `symbol` in the main loop.
- **Safety Adjustments**: 
    - Reduce the `HARD FUSE` sleep from 24 hours to 1 hour for accounts < $100.
    - Log a clearer message when entering a long safety sleep so the user knows the bot is intentionally idle.
    - Ensure `symbol_info` is checked for `None` before accessing attributes like `trade_tick_size`.

## Verification Plan

### Automated Tests
- Run `python3 src/scripts/run_live.py` and verify that the `Iter Error` no longer appears in the logs.
- Simulate an equity drop (temporary test override) to verify the new 1-hour safety cool-off.

### Manual Verification
- Monitor the dashboard to ensure the "BOT ACTIVE" status remains stable and logs continue to flow.
