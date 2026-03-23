# Proposal: Axi Account Challenge Connection Fix

Address the "IPC timeout" and "result expired" issues preventing the trading bot from connecting to the live Axi balance ($27).

## User Review Required

> [!WARNING]
> Connection to "Axi-US51-Live" may fail if the MT5 terminal does not have the server definitions. 
> I will attempt to force a server scan or provide a manual configuration.

## Proposed Changes

### Dashboard Backend

#### [MODIFY] [mt5_service.py](file:///Users/danielsuarezsucre/TRADING/trading_agent/dashboard/backend/app/services/mt5_service.py)
- Refine bridge launch logic to prevent zombie processes.
- Add additional logging for initialization timeouts.

### Trading Engine

#### [MODIFY] [run_live.py](file:///Users/danielsuarezsucre/TRADING/trading_agent/src/scripts/run_live.py)
- Ensure MT5 connection failure doesn't crash the main loop before it can log the error.
- Implement a cleaner retry mechanism for the Axi server.

## Verification Plan

### Automated Tests
- Use `/tmp/test_mt5_connect.py` to verify connection outside the main engine.
- Check dashboard `/stats` endpoint for $27 balance.

### Manual Verification
- Restart the bot and verify the startup message shows the correct Axi account details.
