# 🦖 Nanobot - Institutional Trading System

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: Private](https://img.shields.io/badge/license-Private-red.svg)](LICENSE)
[![FTMO Compliant](https://img.shields.io/badge/FTMO-Compliant-green.svg)](docs/validation.md)

> **Algorithmic trading system with AI-powered risk management, probabilistic calibration, and institutional-grade capital allocation.**

---

## 🎯 Overview

Nanobot is a sophisticated trading bot designed for FTMO and prop firm environments, featuring:

- **🧠 AI Risk Assessment**: Gemini-powered market analysis and dynamic risk adjustment
- **⚖️ Fractional Kelly Sizing**: Mathematically optimal position sizing with SE shrinkage
- **🔬 Calibrated ML**: Isotonic-calibrated Random Forest for stop-hunt detection
- **🛡️ Multi-Layer Protection**: Circuit breakers, dynamic overlays, and trade guardians
- **📊 FTMO-Grade Validation**: Block bootstrap stress testing (Convexity Ratio: 3.15)

---

## 🏗️ Architecture

```
trading_agent/
├── src/
│   ├── probability/          # Kelly sizing, Bayesian engines
│   ├── ml/                   # Stop-hunt detection models
│   ├── nanobot/              # AI supervisor, risk assessment
│   └── utils/                # Telegram, logging, helpers
├── scripts/
│   ├── run_ftmo_manual.py    # Main trading loop
│   ├── experimental/         # Monte Carlo validation
│   └── *.sh                  # Launch scripts
├── models/                   # ML models (excluded from git)
├── config/                   # Configuration (credentials excluded)
└── brain/                    # Documentation, operation manual
```

---

## 🚀 Quick Start

### Prerequisites

- Python 3.10+
- MetaTrader 5 (for live trading)
- API Keys: Gemini AI, Telegram Bot

### Installation

```bash
# 1. Clone the repository
git clone https://github.com/Danielssucre/Moliendo-oro.git
cd Moliendo-oro

# 2. Create virtual environment
python3 -m venv .venv
source .venv/bin/activate  # macOS/Linux
# .venv\Scripts\activate   # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure credentials
cp .env.example .env
# Edit .env with your API keys

# 5. Train ML models (first run only)
python scripts/experimental/retrain_calibrated.py

# 6. Launch bot
./run_live_trading.sh 10000  # $10,000 initial capital
```

---

## ⚙️ Configuration

### Environment Variables

Create a `.env` file based on `.env.example`:

```bash
# API Keys
GEMINI_API_KEY=your_gemini_key_here
TELEGRAM_BOT_TOKEN=your_telegram_token_here
TELEGRAM_CHAT_ID=your_chat_id_here

# Trading Parameters
INITIAL_CAPITAL=10000
RISK_PER_TRADE=0.004  # 0.4%
KELLY_FRACTION=0.25   # Fractional Kelly
```

### Trading Pairs

Edit `ASSET_MAP` in `run_ftmo_manual.py` to customize pairs:
```python
ASSET_MAP = {
    "AUDUSD": "AUDUSD",
    "GBPJPY": "GBPJPY",
    # ... add your pairs
}
```

---

## 📊 Risk Management

Nanobot implements multiple layers of protection:

1. **Fractional Kelly (0.25x)**: Position sizing based on mathematical edge
2. **SE Shrinkage**: Dynamic adjustment for probability uncertainty
3. **Circuit Breakers**: Auto-halt on 2% daily loss
4. **Risk Overlay**: 50% reduction if drawdown > 3%
5. **ML Filtering**: Skip trades with high stop-hunt probability (>0.75)

---

## 🧪 Validation & Backtesting

Run Monte Carlo stress tests:

```bash
python scripts/experimental/monte_carlo_sizing.py
```

Results (Phase 22D):
- **Convexity Ratio**: 3.15 (Kelly 0.25x vs fixed risk)
- **P99 Max DD**: -8.29% (FTMO-compliant)
- **Brier Score**: 0.101 (calibrated)

---

## 📝 Key Features

### Phase 22A: Probabilistic Calibration
- Isotonic calibration of Random Forest
- Brier Score improvement: 0.165 → 0.101
- Expected Calibration Error (ECE) correction

### Phase 22C: Institutional Kelly
- Standard Error-based shrinkage
- Strict skip policy (f* ≤ 0)
- Hard cap at 2.5x multiplier

### Phase 22D: Stress Testing
- Block bootstrap (10-trade blocks)
- Edge erosion scenarios
- Probability bias sensitivity analysis

---

## 🛡️ Security

⚠️ **CRITICAL**: This repository does NOT contain:
- API keys or credentials
- Live trading logs
- Trained ML models (regenerate locally)

**Best Practices**:
1. Never commit `.env` or `config/credentials.json`
2. Use environment variables for secrets
3. Regenerate models locally: `python scripts/experimental/retrain_calibrated.py`

---

## 📚 Documentation

- [Operation Manual](brain/manual_operativo_bot.md)
- [Phase 22 Walkthrough](walkthrough.md)
- [Implementation Plan](implementation_plan.md)

---

## 🤝 Contributing

This is a private repository. For collaboration:

1. Request access from repository owner
2. Create feature branches: `git checkout -b feature/your-feature`
3. Test thoroughly before merging
4. Update documentation

---

## 📜 License

**Private & Confidential** - All rights reserved.

This software is proprietary and confidential. Unauthorized copying, distribution, or use is strictly prohibited.

---

## ⚠️ Disclaimer

Trading involves substantial risk of loss. This software is provided "as is" without warranty. Use at your own risk. Past performance does not guarantee future results.

---

## 📞 Contact

For questions or support, contact the repository owner.

---

**Built with 🧠 by the Nanobot Team | Powered by Gemini AI & Silicon MT5**
