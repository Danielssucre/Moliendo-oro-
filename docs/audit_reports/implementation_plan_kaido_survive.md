# Kaido Survive: Low-Cap High-Prob Variant Release

Currently, the Kaido module is disabled for small accounts to avoid over-exposure (4 variants at 1% risk each). This plan introduces "Kaido Survive," a safe version of the monster strategy.

## Proposed Changes

### 1. New Kaido Logic in `run_live.py`
- **[MODIFY] [run_live.py](file:///Users/danielsuarezsucre/TRADING/trading_agent/src/scripts/run_live.py)**:
    - Update the `if (not is_small_cap)` block around line 2455.
    - If `is_small_cap` is True, implement **Kaido Survive**:
        - **Threshold**: Increase probability requirement to > 85% (instead of 75%).
        - **Variant**: Release only ONE variant (`KAIDO_15R`).
        - **Lot Size**: Force **0.01 lots**.
        - **Safety**: Still skip volatile assets (Gold, BTC) via the Small Cap Shield.

### 2. Update Squad Report
- **[MODIFY] [auditoria_forense_axi_estrategica.md](file:///Users/danielsuarezsucre/.gemini/antigravity/brain/5694f615-1d4a-4ec6-a48a-725a8503e59e/auditoria_forense_axi_estrategica.md)**: Move Kaido from "Reserve" to "Active (Survive Version)".

## Verification Plan

### Automated Verification
- Check the syntax of the new `if/else` block.
- Verify `is_small_cap` handling in the `run_live.py` main loop.

### Manual Verification
- Monitor the Axi Dashboard logs for `🐉 [KAIDO SURVIVE] RELEASING` messages when a high-prob signal arrives.
- Verify that only 0.01 lots are used.
