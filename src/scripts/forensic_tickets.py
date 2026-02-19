from siliconmetatrader5 import MetaTrader5
from datetime import datetime
import sys

mt5 = MetaTrader5(port=8001)
if not mt5.initialize():
    print("MT5 Init Failed")
    sys.exit()

target_tickets = [389161127, 389132847, 389160535, 388796945]

print("--- TICKET ANALYSIS ---")
# Get all history deals for the last 3 days to be safe
deals = mt5.history_deals_get(datetime(2026, 2, 15), datetime.now())

if deals:
    for d in deals:
        if d.order in target_tickets or d.ticket in target_tickets:
            print(f"Ticket: {d.ticket} | Order: {d.order} | Symbol: {d.symbol} | Type: {d.type} (0=Buy, 1=Sell) | Profit: {d.profit} | Time: {datetime.fromtimestamp(d.time)}")
else:
    print("No deals found in history.")

# Also check active positions just in case
positions = mt5.positions_get()
if positions:
    print("\n--- ACTIVE POSITIONS CHECK ---")
    for p in positions:
        if p.ticket in target_tickets:
            print(f"ACTIVE Ticket: {p.ticket} | Symbol: {p.symbol} | Profit: {p.profit} | Time: {datetime.fromtimestamp(p.time)}")

mt5.shutdown()
