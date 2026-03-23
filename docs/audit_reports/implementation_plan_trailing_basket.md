# Plan: Dynamic Basket Trailing Protection (Anti-Fuga)

## Problem
The account currently waits for a "Hard" +$5.00 profit. If the market reaches +$3.50 and then reverses, the bot stays open, often turning a gain into a -$5.00 loss (fuga). 

## Proposed Changes
We will implement a **Trailing Buffer** for the basket profit in `run_live.py`:

### [Component] Basket Manager (Axi)
- **Checkpoints**:
  1. **Level 1 (The Hedge)**: If Profit hits **$3.00**, we set a "Floor" at **$1.00**.
  2. **Level 2 (The Lock)**: If Profit hits **$4.00**, we set a "Floor" at **$2.50**.
- **Logic**: If at any time after hitting a checkpoint, the profit falls below the Floor, the bot executes a `close_all_positions()` immediately.

### Files to Modify
#### [MODIFY] [run_live.py](file:///Users/danielsuarezsucre/TRADING/trading_agent/src/scripts/run_live.py)
- Add global variables: `PEAK_BASKET_PNL`.
- Update `check_basket_profit_lock()` to handle the trailing logic.

## Verification Plan
### Automated Verification
- Observe logs for "🛡️ [BASKET TRAIL] Floor set at $1.00".
- Verify that if PnL drops from $3.20 to $0.90, the basket closes automatically.
