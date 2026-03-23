# MT5 Dashboard Enhancements

Extend the Mission Dashboard (MT5) to include detailed logs, active trade information, and history, mirroring the visibility we just implemented for Binance.

## Proposed Changes

### Backend (FastAPI)

#### [MODIFY] [mt5_service.py](file:///Users/danielsuarezsucre/TRADING/trading_agent/dashboard/backend/app/services/mt5_service.py)
- Expand `get_account_stats` to return detailed trade information.
- Implement `get_active_positions()` to fetch live trades from MT5.
- Implement `get_trade_history()` to fetch recent closed trades.
- Implement `get_last_logs()` to read `run_live.log`.

#### [MODIFY] [main.py](file:///Users/danielsuarezsucre/TRADING/trading_agent/dashboard/backend/app/main.py)
- Update `/stats` endpoint to include new data.
- Add `/mt5/logs` endpoint for tailing the Forex logs.

### Frontend (React)

#### [MODIFY] [App.tsx](file:///Users/danielsuarezsucre/TRADING/trading_agent/dashboard/frontend/src/App.tsx)
- Add UI sections for "Active MT5 Positions" and "Recent Trade History".
- Add a "Live Logs" window to the Mission (MT5) tab.
- Update data fetching to populate these new components.

## Verification Plan

### Automated Tests
- Restart dashboard.
- Verify through browser subagent the presence of:
    - Active trades table.
    - History table.
    - Live logs stream.
