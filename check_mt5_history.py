import MetaTrader5 as mt5
from datetime import datetime, timedelta
import pandas as pd

def check_history():
    if not mt5.initialize():
        print(f"MT5 Initialize failed, error code: {mt5.last_error()}")
        return

    # Set dates for today
    from_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    to_date = datetime.now() + timedelta(days=1)
    
    print(f"Fetching history from {from_date} to {to_date}...")
    
    # Check History Deals (Realized P&L)
    history_deals = mt5.history_deals_get(from_date, to_date)
    
    if history_deals is None:
        print("No history deals found.")
    elif len(history_deals) == 0:
        print("History list is empty for today.")
    else:
        df = pd.DataFrame(list(history_deals), columns=history_deals[0]._asdict().keys())
        # Filter for closed deals (entry=1 is out, depending on broker, but profit != 0 usually indicates closure)
        closed_deals = df[df['profit'] != 0]
        if closed_deals.empty:
            print("No closed deals with profit/loss recorded today.")
        else:
            print("\n--- CLOSED DEALS TODAY ---")
            print(closed_deals[['time', 'symbol', 'type', 'entry', 'profit', 'comment']])
            
    # Check Active Positions
    positions = mt5.positions_get()
    if positions:
        print("\n--- ACTIVE POSITIONS ---")
        df_pos = pd.DataFrame(list(positions), columns=positions[0]._asdict().keys())
        print(df_pos[['symbol', 'type', 'volume', 'price_open', 'profit', 'comment']])
    else:
        print("\nNo active positions.")

    mt5.shutdown()

if __name__ == "__main__":
    check_history()
