#!/usr/bin/env python3
"""
Backtest: Multi-TF Zone Reversal Strategy
==========================================
Testea la estrategia de escalación H1→M15→M5 para detectar agotamiento.
"""

import pandas as pd
import numpy as np
from datetime import datetime
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate RSI, ADX, Bollinger Bands, EMA."""
    df = df.copy()

    close = df["close"]

    delta = close.diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss.replace(0, 1e-10)
    df["rsi"] = 100 - (100 / (1 + rs))

    df["sma20"] = close.rolling(20).mean()
    df["std20"] = close.rolling(20).std()
    df["bb_upper"] = df["sma20"] + 2 * df["std20"]
    df["bb_lower"] = df["sma20"] - 2 * df["std20"]
    df["bb_distance"] = (close - df["sma20"]) / df["std20"].replace(0, 1e-10)

    df["ema8"] = close.ewm(span=8, adjust=False).mean()
    df["ema21"] = close.ewm(span=21, adjust=False).mean()
    df["ema_fast_above"] = df["ema8"] > df["ema21"]
    df["ema_cross_up"] = df["ema_fast_above"] & (
        ~df["ema_fast_above"].shift(1).fillna(False)
    )
    df["ema_cross_down"] = (~df["ema_fast_above"]) & (
        df["ema_fast_above"].shift(1).fillna(False)
    )

    high_low = df["high"] - df["low"]
    high_close = abs(df["high"] - close.shift())
    low_close = abs(df["low"] - close.shift())
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df["atr"] = tr.rolling(14).mean()
    df["atr_pct"] = df["atr"] / close * 100

    high_ = df["high"]
    low_ = df["low"]
    close_ = df["close"]
    plus_dm = high_.diff()
    minus_dm = -low_.diff()
    plus_dm[plus_dm < 0] = 0
    minus_dm[minus_dm < 0] = 0

    tr14 = tr.rolling(14).mean()
    plus_di = 100 * (plus_dm.rolling(14).mean() / tr14)
    minus_di = 100 * (minus_dm.rolling(14).mean() / tr14)
    dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
    df["adx"] = dx.rolling(14).mean()

    return df


def resample_tf(df: pd.DataFrame, tf: str) -> pd.DataFrame:
    """Resample M5 to higher timeframe."""
    df = df.copy()
    df["time"] = pd.to_datetime(df["time"])
    df.set_index("time", inplace=True)

    rule = {"M15": "15min", "H1": "1h", "H4": "4h", "D1": "1d"}[tf]

    resampled = pd.DataFrame()
    resampled["open"] = df["open"].resample(rule).first()
    resampled["high"] = df["high"].resample(rule).max()
    resampled["low"] = df["low"].resample(rule).min()
    resampled["close"] = df["close"].resample(rule).last()
    resampled = resampled.dropna()
    resampled = calculate_indicators(resampled)
    resampled = resampled.reset_index()
    resampled = resampled.rename(columns={"time": "time"})

    return resampled


def simulate_trades(
    df_h1: pd.DataFrame,
    df_m15: pd.DataFrame,
    df_m5: pd.DataFrame,
    symbol: str,
    use_ema_confirm: bool = True,
) -> list:
    """Simulate Multi-TF momentum continuation trades."""
    trades = []

    RSI_BULL_THRESH = 55
    RSI_BEAR_THRESH = 45
    ADX_STRONG = 22

    SL_PIPS = 15
    TP_PIPS = 30

    pip_size = 0.0001 if "JPY" not in symbol else 0.01

    for i in range(100, len(df_h1)):
        h1 = df_h1.iloc[i]
        h1_time = h1["time"]

        rsi_h1 = h1["rsi"]
        adx_h1 = h1["adx"]
        close_h1 = h1["close"]

        direction = 0

        if rsi_h1 > RSI_BULL_THRESH and adx_h1 > ADX_STRONG:
            direction = 1
        elif rsi_h1 < RSI_BEAR_THRESH and adx_h1 > ADX_STRONG:
            direction = -1

        if direction == 0:
            continue

        m15_idx = df_m15[df_m15["time"] >= h1_time].index
        if len(m15_idx) == 0:
            continue
        m15_pos = m15_idx[0]

        m15_confirmed = False
        for j in range(m15_pos, min(m15_pos + 4, len(df_m15))):
            m15 = df_m15.iloc[j]
            rsi_m15 = m15["rsi"]

            if direction == 1 and rsi_m15 > RSI_BULL_THRESH:
                m15_confirmed = True
                break
            elif direction == -1 and rsi_m15 < RSI_BEAR_THRESH:
                m15_confirmed = True
                break

        if not m15_confirmed:
            continue

        m5_idx = df_m5[df_m5["time"] >= h1_time].index
        if len(m5_idx) == 0:
            continue
        m5_pos = m5_idx[0]

        entry_price = None
        entry_time = None

        for k in range(m5_pos, min(m5_pos + 12, len(df_m5))):
            m5 = df_m5.iloc[k]
            rsi_m5 = m5["rsi"]
            close_m5 = m5["close"]
            ema_cross_up = m5.get("ema_cross_up", False)
            ema_cross_down = m5.get("ema_cross_down", False)

            if use_ema_confirm:
                if direction == 1 and ema_cross_up:
                    entry_price = close_m5
                    entry_time = m5["time"]
                    break
                elif direction == -1 and ema_cross_down:
                    entry_price = close_m5
                    entry_time = m5["time"]
                    break
            else:
                if direction == 1 and rsi_m5 > RSI_BULL_THRESH:
                    entry_price = close_m5
                    entry_time = m5["time"]
                    break
                elif direction == -1 and rsi_m5 < RSI_BEAR_THRESH:
                    entry_price = close_m5
                    entry_time = m5["time"]
                    break

        if entry_price is None:
            continue

        sl_price = entry_price - (SL_PIPS * pip_size * direction)
        tp_price = entry_price + (TP_PIPS * pip_size * direction)

        result = "OPEN"
        exit_price = None
        exit_time = None

        for k_idx in range(m5_pos + 1, len(df_m5)):
            m5_candle = df_m5.iloc[k_idx]
            high_m5 = m5_candle["high"]
            low_m5 = m5_candle["low"]

            if direction == 1:
                if low_m5 <= sl_price:
                    result = "LOSS"
                    exit_price = sl_price
                    exit_time = m5_candle["time"]
                    break
                elif high_m5 >= tp_price:
                    result = "WIN"
                    exit_price = tp_price
                    exit_time = m5_candle["time"]
                    break
            else:
                if high_m5 >= sl_price:
                    result = "LOSS"
                    exit_price = sl_price
                    exit_time = m5_candle["time"]
                    break
                elif low_m5 <= tp_price:
                    result = "WIN"
                    exit_price = tp_price
                    exit_time = m5_candle["time"]
                    break

        if result == "OPEN":
            final_candle = df_m5.iloc[-1]
            exit_price = final_candle["close"]
            exit_time = final_candle["time"]
            pnl_pips = (exit_price - entry_price) / pip_size * direction
            result = "WIN" if pnl_pips > 0 else "LOSS"
        else:
            pnl_pips = (
                (exit_price - entry_price) / pip_size * direction if exit_price else 0
            )

        trades.append(
            {
                "symbol": symbol,
                "direction": "BUY" if direction == 1 else "SELL",
                "entry_time": entry_time,
                "entry_price": entry_price,
                "exit_time": exit_time,
                "exit_price": exit_price,
                "sl_pips": SL_PIPS,
                "tp_pips": TP_PIPS,
                "pnl_pips": pnl_pips,
                "result": result,
                "rsi_h1": rsi_h1,
                "rsi_m15": df_m15.iloc[m15_pos]["rsi"],
                "rsi_m5": df_m5.iloc[m5_pos]["rsi"],
                "adx_h1": adx_h1,
                "ema_confirm": use_ema_confirm if "use_ema_confirm" in dir() else False,
            }
        )

    return trades


def run_strategy(symbols, use_ema: bool, base_path: str) -> pd.DataFrame:
    """Run strategy with or without EMA confirmation."""
    all_trades = []

    for symbol in symbols:
        csv_path = f"{base_path}/MT5_5M_{symbol}_Training_Dataset.csv"
        if not os.path.exists(csv_path):
            continue

        try:
            df_m5 = pd.read_csv(csv_path)
            df_m5.columns = [
                "time",
                "open",
                "high",
                "low",
                "close",
                "tick_volume",
                "spread",
                "real_volume",
            ]
            df_m5["time"] = pd.to_datetime(df_m5["time"])
            df_m5 = calculate_indicators(df_m5)

            df_h1 = resample_tf(df_m5, "H1")
            df_m15 = resample_tf(df_m5, "M15")

            trades = simulate_trades(
                df_h1, df_m15, df_m5, symbol, use_ema_confirm=use_ema
            )
            all_trades.extend(trades)

        except Exception as e:
            continue

    return pd.DataFrame(all_trades)


def analyze_results(trades_df: pd.DataFrame) -> dict:
    """Analyze trading results."""
    if trades_df.empty:
        return {}

    wins = len(trades_df[trades_df["result"] == "WIN"])
    losses = len(trades_df[trades_df["result"] == "LOSS"])
    total = len(trades_df)
    wr = (wins / total * 100) if total > 0 else 0

    avg_win = (
        trades_df[trades_df["result"] == "WIN"]["pnl_pips"].mean() if wins > 0 else 0
    )
    avg_loss = (
        trades_df[trades_df["result"] == "LOSS"]["pnl_pips"].mean() if losses > 0 else 0
    )

    total_pnl = trades_df["pnl_pips"].sum()
    rr_ratio = abs(avg_win / avg_loss) if avg_loss != 0 else 0
    expectancy = (wr / 100) * avg_win - (1 - wr / 100) * abs(avg_loss)

    return {
        "total": total,
        "wins": wins,
        "losses": losses,
        "wr": wr,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "total_pnl": total_pnl,
        "rr_ratio": rr_ratio,
        "expectancy": expectancy,
    }


def main():
    print("=" * 70)
    print("MULTI-TF BACKTEST: RSI+ADX vs RSI+ADX+EMA CROSSOVER")
    print("=" * 70)

    base_path = "/Users/danielsuarezsucre/TRADING/trading_agent/data/historical"

    symbols = [
        "EURUSD",
        "GBPUSD",
        "USDJPY",
        "GBPJPY",
        "EURJPY",
        "AUDUSD",
        "USDCAD",
        "EURGBP",
        "AUDJPY",
    ]

    print("\n[1/2] Running WITHOUT EMA crossover (baseline)...")
    df_baseline = run_strategy(symbols, use_ema=False, base_path=base_path)

    print("[2/2] Running WITH EMA crossover confirmation...")
    df_ema = run_strategy(symbols, use_ema=True, base_path=base_path)

    baseline = analyze_results(df_baseline)
    ema_results = analyze_results(df_ema)

    print("\n" + "=" * 70)
    print("COMPARISON RESULTS")
    print("=" * 70)
    print(f"{'Metric':<20} {'Baseline':>15} {'+EMA Crossover':>18} {'Change':>12}")
    print("-" * 70)
    print(
        f"{'Total Trades':<20} {baseline['total']:>15} {ema_results['total']:>18} {ema_results['total'] - baseline['total']:>+12}"
    )
    print(
        f"{'Win Rate':<20} {baseline['wr']:>14.1f}% {ema_results['wr']:>17.1f}% {ema_results['wr'] - baseline['wr']:>+11.1f}%"
    )
    print(
        f"{'Avg Win (pips)':<20} {baseline['avg_win']:>15.1f} {ema_results['avg_win']:>18.1f} {ema_results['avg_win'] - baseline['avg_win']:>+12.1f}"
    )
    print(
        f"{'Avg Loss (pips)':<20} {baseline['avg_loss']:>15.1f} {ema_results['avg_loss']:>18.1f} {ema_results['avg_loss'] - baseline['avg_loss']:>+12.1f}"
    )
    print(
        f"{'Total PnL':<20} {baseline['total_pnl']:>15.1f} {ema_results['total_pnl']:>18.1f} {ema_results['total_pnl'] - baseline['total_pnl']:>+12.1f}"
    )
    print(
        f"{'R:R Ratio':<20} {'1:' + str(round(baseline['rr_ratio'], 2)):>15} {'1:' + str(round(ema_results['rr_ratio'], 2)):>18} {'':>12}"
    )
    print(
        f"{'Expectancy/trade':<20} {baseline['expectancy']:>15.2f} {ema_results['expectancy']:>18.2f} {ema_results['expectancy'] - baseline['expectancy']:>+12.2f}"
    )
    print("-" * 70)

    trades_reduction = (
        (baseline["total"] - ema_results["total"]) / baseline["total"] * 100
        if baseline["total"] > 0
        else 0
    )
    wr_improvement = ema_results["wr"] - baseline["wr"]

    print(f"\n{'=' * 70}")
    print("ANALYSIS")
    print("=" * 70)
    print(f"  Trades reduced by EMA:    {trades_reduction:.1f}%")
    print(f"  WR improvement:            {wr_improvement:+.1f}%")
    print(
        f"  PnL change:               {ema_results['total_pnl'] - baseline['total_pnl']:+.1f} pips"
    )

    print(f"\n{'=' * 70}")
    print("CONCLUSION")
    print("=" * 70)

    if ema_results["expectancy"] > baseline["expectancy"] and wr_improvement > 0:
        print("✓ EMA CROSSOVER IMPROVES THE STRATEGY")
        print(
            f"  Higher WR (+{wr_improvement:.1f}%) and better expectancy (+{ema_results['expectancy'] - baseline['expectancy']:.2f})"
        )
        if ema_results["total_pnl"] > 0:
            print("  ✓ POSITIVE EXPECTANCY MAINTAINED")
    elif ema_results["wr"] > baseline["wr"] and ema_results["total_pnl"] > 0:
        print("~ EMA CROSSOVER REDUCES TRADES BUT MAINTAINS QUALITY")
        print(
            f"  Less trades ({ema_results['total']} vs {baseline['total']}) but better quality ({wr_improvement:+.1f}% WR)"
        )
    elif ema_results["total_pnl"] > baseline["total_pnl"]:
        print("✓ EMA CROSSOVER IMPROVES TOTAL PNL")
        print(
            f"  PnL increased by {ema_results['total_pnl'] - baseline['total_pnl']:.1f} pips despite fewer trades"
        )
    else:
        print("✗ EMA CROSSOVER DOES NOT IMPROVE THE STRATEGY")
        print("  Consider other confirmations or use baseline strategy")

    df_ema.to_csv(
        "/Users/danielsuarezsucre/TRADING/trading_agent/data/backtest_ema_results.csv",
        index=False,
    )
    print(f"\n  Results saved to: backtest_ema_results.csv")


if __name__ == "__main__":
    main()
