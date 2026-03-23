# Telegram Rate Limit Mitigation

Resolve "Too Many Requests" (HTTP 429) errors by implementing a robust throttling and queuing system for Telegram notifications.

## Proposed Changes

### Core Utilities

#### [MODIFY] [telegram_bot.py](file:///Users/danielsuarezsucre/TRADING/trading_agent/src/nanobot/utils/telegram_bot.py)
- Implement `RateLimiter` logic:
    - Track `last_sent_time`.
    - Enforce a minimum delay (e.g., 2 seconds) between messages to the same chat.
    - Parse `retry_after` from 429 responses and block further attempts for that duration.
- Add `queue_message` method for non-critical updates.

#### [MODIFY] [notificador.py](file:///Users/danielsuarezsucre/TRADING/trading_agent/src/nanobot/utils/notificador.py)
- Refactor to use `TelegramBot` internally or merge logic to avoid redundant implementations.
- Ensure consistent error handling.

### Strategy Runners

#### [MODIFY] [run_skypie_binance.py](file:///Users/danielsuarezsucre/TRADING/trading_agent/src/scripts/run_skypie_binance.py)
- Replace direct `requests.post` with the centralized `TelegramBot` or a throttled version.

## Verification Plan

### Automated Tests
- Run `test_telegram.py` with a loop of 10 rapid messages.
- Verify that the logs show throttling messages ("Waiting X seconds to respect rate limit") instead of HTTP 429 errors.
- Verify that the dashboard log viewer shows the synchronized message flow.
