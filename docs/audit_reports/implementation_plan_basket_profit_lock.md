# Implementation Plan: Basket Profit Lock (Axi)

Establish a "Basket Profit Lock" that automatically closes all positions when a combined profit threshold is reached. Includes a Dashboard toggle for manual control.

## User Review Required

> [!IMPORTANT]
> The "Basket Profit Lock" will close ALL open positions on the Axi account when the threshold is met. By default, I will set it to **$5.00** as per our best-case simulation, but you can change it or toggle it OFF from the Dashboard.

## Proposed Changes

### Configuration
#### [NEW] [basket_config.json](file:///Users/danielsuarezsucre/TRADING/trading_agent/config/basket_config.json)
Create a persistent configuration file to store the lock state and threshold.

### Core Logic (Axi)
#### [MODIFY] [run_live.py](file:///Users/danielsuarezsucre/TRADING/trading_agent/src/scripts/run_live.py)
- Add a periodic check within the main trading loop.
- Read `basket_config.json`.
- If `enabled` and `total_pnl >= threshold`, execute a mass-close of all positions.
- Log the event and send a Telegram notification.

### Dashboard Backend
#### [NEW] [basket_lock.py](file:///Users/danielsuarezsucre/TRADING/trading_agent/dashboard/backend/app/api/basket_lock.py)
- Create new API endpoints:
    - `GET /api/basket-lock`: Returns the current config.
    - `POST /api/basket-lock`: Updates the config (toggle ON/OFF, change threshold).
#### [MODIFY] [main.py](file:///Users/danielsuarezsucre/TRADING/trading_agent/dashboard/backend/app/main.py)
- Include the new `basket_lock` router.

### Dashboard Frontend
#### [MODIFY] [App.tsx](file:///Users/danielsuarezsucre/TRADING/trading_agent/dashboard/frontend/src/App.tsx)
- Add a "Security" or "Basket Lock" section.
- Implement a Toggle switch and a threshold input field.
- Connect to the new backend endpoints.

## Verification Plan

### Automated Tests
- Verify `basket_config.json` reading/writing.
- Mock floating PnL in a test script to verify `run_live.py` correctly triggers closure.

### Manual Verification
- Toggle the lock from the Dashboard and verify the file updates on disk.
- Monitor logs during live trading to ensure the closure triggers at the correct profit.
