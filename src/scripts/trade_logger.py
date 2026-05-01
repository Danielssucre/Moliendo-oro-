#!/usr/bin/env python3
"""
NANOBOT TRADE LOGGER v2.0
Sistema centralizado para registrar TODOS los trades de MT5 con detalles completos
"""

import os
import json
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class TradeLogger:
    """Sistema centralizado de logging para trades"""

    def __init__(self, log_dir: str = "data/trades"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

        self.daily_log = self.log_dir / "daily_trades.csv"
        self.strategy_log = self.log_dir / "strategy_trades.csv"
        self.symbol_log = self.log_dir / "symbol_trades.csv"

        self._init_logs()

    def _init_logs(self):
        """Inicializa archivos de log si no existen"""

        # Daily trades log
        if not self.daily_log.exists():
            with open(self.daily_log, "w") as f:
                f.write(
                    "timestamp,symbol,type,volume,entry_price,sl,tp,profit,commission,swap,comment,ticket,exit_price,duration_hours, session\n"
                )

        # Strategy log
        if not self.strategy_log.exists():
            with open(self.strategy_log, "w") as f:
                f.write(
                    "timestamp,symbol,strategy,config,probability,adx,rsi,atr,volume,entry_price,sl,tp,profit,result_r,session\n"
                )

        # Symbol log
        if not self.symbol_log.exists():
            with open(self.symbol_log, "w") as f:
                f.write(
                    "date,symbol,wins,losses,total_profit,total_trades,win_rate,avg_win,avg_loss\n"
                )

    def log_trade(self, trade_data: Dict):
        """Loggea un trade individual"""
        try:
            timestamp = trade_data.get("timestamp", datetime.now().isoformat())

            # Daily log
            with open(self.daily_log, "a") as f:
                f.write(
                    f"{timestamp},{trade_data.get('symbol', '')},{trade_data.get('type', '')},"
                    f"{trade_data.get('volume', 0)},{trade_data.get('entry_price', 0)},{trade_data.get('sl', 0)},{trade_data.get('tp', 0)},"
                    f"{trade_data.get('profit', 0)},{trade_data.get('commission', 0)},{trade_data.get('swap', 0)},"
                    f"{trade_data.get('comment', '')},{trade_data.get('ticket', 0)},{trade_data.get('exit_price', 0)},"
                    f"{trade_data.get('duration_hours', 0)},{trade_data.get('session', '')}\n"
                )

            # Strategy log
            if "strategy" in trade_data:
                with open(self.strategy_log, "a") as f:
                    f.write(
                        f"{timestamp},{trade_data.get('symbol', '')},{trade_data.get('strategy', '')},{trade_data.get('config', '')},"
                        f"{trade_data.get('probability', 0)},{trade_data.get('adx', 0)},{trade_data.get('rsi', 0)},{trade_data.get('atr', 0)},"
                        f"{trade_data.get('volume', 0)},{trade_data.get('entry_price', 0)},{trade_data.get('sl', 0)},{trade_data.get('tp', 0)},"
                        f"{trade_data.get('profit', 0)},{trade_data.get('result_r', 0)},{trade_data.get('session', '')}\n"
                    )

            logger.info(
                f"📝 Logged trade: {trade_data.get('symbol')} {trade_data.get('ticket')} ${trade_data.get('profit', 0):.2f}"
            )

        except Exception as e:
            logger.error(f"❌ Error logging trade: {e}")

    def log_batch(self, trades: List[Dict]):
        """Loggea un batch de trades"""
        for trade in trades:
            self.log_trade(trade)

    def log_from_mt5_deal(self, deal):
        """Convierte un deal de MT5 a formato de log"""
        trade_data = {
            "timestamp": datetime.fromtimestamp(deal.time).isoformat(),
            "symbol": deal.symbol,
            "type": "BUY" if deal.type == 0 else "SELL",
            "volume": deal.volume,
            "entry_price": deal.price,
            "sl": deal.sl,
            "tp": deal.tp,
            "profit": deal.profit,
            "commission": deal.commission,
            "swap": deal.swap,
            "comment": deal.comment,
            "ticket": deal.ticket,
            "exit_price": deal.price,
            "duration_hours": 0,
            "session": "",
        }

        # Extract strategy from comment
        comment = deal.comment or ""
        if "NEMESIS" in comment.upper():
            trade_data["strategy"] = "NEMESIS"
            if "_S" in comment:
                trade_data["config"] = "SNIPER"
            elif "_B" in comment:
                trade_data["config"] = "BASE"
            elif "_H" in comment:
                trade_data["config"] = "HARVEST"
            else:
                trade_data["config"] = "NORMAL"
        elif "CHAM" in comment.upper() or "ALFA" in comment.upper():
            trade_data["strategy"] = "CHAMeleon"
            trade_data["config"] = comment
        elif "IRON" in comment.upper():
            trade_data["strategy"] = "IRON_SHIELD"
            trade_data["config"] = comment
        else:
            trade_data["strategy"] = "UNKNOWN"
            trade_data["config"] = comment

        self.log_trade(trade_data)

    def generate_daily_summary(self, date: str = None):
        """Genera resumen diario"""
        if not self.daily_log.exists():
            print("No trades logged yet")
            return

        df = pd.read_csv(self.daily_log)

        if date:
            df = df[df["timestamp"].str.startswith(date)]

        print(f"\n=== DAILY SUMMARY {'(' + date + ')' if date else ''} ===")
        print(f"Total trades: {len(df)}")
        print(f"Profit: ${df['profit'].sum():.2f}")

        # By symbol
        print(f"\n=== BY SYMBOL ===")
        by_symbol = (
            df.groupby("symbol")
            .agg({"profit": "sum", "ticket": "count"})
            .rename(columns={"ticket": "trades"})
            .sort_values("profit", ascending=False)
        )
        print(by_symbol)

        # By strategy
        print(f"\n=== BY COMMENT ===")
        by_comment = (
            df.groupby("comment")
            .agg({"profit": "sum", "ticket": "count"})
            .rename(columns={"ticket": "trades"})
            .sort_values("profit", ascending=False)
            .head(20)
        )
        print(by_comment)

    def generate_strategy_report(self):
        """Genera reporte por estrategia"""
        if not self.strategy_log.exists():
            print("No strategy trades logged")
            return

        df = pd.read_csv(self.strategy_log)

        print(f"\n=== STRATEGY REPORT ===")

        # By strategy
        by_strategy = df.groupby("strategy").agg(
            {"profit": ["sum", "count", "mean"], "result_r": "mean"}
        )
        print(by_strategy)

        # By config
        print(f"\n=== BY CONFIG ===")
        by_config = (
            df.groupby("config")
            .agg({"profit": ["sum", "count"], "result_r": "mean"})
            .sort_values(("profit", "sum"), ascending=False)
            .head(20)
        )
        print(by_config)


def sync_from_mt5(days_back: int = 7):
    """Sincroniza trades desde MT5"""
    try:
        from siliconmetatrader5 import MetaTrader5
    except ImportError:
        print("❌ SiliconMT5 not available")
        return

    mt5 = MetaTrader5(port=8001)
    if not mt5.initialize():
        print("❌ MT5 connection failed")
        return

    logger = TradeLogger()

    end_date = datetime.now()
    start_date = end_date - timedelta(days=days_back)

    deals = mt5.history_deals_get(start_date, end_date)

    if not deals:
        print("No deals found")
        mt5.shutdown()
        return

    print(f"📊 Syncing {len(deals)} deals from MT5...")

    for deal in deals:
        logger.log_from_mt5_deal(deal)

    print(f"✅ Synced {len(deals)} trades")

    logger.generate_daily_summary()

    mt5.shutdown()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Nanobot Trade Logger")
    parser.add_argument("--sync", "-s", action="store_true", help="Sync from MT5")
    parser.add_argument("--days", "-d", type=int, default=7, help="Days to sync")
    parser.add_argument("--report", "-r", action="store_true", help="Generate report")
    parser.add_argument(
        "--summary", type=str, help="Daily summary for date (YYYY-MM-DD)"
    )

    args = parser.parse_args()

    if args.sync:
        sync_from_mt5(args.days)
    elif args.summary:
        logger = TradeLogger()
        logger.generate_daily_summary(args.summary)
    elif args.report:
        logger = TradeLogger()
        logger.generate_strategy_report()
    else:
        print(
            "Use --sync to sync from MT5, --report for strategy report, or --summary YYYY-MM-DD"
        )
