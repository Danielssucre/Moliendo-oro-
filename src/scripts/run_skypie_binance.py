#!/usr/bin/env python3
"""
SKYPIE-ENEL BINANCE LIVE RUNNER ⚡
====================================
Live trading bot for Binance Spot using the MCA Gold Cluster strategy.
Capital: Micro-sizing (all available USDT, min $5 per trade)
Pairs: ETHUSDT, SOLUSDT (BTC requires more capital)
Risk: Signal-based entry, fixed 2% take profit, 1.5% stop loss
"""

import sys
import os
import time
import logging
import json
import requests
import pandas as pd
import numpy as np
from datetime import datetime

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(os.path.dirname(_SCRIPT_DIR))
sys.path.insert(0, _PROJECT_ROOT)

from src.nanobot.exchanges.binance_client import BinanceClient
from binance.exceptions import BinanceAPIException

# --- LOGGING ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    handlers=[
        logging.FileHandler('logs/skypie_binance.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("Skypie.Binance")

# --- TELEGRAM ---
from src.nanobot.utils.telegram_bot import TelegramBot
bot = TelegramBot()

def tg(msg: str):
    """Throttled Telegram message via centralized bot."""
    if not bot.enabled:
        return
    bot.send_message(msg)

# --- CONFIG ---
SYMBOLS        = ["ETHUSDT", "SOLUSDT"]
SCAN_INTERVAL  = 60          # seconds between scans
MIN_USDT       = 5.0         # Binance minimum notional
MAX_TRADE_PCT  = 0.80        # Use at most 80% of balance per trade
TAKE_PROFIT    = 0.020       # 2.0%
STOP_LOSS      = 0.015       # 1.5%
ADX_MIN        = 20.0
ADX_MAX        = 35.0
RSI_MIN        = 40.0
RSI_MAX        = 60.0

# --- BANK PRIORITY (Bancolombia Arbitrage) ---
BANK_PRIORITY_MODE    = True
DEBT_MONTHLY_TARGET   = 31.50   # Bancolombia interest target
DEBT_RESERVE_PERCENT  = 1.0     # 100% of profit goes to reserve until target met
CAPITAL_INITIAL       = 60.0    # Baseline for profit calculation (Update to 1000 if funded)
last_notified_target  = False    # Flag to avoid spamming TG

# --- HELPERS ---

def calculate_debt_status(current_usdt: float) -> dict:
    """Calculate how much debt interest has been covered."""
    profit = current_usdt - CAPITAL_INITIAL
    profit = max(0, profit)
    covered = min(profit, DEBT_MONTHLY_TARGET)
    percent = (covered / DEBT_MONTHLY_TARGET) * 100 if DEBT_MONTHLY_TARGET > 0 else 100
    remaining = DEBT_MONTHLY_TARGET - covered
    
    return {
        "profit": profit,
        "covered": covered,
        "percent": percent,
        "remaining": max(0, remaining),
        "target_met": profit >= DEBT_MONTHLY_TARGET
    }

def compute_indicators(klines: list) -> dict:
    """Compute ADX, RSI, Volatility from Binance klines data."""
    df = pd.DataFrame(klines, columns=[
        'open_time','open','high','low','close','volume',
        'close_time','quote_vol','trades','taker_buy_base','taker_buy_quote','ignore'
    ])
    df['close'] = df['close'].astype(float)
    df['high']  = df['high'].astype(float)
    df['low']   = df['low'].astype(float)

    # RSI (14)
    delta  = df['close'].diff()
    gain   = delta.clip(lower=0)
    loss   = -delta.clip(upper=0)
    avg_g  = gain.rolling(14).mean()
    avg_l  = loss.rolling(14).mean()
    rs     = avg_g / avg_l.replace(0, np.nan)
    rsi    = (100 - 100 / (1 + rs)).iloc[-1]

    # ATR (14)
    tr = pd.concat([
        df['high'] - df['low'],
        (df['high'] - df['close'].shift()).abs(),
        (df['low']  - df['close'].shift()).abs()
    ], axis=1).max(axis=1)
    atr = tr.rolling(14).mean().iloc[-1]

    # Volatility: ATR as % of price
    price = df['close'].iloc[-1]
    vol   = (atr / price) * 100

    # ADX (14) — simplified directional movement
    plus_dm  = (df['high'].diff()).clip(lower=0)
    minus_dm = (-df['low'].diff()).clip(lower=0)
    plus_di  = 100 * (plus_dm.rolling(14).mean() / tr.rolling(14).mean().replace(0, np.nan))
    minus_di = 100 * (minus_dm.rolling(14).mean() / tr.rolling(14).mean().replace(0, np.nan))
    dx       = (100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan))
    adx      = dx.rolling(14).mean().iloc[-1]

    # Trend direction: EMA12 vs EMA26
    ema12 = df['close'].ewm(span=12).mean()
    ema26 = df['close'].ewm(span=26).mean()
    trend = "BUY" if ema12.iloc[-1] > ema26.iloc[-1] else "SELL"

    return {"rsi": rsi, "adx": adx, "vol": vol, "price": price, "trend": trend}


def is_gold_cluster(ind: dict) -> bool:
    """Apply Skypie-Enel MCA Gold Cluster filter."""
    adx = ind.get('adx', 0)
    vol = ind.get('vol', 999)
    rsi = ind.get('rsi', 50)

    if vol > 5.0:
        logger.info(f"  ❌ Death Zone: Vol={vol:.2f}% (>5%)")
        return False
    if not (ADX_MIN <= adx <= ADX_MAX):
        logger.info(f"  ❌ ADX out of Gold Zone: {adx:.1f} (need {ADX_MIN}-{ADX_MAX})")
        return False
    if not (RSI_MIN <= rsi <= RSI_MAX):
        logger.info(f"  ❌ RSI over-extended: {rsi:.1f} (need {RSI_MIN}-{RSI_MAX})")
        return False

    logger.info(f"  ⚡⚡ GOLD CLUSTER DETECTED! ADX={adx:.1f} RSI={rsi:.1f} Vol={vol:.2f}%")
    return True


def get_pair_asset(symbol: str) -> str:
    """Extract base asset from USDT symbol."""
    if symbol.endswith("USDT"):
        return symbol[:-4]
    return symbol

def round_qty(symbol: str, qty: float) -> float:
    """Truncate quantity to exchange precision to avoid rounding up beyond balance."""
    import math
    if symbol == "ETHUSDT":
        return math.floor(qty * 10000) / 10000.0
    elif symbol == "SOLUSDT":
        return math.floor(qty * 100) / 100.0
    elif symbol == "BTCUSDT":
        return math.floor(qty * 100000) / 100000.0
    return math.floor(qty * 10000) / 10000.0

def calculate_qty(symbol: str, usdt_balance: float, price: float) -> float:
    """Calculate max quantity we can buy within budget constraints."""
    usdt_to_use = min(usdt_balance * MAX_TRADE_PCT, usdt_balance - 0.10)
    if usdt_to_use < MIN_USDT:
        return 0.0

    raw_qty = usdt_to_use / price
    return round_qty(symbol, raw_qty)


def recover_active_positions(client: BinanceClient) -> dict:
    """Scan account balances and trade history to recover lost state after restart."""
    recovered = {}
    logger.info("🔍 RECOVERY MODE: Scanning exchange for active positions...")
    
    for sym in SYMBOLS:
        asset = get_pair_asset(sym)
        bal = client.get_balance(asset)
        
        # Check for Earn balance (Flexible Savings assets start with 'LD')
        earn_asset = f"LD{asset}"
        earn_bal = client.get_balance(earn_asset)
        
        if earn_bal > 0:
            logger.warning(f"   ⚠️ Found {earn_bal} {asset} in Flexible Savings ({earn_asset}).")
            logger.info(f"   🛠️ [AUTO-REDEEM] Attempting fast redemption for {asset}...")
            if client.redeem_from_savings(asset, earn_bal):
                bal += earn_bal
            else:
                logger.error(f"   ❌ [AUTO-REDEEM] Could not move {asset} to Spot! Sell will fail.")
            
            if bal <= 0:
                bal = earn_bal # Fallback for recovery tracking
        
        # If we have a non-trivial balance (Binance often leaves dust, so we check > min qty)
        min_qty = 0.001 if "ETH" in sym or "BTC" in sym else 0.01
        if bal > min_qty:
            logger.info(f"   Found {bal} {asset} (Total Spot+Earn). Finding entry price...")
            try:
                # Fetch last BUY trade to get entry price
                trades = client.client.get_my_trades(symbol=sym, limit=20)
                buy_trades = [t for t in trades if t['isBuyer']]
                if buy_trades:
                    last_buy = buy_trades[-1]
                    entry_price = float(last_buy['price'])
                    recovered[sym] = {
                        "entry": entry_price,
                        "qty": bal,
                        "side": "BUY",
                        "recovered": True
                    }
                    logger.info(f"   ✅ Recovered {sym}: {bal} units bought at ${entry_price:.4f}")
                else:
                    logger.warning(f"   ⚠️ Found balance for {sym} but no recent buy trade. Skipping.")
            except Exception as e:
                logger.error(f"   ❌ Error recovering {sym}: {e}")
                
    return recovered


def main():
    logger.info("⚡ SKYPIE-ENEL BINANCE LIVE — STARTING")
    logger.info(f"   Pairs: {SYMBOLS}")
    logger.info(f"   Strategy: MCA Gold Cluster | TP: {TAKE_PROFIT*100}% | SL: {STOP_LOSS*100}%")

    client = BinanceClient()
    
    # --- POSITION RECOVERY ---
    active_positions = recover_active_positions(client)

    usdt_start = client.get_balance('USDT')
    # Check if USDT is also in Earn
    earn_usdt = client.get_balance('LDUSDT')
    if earn_usdt > 0:
        logger.info(f"   🛠️ [AUTO-REDEEM] Recovering {earn_usdt} USDT from Savings...")
        client.redeem_from_savings('USDT', earn_usdt)
        usdt_start += earn_usdt

    tg(
        f"⚡ *SKYPIE-ENEL BINANCE — ONLINE* ⚡\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🌐 Exchange: *Binance Spot*\n"
        f"📊 Pares: `{', '.join(SYMBOLS)}`\n"
        f"🎯 Estrategia: MCA Gold Cluster\n"
        f"💰 Capital: `${usdt_start:.4f} USDT`\n"
        f"🛡️ TP: `+{TAKE_PROFIT*100:.1f}%` | SL: `-{STOP_LOSS*100:.1f}%`\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        + (f"🏦 *BPriority:* `Bancolombia $31.50/mo`\n" if BANK_PRIORITY_MODE else "")
        + f"🤖 Modo: Centinela Activo — Buscando Gold Cluster..."
    )

    while True:
        try:
            loop_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            logger.info(f"\n{'='*55}")
            logger.info(f"⚡ SCAN CYCLE: {loop_time}")

            # 1. Check active positions for TP/SL
            for sym in list(active_positions.keys()):
                pos = active_positions[sym]
                current_ticker = client.client.get_symbol_ticker(symbol=sym)
                current_price  = float(current_ticker['price'])
                entry          = pos['entry']
                pct_change     = (current_price - entry) / entry

                logger.info(f"  👁️  {sym} | Entry: {entry:.4f} | Now: {current_price:.4f} | P&L: {pct_change*100:.2f}%")

                if pct_change >= TAKE_PROFIT:
                    logger.info(f"  🎯 TAKE PROFIT HIT for {sym}! Closing...")
                    try:
                        # Fetch actual exchange balance (Spot + Earn)
                        asset = get_pair_asset(sym)
                        
                        # FORCE REDEEM before sell to ensure we capture Everything
                        earn_bal = client.get_balance(f"LD{asset}")
                        if earn_bal > 0:
                            logger.info(f"  🛠️ [AUTO-REDEEM] {earn_bal} {asset} detected in Earn. Rescuing...")
                            client.redeem_from_savings(asset, earn_bal)
                            time.sleep(1) # Allow exchange sync

                        exchange_bal = client.get_balance(asset)
                        sell_qty = round_qty(sym, min(pos['qty'], exchange_bal))
                        
                        logger.info(f"  💰 Qty Internal: {pos['qty']} | Qty Exchange: {exchange_bal} | Selling: {sell_qty}")
                        
                        if sell_qty <= 0:
                            logger.error(f"  ❌ Cannot sell {sym}: Zero balance on exchange.")
                            del active_positions[sym]
                            continue

                        client.market_sell(sym, sell_qty)
                        pnl = sell_qty * current_price - sell_qty * pos['entry']
                        logger.info(f"  ✅ Position closed at +{pct_change*100:.2f}%")
                        tg(
                            f"🎯 *TAKE PROFIT — SKYPIE BINANCE*\n"
                            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                            f"💹 Par: `{sym}`\n"
                            f"📈 P&L: `+{pct_change*100:.2f}%` (+${pnl:.4f} USDT)\n"
                            f"🎯 Entrada: `${pos['entry']:.4f}` → Cierre: `${current_price:.4f}`\n"
                            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                            f"⚡ Skypie-Enel | MCA Gold Cluster"
                        )
                        del active_positions[sym]
                    except BinanceAPIException as e:
                        logger.error(f"  ❌ TP Close Error: {e}")

                elif pct_change <= -STOP_LOSS:
                    logger.info(f"  🛑 STOP LOSS HIT for {sym}! Closing...")
                    try:
                        # Fetch actual exchange balance to avoid 'insufficient balance' due to fees
                        asset = get_pair_asset(sym)
                        
                        # FORCE REDEEM before sell
                        earn_bal = client.get_balance(f"LD{asset}")
                        if earn_bal > 0:
                            logger.info(f"  🛠️ [AUTO-REDEEM] {earn_bal} {asset} detected in Earn. Rescuing for SL...")
                            client.redeem_from_savings(asset, earn_bal)
                            time.sleep(1)

                        exchange_bal = client.get_balance(asset)
                        sell_qty = round_qty(sym, min(pos['qty'], exchange_bal))

                        logger.info(f"  💰 Qty Internal: {pos['qty']} | Qty Exchange: {exchange_bal} | Selling: {sell_qty}")

                        if sell_qty <= 0:
                            logger.error(f"  ❌ Cannot sell {sym}: Zero balance on exchange.")
                            del active_positions[sym]
                            continue

                        client.market_sell(sym, sell_qty)
                        pnl = sell_qty * current_price - sell_qty * pos['entry']
                        logger.info(f"  ⚠️  Position closed at {pct_change*100:.2f}%")
                        tg(
                            f"🛑 *STOP LOSS — SKYPIE BINANCE*\n"
                            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                            f"💹 Par: `{sym}`\n"
                            f"📉 P&L: `{pct_change*100:.2f}%` (${pnl:.4f} USDT)\n"
                            f"🛑 Entrada: `${pos['entry']:.4f}` → Cierre: `${current_price:.4f}`\n"
                            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                            f"🛡️ Capital protegido — Buscando siguiente setup..."
                        )
                        del active_positions[sym]
                    except BinanceAPIException as e:
                        logger.error(f"  ❌ SL Close Error: {e}")

            # 2. Scan for new entries
            # --- AUTO-REDEMPTION FOR USDT ---
            # If your "Spot" USDT is empty but you have "Earn" USDT, rescue it every cycle
            earn_usdt = client.get_balance('LDUSDT')
            if earn_usdt > 0:
                logger.info(f"  🛠️ [AUTO-REDEEM] Found ${earn_usdt} USDT in Earn. Collecting for reinvestment...")
                client.redeem_from_savings('USDT', earn_usdt)
                time.sleep(1)

            usdt_balance = client.get_balance("USDT")
            
            # --- BANK PRIORITY CHECK ---
            if BANK_PRIORITY_MODE:
                status = calculate_debt_status(usdt_balance)
                prefix = "[🏦 BPriority]"
                if status['target_met']:
                    logger.info(f"{prefix} ✅ TARGET MET: ${status['profit']:.2f} profit. Excess is yours!")
                    if not last_notified_target:
                        tg(f"🎉 *BANCOLOMBIA PRIORIDAD LOGRADA*\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n💰 Profit: `${status['profit']:.2f}`\n✅ Interés de $31.50 cubierto.\n🚀 El excedente es utilidad neta.")
                        last_notified_target = True
                else:
                    logger.info(f"{prefix} ⏳ Progress: ${status['covered']:.2f}/${DEBT_MONTHLY_TARGET} ({status['percent']:.1f}%) | Need: ${status['remaining']:.2f}")

            logger.info(f"💰 Available USDT: ${usdt_balance:.4f}")

            if usdt_balance < MIN_USDT:
                logger.info("  ⚠️  Insufficient USDT balance for new entries. Watching positions...")
            else:
                for symbol in SYMBOLS:
                    if symbol in active_positions:
                        logger.info(f"  📌 {symbol}: Already in position. Skipping entry scan.")
                        continue

                    logger.info(f"\n🔍 Analyzing {symbol}...")
                    klines = client.get_klines(symbol, interval="15m", limit=50)
                    ind    = compute_indicators(klines)

                    logger.info(f"   ADX={ind['adx']:.1f} | RSI={ind['rsi']:.1f} | Vol={ind['vol']:.2f}% | Trend={ind['trend']} | Price=${ind['price']:.4f}")

                    if ind['trend'] == "BUY" and is_gold_cluster(ind):
                        qty = calculate_qty(symbol, usdt_balance, ind['price'])

                        if qty <= 0:
                            logger.info(f"  ⚠️  Quantity too small to execute. Balance insufficient.")
                            continue

                        logger.info(f"  🚀 ENTRY SIGNAL! Buying {qty} {symbol} @ ${ind['price']:.4f}")
                        try:
                            order = client.market_buy(symbol, qty)
                            actual_price = float(order.get('fills', [{}])[0].get('price', ind['price'])) if order.get('fills') else ind['price']
                            tp_price = actual_price * (1 + TAKE_PROFIT)
                            sl_price = actual_price * (1 - STOP_LOSS)
                            active_positions[symbol] = {
                                "entry": actual_price,
                                "qty": qty,
                                "side": "BUY",
                                "time": loop_time
                            }
                            logger.info(f"  ✅ POSITION OPENED: {symbol} {qty} @ ${actual_price:.4f}")
                            tg(
                                f"⚡⚡ *GOLD CLUSTER — ENTRADA SKYPIE*\n"
                                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                                f"🟢 *COMPRA {symbol}*\n"
                                f"💰 Cantidad: `{qty}`\n"
                                f"📌 Entrada: `${actual_price:.4f}`\n"
                                f"🎯 TP: `${tp_price:.4f}` (+{TAKE_PROFIT*100:.1f}%)\n"
                                f"🛑 SL: `${sl_price:.4f}` (-{STOP_LOSS*100:.1f}%)\n"
                                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                                f"📊 ADX: `{ind['adx']:.1f}` | RSI: `{ind['rsi']:.1f}` | Vol: `{ind['vol']:.2f}%`\n"
                                f"⚡ Skypie-Enel | MCA GOLD CLUSTER CONFIRMADO"
                            )
                        except BinanceAPIException as e:
                            logger.error(f"  ❌ Order Error for {symbol}: {e}")
                    else:
                        logger.info(f"  🔕 No Gold Cluster signal for {symbol}.")

            # 3. Telegram scan summary (every cycle)
            bal_now = client.get_balance('USDT')
            pos_lines = ''
            for s, p in active_positions.items():
                tick = client.client.get_symbol_ticker(symbol=s)
                cp = float(tick['price'])
                pct = (cp - p['entry']) / p['entry'] * 100
                pos_lines += f"  📌 `{s}`: ${cp:.4f} | P&L: `{pct:+.2f}%`\n"

            tg(
                f"⚡ *SKYPIE BINANCE — Scan {loop_time}*\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"💰 USDT Libre: `${bal_now:.4f}`\n"
                + (f"📊 Posiciones Abiertas:\n{pos_lines}" if pos_lines else "🔕 Sin posiciones abiertas\n")
                + f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🤖 Skypie-Enel | MCA Gold Cluster Watcher"
            )

            logger.info(f"\n⏳ Active Positions: {list(active_positions.keys()) or 'None'}")
            logger.info(f"💤 Sleeping {SCAN_INTERVAL}s until next scan...")
            time.sleep(SCAN_INTERVAL)

        except KeyboardInterrupt:
            logger.info("\n🛑 Skypie-Enel Binance runner stopped by user.")
            # Close all open positions on exit
            if active_positions:
                logger.info("🔒 Closing all open positions...")
                for sym, pos in active_positions.items():
                    try:
                        asset = get_pair_asset(sym)
                        # Emergency rescue before final sell
                        earn_bal = client.get_balance(f"LD{asset}")
                        if earn_bal > 0:
                            client.redeem_from_savings(asset, earn_bal)
                        
                        exchange_bal = client.get_balance(asset)
                        qty = round_qty(sym, min(pos['qty'], exchange_bal))
                        
                        if qty > 0:
                            client.market_sell(sym, qty)
                            logger.info(f"  ✅ {sym} closed and realized to USDT.")
                    except Exception as e:
                        logger.error(f"  ❌ Could not close {sym}: {e}")
            break
        except Exception as e:
            logger.error(f"❌ Loop Error: {e} — retrying in {SCAN_INTERVAL}s")
            time.sleep(SCAN_INTERVAL)


if __name__ == "__main__":
    main()
