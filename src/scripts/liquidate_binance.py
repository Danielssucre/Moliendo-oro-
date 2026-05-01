#!/usr/bin/env python3
"""
HIVE EMERGENCY LIQUIDATOR 🚨
============================
Rescues assets from Binance Earn (Flexible) and sells everything to USDT.
"""

import sys
import os
import time
import logging

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(os.path.dirname(_SCRIPT_DIR))
sys.path.insert(0, _PROJECT_ROOT)

from src.nanobot.exchanges.binance_client import BinanceClient
from binance.exceptions import BinanceAPIException

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
logger = logging.getLogger("HIVE.Liquidator")

def main():
    logger.info("🚨 EMERGENCY LIQUIDATION STARTED")
    client = BinanceClient()
    
    # 1. Audit Current State
    balances = client.get_all_balances()
    logger.info(f"📊 Current balances: {balances}")
    
    # 2. Rescue from Earn
    for asset, qty in balances.items():
        if asset.startswith("LD") and qty > 0:
            real_asset = asset[2:]
            logger.info(f"🛠️ [RESCUE] Moving {qty} {real_asset} from Earn to Spot...")
            try:
                if client.redeem_from_savings(real_asset, qty):
                    logger.info(f"   ✅ {real_asset} rescued.")
                else:
                    logger.error(f"   ❌ Failed to rescue {real_asset}.")
            except Exception as e:
                logger.error(f"   ❌ Rescue Error: {e}")

    # Wait for exchange sync
    time.sleep(3)
    
    # 3. Refresh Spot balances after rescue
    spot_balances = client.get_all_balances()
    logger.info(f"📊 Spot balances after rescue: {spot_balances}")
    
    # 4. Market Sell everything (except USDT/BNB/Dust)
    for asset, qty in spot_balances.items():
        if asset in ["USDT", "BNB"]: continue # Keep USDT and small BNB for fees
        if asset.startswith("LD"): continue # Already handled or failed
        
        symbol = f"{asset}USDT"
        
        # Minimum sell value check (Binance limit is usually $5 or $10)
        try:
            price = client.get_price(symbol)
            value = qty * price
            if value > 1.0: # Only sell if value > $1
                logger.info(f"🔴 [SELL] Liquidating {qty} {asset} (~${value:.2f} USDT)...")
                client.market_sell(symbol, qty)
                logger.info(f"   ✅ {symbol} liquidated.")
            else:
                logger.info(f"   💨 Skipping {asset} (Dust: ${value:.4f})")
        except Exception as e:
            logger.warning(f"   ⚠️ Could not sell {asset}: {e}")

    # 5. Final Balance
    final_usdt = client.get_balance("USDT")
    logger.info(f"💰 FINAL LIQUIDATION BALANCE: ${final_usdt:.2f} USDT")
    print(f"RESULT_CAPITAL_RECOVERED={final_usdt}")

if __name__ == "__main__":
    main()
