# Implementation Plan: Adjusting Concurrency Limit (3 Trades)

As per user request, we will increase the total allowed concurrent trades for small accounts (Axi Survival mode) from 1 to 3. Matches existing "Unique Symbol Lock" logic to ensure those 3 trades are on different pairs.

## Proposed Changes

### Core Logic (`src/scripts/run_live.py`)

#### [MODIFY] [run_live.py](file:///Users/danielsuarezsucre/TRADING/trading_agent/src/scripts/run_live.py)

1.  Update the `max_concurrent` variable from 1 to 3 in the `is_small_cap` block.

```python
# Before
max_concurrent = 1 

# After
max_concurrent = 3
```

## Verification Plan

### Automated Verification
1.  Check `logs/live_startup_new.log` for logs showing multiple (up to 3) active positions.
2.  Ensure that the `[CONCURRENCY LIMIT]` warning only appears when `active_count >= 3`.

### Manual Verification
- Monitor the MT5 terminal to confirm the bot successfully manages up to 3 diverse pairs simultaneously.
