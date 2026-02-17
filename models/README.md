# Nanobot Models 🧠

This directory contains the active Machine Learning models used by the Nanobot Trading System.

## Active Models

| Model File | Type | Purpose | Module |
|String | String | String | String |
|---|---|---|---|
| `gatekeeper_qnet_v2.pth` | PyTorch (DQN) | **Gatekeeper**: Filters entry signals (HIVE) to prevent bad trades. | `src/nanobot/ml/gatekeeper.py` |
| `stop_hunt_rf_calibrated.joblib` | Scikit-Learn (RandomForest) | **Stop Hunt Detector**: Analyzes price action for liquidity traps. | `src/nanobot/ml/stop_hunt.py` |
| `infinite_rl_qnet_v1.pth` | PyTorch (DQN) | **RL Trailing Manager**: Manages open trades (trailing stop, partial close). | `src/nanobot/ml/rl_trailing.py` |

## Archived Models
Older versions and experiments are moved to `archive/`.

## Missing Files
- `gatekeeper_scaler_v2.json`: Required for Gatekeeper normalization. Currently missing/regenerating.
