from siliconmetatrader5 import MetaTrader5
from datetime import datetime, timedelta
import pandas as pd
import sys

mt5 = MetaTrader5(port=8001)
if not mt5.initialize():
    print("MT5 Init Failed")
    sys.exit()

# Signals to evaluate
# format: (symbol, type, timestamp)
blocks = [
    ("USDCHF", "BUY", "2026-02-18 12:49:56"),
    ("GBPNZD", "BUY", "2026-02-18 12:50:00"),
    ("AUDUSD", "SELL", "2026-02-18 16:57:41"),
    ("GBPUSD", "SELL", "2026-02-18 16:57:47")
]

print("--- GATEKEEPER DECISION AUDIT ---")
for symbol, order_type, ts_str in blocks:
    ts = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
    
    # Get price at that time (approx using H1/M15 bars)
    rates = mt5.copy_rates_from(symbol, mt5.TIMEFRAME_M1, ts + timedelta(minutes=1), 1)
    if rates is not None and len(rates) > 0:
        price_at_signal = float(rates[0]['open'])
        
        # Get current price
        tick = mt5.symbol_info_tick(symbol)
        current_price = tick.bid if order_type == "SELL" else tick.ask
        
        diff = current_price - price_at_signal
        profit_pips = (diff / mt5.symbol_info(symbol).point) if order_type == "BUY" else (-diff / mt5.symbol_info(symbol).point)
        
        status = "✅ GOOD REJECT (Losing trade)" if profit_pips < 0 else "❌ BAD REJECT (Winning trade - missed opportunity)"
        
        print(f"Signal: {symbol} {order_type} @ {ts_str}")
        print(f"  Price then: {price_at_signal:.5f}")
        print(f"  Price now:  {current_price:.5f}")
        print(f"  Potential: {profit_pips:.1f} pips | {status}")
        print("-" * 40)
    else:
        print(f"No data for {symbol} at {ts_str}")

mt5.shutdown()
