# Implementation Plan: Restricting XAUUSD for Small Accounts

The user reported a near-liquidation event on XAUUSD on a small account (~$23). To prevent future high-risk exposure on Gold for small capitals, we will implement a hard block on `XAUUSD` for any account where `INITIAL_CAPITAL < 100,000`.

## Proposed Changes

### Core Logic (`src/scripts/run_live.py`)

#### [MODIFY] [run_live.py](file:///Users/danielsuarezsucre/TRADING/trading_agent/src/scripts/run_live.py)

1.  Inside the main signal loop (`for pair in ASSET_MAP.keys():`), add a condition to check if the current pair is Gold.
2.  If the pair is `XAUUSD` (or mapped to Gold) and `INITIAL_CAPITAL < 100000`, skip the symbol entirelty with a log warning.

```python
for pair in ASSET_MAP.keys():
    symbol = ASSET_MAP.get(pair)
    
    # --- PHASE 92: SMALL CAP PROTECTION (GOLD BLOCK) ---
    if "XAU" in symbol.upper() and INITIAL_CAPITAL < 100000:
        logger.info(f"🛡️ [GOLD SHIELD] Skipping {symbol} (Initial Capital ${INITIAL_CAPITAL:,} < $100,000)")
        continue
```

## Verification Plan

### Automated Verification
1.  Check the logs after implementation.
2.  Verify that `XAUUSD` is explicitly skipped with the message `🛡️ [GOLD SHIELD] Skipping XAUUSD...`.
3.  Ensure other symbols (currencies) continue to be processed normally.

### Manual Verification
- Confirm with the user that the Gold trades have stopped appearing in the dashboard or pulse reports.
