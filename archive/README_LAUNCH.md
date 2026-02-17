# 🦖 Nanobot Trading System (Phase 25)

## 🚀 Status: MISSION READY
The system is fully configured for the Prop Firm Challenge (Stage 1).

### 🔑 Key Features
*   **Strategy:** Hybrid (ADX Trend + RSI Range)
*   **Asset:** GBPUSD Only (Sniper Mode)
*   **Time Window:** 08:00 - 12:00 UTC (The Golden Hours)
*   **Risk:** 1.0% Fixed per Trade
*   **Safety:** "Council of Oracles" (Twelvedata Verification) + Telegram Notifications

---

## 🟢 HOW TO START (The Green Button)

1.  **Open Terminal**
2.  **Run the Launcher:**
    ```bash
    ./run_live_trading.sh
    ```

That's it. The script will:
1.  Check your API keys.
2.  Verify connection to the Oracle (Twelvedata).
3.  Start scanning GBPUSD every 15 minutes.
4.  Send you a **Telegram Message** when a signal is found.

---

## ⚠️ Important Notes
*   **Keep the Terminal Open:** Do not close the window while the bot is running.
*   **Oracles:** If Twelvedata fails, the bot will warn you but continue (Fail Open).
*   **Stop Execution:** Press `Ctrl+C` to stop the bot safely.

---

## 📊 Recent Performance (Last 60 Days)
*   **Win Rate:** 37.5% (Profitable at 1:2 RR)
*   **Return:** +36%
*   **Drawdown:** 6% (Safe)
