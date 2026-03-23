# Plan: Fix Binance Balance Mismatch

To prevent 'insufficient balance' errors during Take Profit or Stop Loss sell orders, we will modify the bot to verify the actual available balance on the exchange before attempting to execute a sell order.

## Proposed Changes

### [Binance Bot](file:///Users/danielsuarezsucre/TRADING/trading_agent/src/scripts/run_skypie_binance.py)

#### [MODIFY] [run_skypie_binance.py](file:///Users/danielsuarezsucre/TRADING/trading_agent/src/scripts/run_skypie_binance.py)
- Update the TP and SL logic to fetch the real balance of the base asset.
- Implement a helper to extract the base asset from the symbol (e.g., 'SOL' from 'SOLUSDT').
- Sanitize the quantity to sell using exchange precision.

## Verification Plan

### Manual Verification
- Review the logs for the next trade to ensure it fetches the balance correctly before selling.
- Log the difference between the tracked quantity and the real exchange balance.
