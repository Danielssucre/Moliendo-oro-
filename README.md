# 🦖 Nanobot Trading System (v2.0 Clean)

**Institutional-Grade Algorithmic Trading with AI Reinforcement Learning.**

## 📂 Project Structure

```bash
TRADING/trading_agent/
├── src/
│   ├── nanobot/          # Core Logic
│   │   ├── ml/           # Machine Learning (Gatekeeper, StopHunt)
│   │   ├── execution/    # Trade Execution
│   │   └── utils/        # Helpers (Logging, Telegram)
│   └── scripts/          # Entry Points
│       ├── run_live.py   # MAIN RUNNER (Live Trading)
│       └── run_backtest.py
├── config/               # Configuration (JSON/YAML)
├── models/               # Active AI Models (.pth, .joblib)
├── archive/              # Legacy Code (Archived)
└── logs/                 # Trading Logs
```

## 🚀 Quick Start

### 1. Installation
```bash
cd trading_agent
pip install -r requirements.txt
```

### 2. Live Trading
To start the bot in **Manual Signal Mode** (Gatekeeper Shadowed):
```bash
source .venv/bin/activate
python3 src/scripts/run_live.py --capital 100000
```

### 3. Configuration
- **API Keys**: `config/api_keys.json`
- **Trading Params**: `config/trading_config.json`

## 🧠 AI Components
- **Gatekeeper (RL)**: Filters entry signals.
- **Stop Hunt Detector (ML)**: Avoids liquidity traps.
- **Nanobot Supervisor (LLM)**: Provides daily briefings and risk analysis.

---
*Cleaned and Unified - Feb 2026*
