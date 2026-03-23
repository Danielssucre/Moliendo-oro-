# Proposal V2: Progressive Micro-Sizing Protocol

Implement a robust lot-sizing logic for small accounts (specifically those < $500) where standard percentage-based risk management fails due to broker minimums.

## User Review Required

> [!IMPORTANT]
> This protocol adopts a "Safe Stepped Growth" approach instead of dynamic percentage risk for small accounts. 
> - **$0 - $100:** Fixed 0.01 lots (Accepts higher % risk to allow entry).
> - **$100 - $500:** Increments 0.01 lots per $100 of balance ($200=0.02, $300=0.03...).
> - **$500+:** Reverts to standard % risk (e.g., 1%).

## Axi Account Challenge: Grow $27 Account

Address the connection issues and initiate the survival mode trading on the live Axi account.

### Multi-Account Management & Switching
Allows the dashboard to automatically identify saved MT5 accounts and switch between them, including dynamic reconnection and bot restart.

#### [MODIFY] [mt5_service.py](file:///Users/danielsuarezsucre/TRADING/trading_agent/dashboard/backend/app/services/mt5_service.py)
- Add `list_discovered_accounts()` to scan `Bases` directory.
- Update `connect()` to accept optional account parameters.

#### [MODIFY] [main.py](file:///Users/danielsuarezsucre/TRADING/trading_agent/dashboard/backend/app/main.py)
- New endpoint `GET /accounts` to return identified accounts.
- New endpoint `POST /accounts/select` to switch active account.

#### [MODIFY] [App.tsx](file:///Users/danielsuarezsucre/TRADING/trading_agent/dashboard/frontend/src/App.tsx)
- Replace static MT5 input fields with a dynamic account selector/dropdown.
- Show "New Account" option to manually add credentials.

### [MODIFY] [mt5_service.py](file:///Users/danielsuarezsucre/TRADING/trading_agent/dashboard/backend/app/services/mt5_service.py)
- Refine bridge launch logic with guards to prevent zombie processes.
- Add additional logging for initialization and login states.

### [MODIFY] [run_live.py](file:///Users/danielsuarezsucre/TRADING/trading_agent/src/scripts/run_live.py)
- Ensure MT5 connection failure doesn't crash the main loop.
- Implement cleaner retry and logging for the Axi server.

## Verification Plan

### Automated Tests
- Mock account balance at $27, $150, $350, and $1000 and verify calculated lot sizes.
- Use diagnostic scripts to verify connection status and balance retrieval.

### Manual Verification
- Start the bot with the $27 account and verify it picks 0.01 lots.
- Check Dashboard UI for $27 balance and "Axi-US51-Live" server.
