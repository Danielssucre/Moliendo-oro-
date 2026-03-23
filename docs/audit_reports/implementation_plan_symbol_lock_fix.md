# Implementation Plan: Fixing Unique Symbol Lock (Race Condition & Case-Sensitivity)

The previous implementation failed because it was case-sensitive ($EUMNZD \neq eumnzd$) and it didn't account for multiple triggers within the same loop iteration before the MT5 server could update the position list.

## Proposed Changes

### Core Logic (`src/scripts/run_live.py`)

#### [MODIFY] [run_live.py](file:///Users/danielsuarezsucre/TRADING/trading_agent/src/scripts/run_live.py)

1.  **Standardize Case**: All symbol comparisons will use `.upper()`.
2.  **Local Iteration Tracking**: Create a set `iteration_exposed_symbols` at the start of the `main()` loop to track symbols that have just had an order placed during this specific scan.
3.  **Enhanced Symbol Lock**:
    - Update the check to look into `iteration_exposed_symbols` PLUS the results from `mt5_client`.
    - Move the primary check to be more robust.

```python
# --- TRACKING SETUP ---
iteration_exposed_symbols = set() # Reset every main loop iteration

for pair in ASSET_MAP.keys():
    symbol = ASSET_MAP.get(pair)
    
    # CASE-INSENSITIVE CHECK
    try:
        current_pos = mt5_client.positions_get()
        current_ord = mt5_client.orders_get()
        
        # Build normalized uppercase set of all exposure
        remote_exposed = set()
        if current_pos: remote_exposed.update([p.symbol.upper() for p in current_pos])
        if current_ord: remote_exposed.update([o.symbol.upper() for o in current_ord])
        
        # Combined Lock
        if symbol.upper() in remote_exposed or symbol.upper() in iteration_exposed_symbols:
            logger.debug(f"🔒 [SYMBOL LOCK] {symbol} already exposed (Remote or Local). Skipping.")
            continue
    except: pass

    # ... after order placement ...
    if result and result.retcode == mt5_client.TRADE_RETCODE_DONE:
        iteration_exposed_symbols.add(symbol.upper())
```

## Verification Plan

### Automated Verification
1.  Run the bot and check logs for `[SYMBOL LOCK]` messages.
2.  Specifically look for blocks on symbols that previously duplicated (e.g., EUMNZD).

### Manual Verification
- Verify in MT5 that no two positions/orders for the same pair are opened, even if signals from ALFA and EXPL appear simultaneously.
