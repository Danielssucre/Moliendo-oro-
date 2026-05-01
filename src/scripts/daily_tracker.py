#!/usr/bin/env python3
"""
NANOBOT DAILY TRACKER
Guarda el historial completo de trades diariamente
"""

import os
import json
import pandas as pd
from datetime import datetime, timedelta, timezone
from pathlib import Path


def ensure_history_dir():
    """Crea el directorio de historial si no existe"""
    history_dir = Path("logs/history")
    history_dir.mkdir(parents=True, exist_ok=True)
    return history_dir


def save_daily_to_history(daily_stats_path: str = "logs/daily_stats.json"):
    """Guarda los stats del día al historial"""

    history_dir = ensure_history_dir()

    if not os.path.exists(daily_stats_path):
        print(f"No daily stats found at {daily_stats_path}")
        return

    with open(daily_stats_path, "r") as f:
        daily = json.load(f)

    date = daily.get("date", datetime.now().strftime("%Y-%m-%d"))
    history_file = history_dir / f"daily_{date}.json"

    with open(history_file, "w") as f:
        json.dump(daily, f, indent=2)

    print(f"✅ Saved: {history_file}")


def load_history(days: int = 30):
    """Carga el historial de los ultimos N dias"""

    history_dir = ensure_history_dir()

    all_days = []
    for i in range(days):
        date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
        history_file = history_dir / f"daily_{date}.json"

        if history_file.exists():
            with open(history_file, "r") as f:
                all_days.append(json.load(f))

    if not all_days:
        print("No history found")
        return

    df = pd.DataFrame(all_days)

    print(f"\n=== HISTORY ({days} days) ===")
    print(f"Total days: {len(df)}")
    print(f"Date range: {df['date'].min()} to {df['date'].max()}")

    print(f"\n=== DAILY PROFIT ===")
    df["net"] = df["trades_won"] - df["trades_lost"]
    print(
        df[
            [
                "date",
                "trades_won",
                "trades_lost",
                "net",
                "champion_pnl",
                "neme_pnl",
                "crypto_pnl",
            ]
        ].tail(14)
    )

    print(f"\n=== TOTALS ===")
    print(f"Trades won: {df['trades_won'].sum()}")
    print(f"Trades lost: {df['trades_lost'].sum()}")
    print(
        f"Win rate: {df['trades_won'].sum() / (df['trades_won'].sum() + df['trades_lost'].sum()) * 100:.1f}%"
    )
    print(f"Champion P&L: ${df['champion_pnl'].sum():.2f}")
    print(f"Neme P&L: ${df['neme_pnl'].sum():.2f}")
    print(f"Crypto P&L: ${df['crypto_pnl'].sum():.2f}")


def generate_weekly_report():
    """Genera reporte semanal"""

    history_dir = ensure_history_dir()

    all_days = []
    for i in range(7):
        date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
        history_file = history_dir / f"daily_{date}.json"

        if history_file.exists():
            with open(history_file, "r") as f:
                all_days.append(json.load(f))

    if not all_days:
        print("No data for last 7 days")
        return

    df = pd.DataFrame(all_days)

    print(f"\n{'=' * 50}")
    print(f"WEEKLY REPORT ({df['date'].min()} to {df['date'].max()})")
    print(f"{'=' * 50}")

    print(
        f"\n{'Date':<12} | {'W':>4} | {'L':>4} | {'WR%':>6} | {'Champ':>8} | {'Neme':>8} | {'Crypto':>8}"
    )
    print("-" * 70)

    for _, row in df.iterrows():
        wr = (
            row["trades_won"] / (row["trades_won"] + row["trades_lost"]) * 100
            if (row["trades_won"] + row["trades_lost"]) > 0
            else 0
        )
        print(
            f"{row['date']:<12} | {int(row['trades_won']):>4} | {int(row['trades_lost']):>4} | {wr:>5.0f}% | ${row['champion_pnl']:>7.2f} | ${row['neme_pnl']:>7.2f} | ${row['crypto_pnl']:>7.2f}"
        )

    print("-" * 70)
    totals_won = df["trades_won"].sum()
    totals_lost = df["trades_lost"].sum()
    total_wr = (
        totals_won / (totals_won + totals_lost) * 100
        if (totals_won + totals_lost) > 0
        else 0
    )
    print(
        f"{'TOTAL':<12} | {int(totals_won):>4} | {int(totals_lost):>4} | {total_wr:>5.0f}% | ${df['champion_pnl'].sum():>7.2f} | ${df['neme_pnl'].sum():>7.2f} | ${df['crypto_pnl'].sum():>7.2f}"
    )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Nanobot Daily Tracker")
    parser.add_argument(
        "--save", "-s", action="store_true", help="Save today to history"
    )
    parser.add_argument(
        "--history", "-h", type=int, default=0, help="Load history N days"
    )
    parser.add_argument(
        "--report", "-r", action="store_true", help="Generate weekly report"
    )

    args = parser.parse_args()

    if args.save:
        save_daily_to_history()
    elif args.history > 0:
        load_history(args.history)
    elif args.report:
        generate_weekly_report()
    else:
        print("Use --save to save today, --history N for history, --report for weekly")
