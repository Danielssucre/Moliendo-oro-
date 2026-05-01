import sys, os
sys.path.append(os.path.join(os.getcwd(), "src"))
from dashboard.backend.app.services.mt5_service import MT5Service
import siliconmetatrader5 as mt5_client
from datetime import datetime
import pandas as pd
mt5 = MT5Service(os.getcwd())
if mt5.connect():
    rates = mt5.client.copy_rates_from_pos("XAUUSD", mt5.client.TIMEFRAME_M1, 0, 1000)
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    # find row near 21:51 server time
    df_filtered = df[(df['time'] >= '2026-04-19 21:51:00') & (df['time'] <= '2026-04-19 23:29:00')]
    print(df_filtered.head(5))
    print(df_filtered.tail(5))
