# Axi Small Capital Profile Deployment ($27)

Implement a high-safety execution profile for small accounts to ensure survival and gradual growth through extreme selectivity.

## Proposed Changes

### [MT5 Bot Runner]
#### [MODIFY] [run_live.py](file:///Users/danielsuarezsucre/TRADING/trading_agent/src/scripts/run_live.py)
- **High Selectivity Filter**: Increase the Polimata/Sniper probability threshold to **75%** (from current ~65/70%).
- **Strategy Lock**: Explicitly enable `HunterX` and `Chameleon2.0` while ensuring `Kaido` and `Mega Grid` are in Shadow Mode for this account.
- **Risk Floor Calibration**: Ensure the sizing logic remains at 0.01 but includes the `HARD FUSE` safety net at 5% daily.
- **Exposure Cap**: Tighten currency exposure to avoid correlated losses in such a small account.

## Verification Plan

### Automated Tests
- Run `run_live.py` in test mode to verify that it skips signals below 75% probability.
- Check logs for the `[SNIPER]` rejection message on 60-70% probability signals.

### Manual Verification
- Monitor the Axi Account `60220215` in the dashboard to ensure only "Elite" setups are triggering orders.
