# Dashboard & Notification Stabilization

This plan addresses the current disconnect between the dashboard controls and the live trading bot's survival state, while also fixing the silent failure of Telegram notifications.

## Proposed Changes

### 1. Unified Project Root Pathing
- **[MODIFY] [logger.py](file:///Users/danielsuarezsucre/TRADING/trading_agent/src/nanobot/utils/logger.py)**: Update `log_dir` calculation to go 4 levels up to the project root, ensuring it finds the correct `logs/` directory.
- **[MODIFY] [config.py](file:///Users/danielsuarezsucre/TRADING/trading_agent/src/nanobot/utils/config.py)**: Ensure redundant pathing logic is consistent with the logger.

### 2. Dashboard Dynamic Capital Start
- **[MODIFY] [main.py](file:///Users/danielsuarezsucre/TRADING/trading_agent/dashboard/backend/app/main.py)**: Update the `/start` endpoint to:
    1. Fetch current account balance via `mt5_service.get_account_stats()`.
    2. Fallback to 100,000 only if the account is empty or disconnected.
    3. Pass the real balance to `bot_manager.start_bot(capital=balance)`.

### 3. Telegram Notification Restoration
- **Verification**: Once pathing is unified, `api_keys.json` will be consistently loaded.
- **Bot Restart**: Restart both `run_live.py` (Axi) and `run_polimata_binance.py` (Binance) to pick up the correct configuration.

## Verification Plan

### Automated Tests
- Run `python3 /tmp/test_telegram.py` after pathing changes to confirm it still works.
- Check `logs/dashboard_bot.log` for the "✅ Telegram Bot Configured." message.

### Manual Verification
- Click **"START BOT"** in the dashboard and verify in the terminal (`ps aux`) that the `--capital` argument reflects the real balance ($22).
- Verify that a Telegram message "*POLIMATA BINANCE CORE IS ONLINE*" is received.
