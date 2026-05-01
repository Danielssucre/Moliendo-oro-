from siliconmetatrader5 import MetaTrader5
from datetime import datetime, timedelta
import pandas as pd

mt5 = MetaTrader5(port=18812)
if not mt5.initialize(login=60220215, password="uP8*tP6?", server="Axi-US51-Live"):
    print("Failed to initialize MT5")
    exit()

# Fetch history for last 30 days
start_date = datetime.now() - timedelta(days=30)
deals = mt5.history_deals_get(start_date, datetime.now())

if not deals:
    print("No deals found in last 30 days")
    mt5.shutdown()
    exit()

df = pd.DataFrame([d._asdict() for d in deals])
# Filter only closed deals (profit != 0)
df = df[df['profit'] != 0].copy()

# Extract Variant from Comment
def extract_variant(comment):
    comment = str(comment).upper()
    for v in ['ALFA', 'WINNER', 'EXPL', 'NEME', 'SNIPER']:
        if v in comment:
            return v
    return 'OTHER'

df['variant'] = df['comment'].apply(extract_variant)

# Statistics by variant
stats = df.groupby('variant').agg({
    'profit': ['sum', 'count', lambda x: (x > 0).mean() * 100]
})
stats.columns = ['Total_Profit', 'Trades', 'Win_Rate_%']
stats = stats.sort_values('Total_Profit', ascending=False)

print("\n--- PROFITABILITY BY VARIANT (Last 30 Days) ---")
print(stats)

# Best Single Trade
best_trade = df.sort_values('profit', ascending=False).iloc[0]
print(f"\nBest Trade: {best_trade['symbol']} | Profit: {best_trade['profit']} | Variant: {best_trade['variant']}")

# Breakdown by Symbol too
sym_stats = df.groupby('symbol')['profit'].sum().sort_values(ascending=False).head(5)
print("\nTop 5 Symbols:")
print(sym_stats)

mt5.shutdown()
