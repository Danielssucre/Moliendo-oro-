# Implementation Plan: Binance Insufficient Balance Fix v2

The previous 0.1% buffer failed because the `round()` function was rounding UP (e.g., 0.4994 -> 0.50), creating a quantity larger than the available balance before the buffer was even applied.

## Proposed Changes

### 1. Exchange Client Improvements
#### [MODIFY] [binance_client.py](file:///Users/danielsuarezsucre/TRADING/trading_agent/src/nanobot/exchanges/binance_client.py)
- Implement a `truncate_quantity(symbol, qty)` helper that:
    - Uses the predefined precision (2 for SOL, 4 for ETH, 5 for BTC).
    - Uses `math.floor` logic to ensure we never round up.
- Update `market_sell` to:
    - Apply a 0.2% safety buffer (increased from 0.1% to be safer against volatile fee calculations).
    - Use `truncate_quantity` AFTER applying the buffer.

### 4. Automated Redemption & Total Control
#### [MODIFY] [binance_client.py](file:///Users/danielsuarezsucre/TRADING/trading_agent/src/nanobot/exchanges/binance_client.py)
- Implement `redeem_from_savings(asset, qty)` using `self.client.redeem_savings_product(asset, qty, type='FAST')`.
- This ensures the bot can pull assets back to the Spot wallet automatically when needed.

#### [MODIFY] [run_skypie_binance.py](file:///Users/danielsuarezsucre/TRADING/trading_agent/src/scripts/run_skypie_binance.py)
- Update `recover_active_positions` to **automatically trigger redemption** if it detects assets in Flexible Savings (`LDSOL`).
- This makes the recovery "zero-touch" for the user.

### 5. Root Cause Prevention
- **User Action Required**: Provide a step-by-step guide to disable "Auto-Subscribe" in the Binance App.

## Verification Plan

### Automated Tests
- Run `redeem_from_savings` in a controlled test script to verify it moves `LDSOL` to `SOL`.
- Confirm with a balance check that `bal_spot` increases after the call.

### Manual Verification
- Observe the bot logs during the next Scan Cycle. It should show: `🛠️ [AUTO-REDEEM] Moving 0.4768 SOL to Spot wallet... Success`.
- Verify the Take Profit order executes after redemption.
