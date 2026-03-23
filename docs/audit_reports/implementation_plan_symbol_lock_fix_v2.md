# Hardened Symbol Lock & Mega Grid Suppression (Axi Fix)

This plan addresses the critical issue where the Axi survival account is duplicating trades on the same pair, hindering diversification and risking the remaining capital.

## Proposed Changes

### [MT5 Core Execution]

#### [MODIFY] [run_live.py](file:///Users/danielsuarezsucre/TRADING/trading_agent/src/scripts/run_live.py)
Update `execute_mt5_trade` to enforce the unique symbol lock before any order submission.

```python
def execute_mt5_trade(pair, order_type_str, price, sl, tp, volume, comment="Nanobot HIVE V5"):
    # ...
    if not MT5_CONNECTED: return
    
    # [NEW] ENSURE SYMBOL LOCK (Extreme Survival)
    if not check_correlation_exposure(pair, order_type_str):
        # logger already handles the message
        return None
    # ...
```

### [Strategy Loop Configuration]

#### [MODIFY] [run_live.py](file:///Users/danielsuarezsucre/TRADING/trading_agent/src/scripts/run_live.py)
Suppress Mega Grid data collection for small accounts.

```python
# Around L2478
if mega_grid_enabled and not is_small_cap:
    # register_signal_pool...
```

## Verification Plan

### Automated Tests
- Review `dashboard_bot.log` to confirm only one trade is opened per symbol.
- Monitor active positions on the dashboard to ensure no overlapping symbols.

### Manual Verification
- Verify that `AUDUSD` or other frequented pairs only have a single active/pending entry.
