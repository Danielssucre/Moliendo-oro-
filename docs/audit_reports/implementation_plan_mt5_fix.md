# MT5 Axi Connection Fix

The bot currently fails to retrieve account info from the Axi MT5 account despite showing a "Verified" connection. This is due to a port mismatch: the working bridge is on port **18812**, but many modules are hardcoded to port **8001**.

## Proposed Changes

### [MT5 Bridge Configuration]

#### [MODIFY] [run_live.py](file:///Users/danielsuarezsucre/TRADING/trading_agent/src/scripts/run_live.py)
- Ensure the `MT5ConnectionManager` consistently uses port **18812**.
- Improve error reporting when `account_info()` returns `None`.

#### [MODIFY] [mt5_data.py](file:///Users/danielsuarezsucre/TRADING/trading_agent/src/nanobot/utils/mt5_data.py)
- Change default port from **8001** to **18812** to match the active bridge.

### [Verification Plan]

#### Automated Tests
- Run the standalone test script `test_axi_connection.py` once more.
- Start `run_live.py` and verify the "🍏 MT5 CONNECTED" message is followed by successful account info retrieval (Balance: $27.0).

#### Manual Verification
- Check the console output for the "📊 Account Info Received" log.
