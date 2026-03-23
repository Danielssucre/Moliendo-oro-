# Plan to Fix Mega Grid Toggle

The user is unable to disable the "Mega Grid" feature from the dashboard. Research revealed a path mismatch: the dashboard backend uses relative paths (`../../config/trading_config.json`) based on an assumed working directory (`dashboard/backend`), but it is actually running from the project root. This causes it to look for the configuration file in a non-existent parent directory.

## Proposed Changes

### Dashboard Backend
#### [MODIFY] [main.py](file:///Users/danielsuarezsucre/TRADING/trading_agent/dashboard/backend/app/main.py)
- Replace all instances of `os.path.join(os.getcwd(), "../../config/...")` with `os.path.join(PROJECT_ROOT, "config/...")`.
- This ensures the API always writes to and reads from the correct project configuration regardless of where the server process is started.

### Project Configuration
#### [MODIFY] [trading_config.json](file:///Users/danielsuarezsucre/TRADING/trading_agent/config/trading_config.json)
- Explicitly add `"mega_grid_enabled": false` to satisfy the user's request immediately.

## Verification Plan

### Automated Tests
- Restart the dashboard backend and verify that toggling "Mega Grid" in the UI correctly updates the `mega_grid_enabled` field in `config/trading_config.json`.
- Verify that `run_live.py` (the bot) logs "🛡️ [MEGA GRID OFF]" when a signal is detected.

### Manual Verification
- Check the dashboard UI to ensure the button reflect the "OFF" state correctly and persists after refresh.
