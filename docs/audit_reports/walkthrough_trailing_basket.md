# Walkthrough: Trailing Basket Protection (Anti-Fuga)

## Problem Identified
The account frequently reached high equity levels (e.g., $39) but failed to hit the fixed $5 basket target, eventually reversing into large drawdowns (e.g., $24). This "all-or-nothing" approach caused significant capital leakage.

## Solution Implemented
Implemented a **Two-Tier Trailing Floor** for the collective basket profit:
1. **Tier 1 (Hedge)**: If Profit reaches **$3.00**, a safety floor is set at **$1.00**.
2. **Tier 2 (Lock)**: If Profit reaches **$4.50**, the safety floor moves up to **$2.50**.

If the market reverses and hits these floors, the bot closes everything immediately to save the partial gain.

## Verification Results
- **Bot Restarted**: PID 14110 (March 23, 10:05 AM).
- **Core Logic Active**: The bot is tracking `CURRENT_BASKET_PEAK` and `CURRENT_BASKET_FLOOR` globally.
- **Initial State**: Bot correctly identified existing NZDUSD exposure and is scanning for synergistic setups.

![Bot Restart Info](/Users/danielsuarezsucre/TRADING/trading_agent/logs/dashboard_bot.log)
> [!IMPORTANT]
> This feature directly stops the "Carousel" from turning winners back into losers. The account should now show more consistent upward steps.
