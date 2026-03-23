# Binance Dashboard Integration Plan

Support monitoring of the new Binance Skypie-Enel bot directly from the central dashboard.

## Proposed Changes

### [Component] Dashboard Backend (FastAPI)

#### [NEW] [binance_service.py](file:///Users/danielsuarezsucre/TRADING/trading_agent/dashboard/backend/app/services/binance_service.py)
- Implement `BinanceService` to bridge the dashboard with `BinanceClient`.
- Methods: `get_stats()` (balances, prices, status), `get_logs()` (last N lines of `skypie_binance.log`).

#### [MODIFY] [schemas.py](file:///Users/danielsuarezsucre/TRADING/trading_agent/dashboard/backend/app/models/schemas.py)
- Add `BinanceStats` model.
- Add `BinancePosition` model.

#### [MODIFY] [main.py](file:///Users/danielsuarezsucre/TRADING/trading_agent/dashboard/backend/app/main.py)
- Initialize `BinanceService`.
- Expose `GET /binance/stats`.
- Expose `GET /binance/logs`.

### [Component] Dashboard Frontend (React + Tailwind)

#### [MODIFY] [App.tsx](file:///Users/danielsuarezsucre/TRADING/trading_agent/dashboard/frontend/src/App.tsx)
- Add "Binance" tab to the main navigation.
- Implement `BinanceView` component:
    - Wallet Summary (USDT, BTC, ETH, SOL).
    - Market Watch (Live Binance prices vs MT5).
    - Active Skypie-Enel Position monitor.
    - Mini Log Viewer for `skypie_binance.log`.

### [Component] Infrastructure

- Install `python-binance` in the dashboard's virtual environment (`.venv`).

## Verification Plan

### Automated Tests
- `curl http://localhost:8000/binance/stats` to verify backend data.

### Manual Verification
- Open Dashboard on browser.
- Click on "Binance" tab.
- Verify that balances and prices match the Telegram/MT5 reports.
- Verify that the log shows active "SCAN CYCLE" entries.
