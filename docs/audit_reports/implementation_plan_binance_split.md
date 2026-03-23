# [Implementation Plan] Tri-Asset Concentrated Allocation (Binance)

Aligning Binance Polimata with the "AXI Equity Logic" by concentrating capital into 3 equal slots ($~20 each) for BTC, ETH, and SOL.

## Proposed Changes

### Core Logic (`run_polimata_binance.py`)
- **Activate BTC**: Add `BTCUSDT` to the `ACTIVE_SYMBOLS` list.
- **Concentrate Capital**: 
    - Set `MAX_SLOTS = 3`.
    - Set `MIN_NOTIONAL = 18.0` (Targeting ~$19-$20 per entry on a $58.50 balance).
- **Slot Recalculation**: Adjust the logic to ensure only 1 slot per asset is active at a time, effectively splitting the account in 3.

### Verification Plan
- **Pre-flight check**: Verify that the new $18+ limit is correctly recognized.
- **Log Audit**: Confirm that `BTCUSDT` entries are being scanned.
- **Balance Sync**: Ensure the total exposure across 3 slots does not exceed balance.

## User Review Required
> [!IMPORTANT]
> **Concentration Risk**: Switching to 3 slots means only 3 trades can be open at once. While this makes each trade "stronger", it means we skip other signals if the slots are full.
> **AXI Sync**: Do you want a "Basket Profit Lock" for Binance as well? (Close all BTC, ETH, SOL if combined profit > X).
