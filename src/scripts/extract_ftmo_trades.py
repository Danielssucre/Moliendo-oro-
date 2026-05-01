#!/usr/bin/env python3
"""
NANOBOT TRADE EXTRACTOR
Extrae todos los trades de MT5 con detalles completos para análisis
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)) + "/../../")

from siliconmetatrader5 import MetaTrader5
from datetime import datetime, timedelta, timezone
import pandas as pd
import json
from pathlib import Path


def extract_trades(start_date=None, end_date=None, output_csv=None):
    """Extrae trades de MT5 para un rango de fechas"""

    mt5 = MetaTrader5(port=8001)
    if not mt5.initialize():
        print("❌ MT5 Init Failed")
        sys.exit(1)

    # Default: ultimos 30 dias
    if not end_date:
        end_date = datetime.now()
    if not start_date:
        start_date = end_date - timedelta(days=30)

    print(f"📊 Extrayendo trades: {start_date} -> {end_date}")

    # Get all deals
    deals = mt5.history_deals_get(start_date, end_date)

    if not deals:
        print("No deals found")
        mt5.shutdown()
        return

    trades_data = []
    for d in deals:
        trades_data.append(
            {
                "ticket": d.ticket,
                "time": datetime.fromtimestamp(d.time).strftime("%Y-%m-%d %H:%M:%S"),
                "time_unix": d.time,
                "symbol": d.symbol,
                "type": "BUY" if d.type == 0 else "SELL",
                "entry": d.entry,  # 0=IN, 1=OUT, 2=INOUT
                "volume": d.volume,
                "price": d.price,
                "sl": d.sl,
                "tp": d.tp,
                "commission": d.commission,
                "swap": d.swap,
                "profit": d.profit,
                "comment": d.comment,
                "external_id": d.external_id,
            }
        )

    df = pd.DataFrame(trades_data)

    print(f"\n✅ Total deals: {len(df)}")
    print(f"\n=== PER DATE ===")
    df["date"] = df["time"].str[:10]
    daily = (
        df.groupby("date")
        .agg({"profit": "sum", "ticket": "count"})
        .rename(columns={"ticket": "trades"})
    )
    print(daily)

    print(f"\n=== PER COMMENT (Top 20) ===")
    if "comment" in df.columns:
        comment_stats = (
            df.groupby("comment")
            .agg({"profit": "sum", "ticket": "count"})
            .rename(columns={"ticket": "trades"})
            .sort_values("profit")
        )
        print(comment_stats.head(20))

    print(f"\n=== PER SYMBOL ===")
    symbol_stats = (
        df.groupby("symbol")
        .agg({"profit": "sum", "ticket": "count"})
        .rename(columns={"ticket": "trades"})
        .sort_values("profit", ascending=False)
    )
    print(symbol_stats)

    # Save to CSV
    if output_csv:
        output_path = Path(output_csv)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(output_path, index=False)
        print(f"\n💾 Guardado: {output_path}")

    mt5.shutdown()
    return df


def extract_open_positions():
    """Extrae posiciones abiertas actualmente"""

    mt5 = MetaTrader5(port=8001)
    if not mt5.initialize():
        print("❌ MT5 Init Failed")
        sys.exit(1)

    positions = mt5.positions_get()

    if not positions:
        print("No open positions")
        mt5.shutdown()
        return

    print(f"\n📊 Posiciones ABIERTAS: {len(positions)}")
    print(
        f"{'Ticket':<10} | {'Symbol':<10} | {'Type':<5} | {'Volume':>6} | {'Open':<12} | {'Price':<10} | {'SL':<10} | {'TP':<10} | {'Profit':>10}"
    )
    print("-" * 95)

    total_profit = 0
    for p in positions:
        p_type = "BUY" if p.type == 0 else "SELL"
        t_str = datetime.fromtimestamp(p.time).strftime("%Y-%m-%d %H:%M")
        print(
            f"{p.ticket:<10} | {p.symbol:<10} | {p_type:<5} | {p.volume:>6.2f} | {t_str:<12} | {p.price_open:<10.5f} | {p.sl:<10.5f} | {p.tp:<10.5f} | {p.profit:>10.2f}"
        )
        total_profit += p.profit

    print("-" * 95)
    print(f"Total Open Profit: ${total_profit:.2f}")

    mt5.shutdown()


def extract_last_n_days(n_days=7, output_csv=None):
    """Extrae trades de los ultimos N dias"""

    mt5 = MetaTrader5(port=8001)
    if not mt5.initialize():
        print("❌ MT5 Init Failed")
        sys.exit(1)

    end_date = datetime.now()
    start_date = end_date - timedelta(days=n_days)

    print(f"📊 Extrayendo ultimos {n_days} dias: {start_date} -> {end_date}")

    deals = mt5.history_deals_get(start_date, end_date)

    if not deals:
        print("No deals found")
        mt5.shutdown()
        return

    trades_data = []
    for d in deals:
        trades_data.append(
            {
                "ticket": d.ticket,
                "time": datetime.fromtimestamp(d.time).strftime("%Y-%m-%d %H:%M:%S"),
                "time_unix": d.time,
                "date": datetime.fromtimestamp(d.time).strftime("%Y-%m-%d"),
                "symbol": d.symbol,
                "type": "BUY" if d.type == 0 else "SELL",
                "entry": d.entry,
                "volume": d.volume,
                "price": d.price,
                "sl": d.sl,
                "tp": d.tp,
                "commission": d.commission,
                "swap": d.swap,
                "profit": d.profit,
                "comment": d.comment or "",
            }
        )

    df = pd.DataFrame(trades_data)

    # Save to CSV
    if output_csv:
        output_path = Path(output_csv)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(output_path, index=False)
        print(f"\n💾 Guardado: {output_path}")

    # Summary by date
    print(f"\n=== RESUMEN DIARIO ===")
    daily = (
        df.groupby("date")
        .agg({"profit": "sum", "ticket": "count"})
        .rename(columns={"ticket": "trades"})
    )
    print(daily)

    # Summary by comment
    print(f"\n=== TOP COMMENTS (Profit) ===")
    if "comment" in df.columns:
        comment_stats = (
            df.groupby("comment")
            .agg({"profit": "sum", "ticket": "count"})
            .rename(columns={"ticket": "trades"})
            .sort_values("profit", ascending=False)
            .head(15)
        )
        print(comment_stats)

    # Summary by symbol
    print(f"\n=== TOP SYMBOLS (Profit) ===")
    symbol_stats = (
        df.groupby("symbol")
        .agg({"profit": "sum", "ticket": "count"})
        .rename(columns={"ticket": "trades"})
        .sort_values("profit", ascending=False)
        .head(15)
    )
    print(symbol_stats)

    print(f"\n✅ Total: {len(df)} trades, ${df['profit'].sum():.2f}")

    mt5.shutdown()
    return df


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Extrae trades de MT5")
    parser.add_argument(
        "--days",
        "-d",
        type=int,
        default=0,
        help="Numero de dias hacia atras (default: todos)",
    )
    parser.add_argument("--start", "-s", type=str, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", "-e", type=str, help="End date (YYYY-MM-DD)")
    parser.add_argument("--output", "-o", type=str, help="Output CSV file")
    parser.add_argument(
        "--open", action="store_true", help="Mostrar posiciones abiertas"
    )

    args = parser.parse_args()

    if args.open:
        extract_open_positions()
    elif args.days > 0:
        extract_last_n_days(args.days, args.output)
    else:
        start = datetime.strptime(args.start, "%Y-%m-%d") if args.start else None
        end = datetime.strptime(args.end, "%Y-%m-%d") if args.end else None
        extract_trades(start, end, args.output)
