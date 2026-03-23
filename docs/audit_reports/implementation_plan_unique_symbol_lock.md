# Implementation Plan: Unique Symbol Lock (Axi Survival)

To improve margin management and enforce variability in the "Extreme Survival" mode, we will implement a hard restriction that prevents more than one order (active or pending) per unique symbol.

## Proposed Changes

### Core Logic (`src/scripts/run_live.py`)

#### [MODIFY] [run_live.py](file:///Users/danielsuarezsucre/TRADING/trading_agent/src/scripts/run_live.py)

We will modify the signal processing loop to include a symbol-specific exposure check.

1.  **Exposure Scanner**: Before processing any signal for a `pair`, we will query MT5 for both active positions and pending orders.
2.  **Uniqueness Enforcement**: If `INITIAL_CAPITAL < 100,000`:
    - Combine list of active positions and pending orders.
    - Check if the current `symbol` (e.g., EURUSD) is already in that list.
    - If it is, skip all signal variants (ALFA, EXPL, NEME) for that symbol during this iteration.

```python
# Pseudo-code logic to be injected:
if INITIAL_CAPITAL < 100000:
    positions = mt5_client.positions_get()
    orders = mt5_client.orders_get()
    
    # Extract symbols from active and pending
    active_symbols = [p.symbol for p in positions] if positions else []
    pending_symbols = [o.symbol for o in orders] if orders else []
    total_exposed_symbols = set(active_symbols + pending_symbols)
    
    if symbol in total_exposed_symbols:
        logger.info(f"🚫 [SYMBOL LOCK] Skiping {symbol}: Already has active/pending exposure.")
        continue
```

## Verification Plan

### Automated Verification
1.  Monitor `logs/live_startup_new.log`.
2.  Place a manual pending order (or wait for the bot) on a symbol.
3.  Verify that subsequent signals for the same symbol are blocked with the `[SYMBOL LOCK]` message.

### Manual Verification
- Confirm in the MetaTrader 5 terminal that no two orders (active or pending) exist for the same symbol simultaneously under the survival profile.
