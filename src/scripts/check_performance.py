from siliconmetatrader5 import MetaTrader5
import sys

mt5 = MetaTrader5(port=8001)
if not mt5.initialize():
    print("MT5 Init Failed")
    sys.exit()

acc = mt5.account_info()
print(f"--- ACCOUNT INFO ---")
print(f"Balance: {acc.balance}")
print(f"Equity: {acc.equity}")
print(f"Profit: {acc.profit}")
print(f"Margin: {acc.margin}")
print(f"Margin Free: {acc.margin_free}")

positions = mt5.positions_get()
print(f"\n--- OPEN POSITIONS ({len(positions) if positions else 0}) ---")
if positions:
    for p in positions:
        print(f"Ticket: {p.ticket} | Symbol: {p.symbol} | Profit: {p.profit} | Type: {'Buy' if p.type==0 else 'Sell'} | Volume: {p.volume}")
else:
    print("No active positions.")

mt5.shutdown()
