
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# CONFIG
ASSETS = [
    "AUDUSD=X", "GBPJPY=X", "BTC-USD", "SOL-USD", "NZDUSD=X", 
    "USDCHF=X", "EURNZD=X", "GBPUSD=X", "GBPNZD=X", "USDJPY=X", 
    "USDCAD=X"
]
RISK_PER_TRADE = 0.003 # 0.3%
RR_TARGET = 3.0
INITIAL_CAPITAL = 10000

print("🔍 ANALYZING LIVE TRADES (LAST 24H)...")

# Fetch Data (Last 5 days to be safe)
data = {}
for symbol in ASSETS:
    try:
        df = yf.download(symbol, period="5d", interval="1h", progress=False)
        if not df.empty:
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            data[symbol] = df
    except: pass

total_pnl = 0
open_trades = []

print(f"\n{'PAIR':<10} | {'TIME (UTC)':<16} | {'TYPE':<4} | {'ENTRY':<10} | {'CURRENT':<10} | {'PnL ($)':<10}")
print("-" * 80)

for symbol, df in data.items():
    # Indicators
    df['ema_9'] = df['Close'].ewm(span=9).mean()
    df['ema_15'] = df['Close'].ewm(span=15).mean()
    df['ema_200'] = df['Close'].ewm(span=200).mean()
    
    # ADX/Vol
    high = df['High']; low = df['Low']; close = df['Close']
    tr = pd.concat([high-low, abs(high-close.shift(1)), abs(low-close.shift(1))], axis=1).max(axis=1)
    atr = tr.rolling(14).mean()
    df['volatility'] = df['Close'].pct_change().rolling(24).std() * 1000
    
    up = high.diff(); down = -low.diff()
    plus_dm = pd.Series(0.0, index=df.index); minus_dm = pd.Series(0.0, index=df.index)
    plus_dm[(up > down) & (up > 0)] = up[(up > down) & (up > 0)]
    minus_dm[(down > up) & (down > 0)] = down[(down > up) & (down > 0)]
    plus_di = 100 * (plus_dm.ewm(alpha=1/14).mean() / atr)
    minus_di = 100 * (minus_dm.ewm(alpha=1/14).mean() / atr)
    dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
    df['adx'] = dx.ewm(alpha=1/14).mean()
    
    # Scan logic (Mimic Bot)
    last_signal_date = None
    
    # Look at last 48 hours
    recent_df = df.tail(48)
    
    for i in range(len(recent_df)):
        row = recent_df.iloc[i]
        ts = row.name
        
        # Check Filters
        if not (row['adx'] > 27 and row['volatility'] < 16): continue
        
        # Check Signal
        sig = 0
        if row['ema_9'] > row['ema_15'] and row['Close'] > row['ema_200']: sig = 1
        elif row['ema_9'] < row['ema_15'] and row['Close'] < row['ema_200']: sig = -1
        
        if sig == 0: continue
        
        # Daily Logic
        current_date = ts.date()
        if current_date == last_signal_date: continue
        last_signal_date = current_date
        
        # FOUND A TRADE
        entry_price = row['Close']
        current_price = df.iloc[-1]['Close'] # Live Price
        
        # Calc Stats
        current_atr = atr.loc[ts]
        sl_dist = current_atr * 1.5
        tp_dist = current_atr * 1.5 * RR_TARGET
        
        sl = entry_price - sl_dist if sig==1 else entry_price + sl_dist
        tp = entry_price + tp_dist if sig==1 else entry_price - tp_dist
        
        # Check Outcome (Did it hit SL/TP already?)
        # We need to scan from entry time to NOW
        outcome = "OPEN"
        future_candles = df.loc[ts:].iloc[1:] # Candles after entry
        
        for j in range(len(future_candles)):
            c = future_candles.iloc[j]
            if sig == 1:
                if c['Low'] <= sl: outcome = "LOSS"; break
                if c['High'] >= tp: outcome = "WIN"; break
            else:
                if c['High'] >= sl: outcome = "LOSS"; break
                if c['Low'] <= tp: outcome = "WIN"; break
                
        # Calculate PnL
        risk_amt = INITIAL_CAPITAL * RISK_PER_TRADE # $30
        
        if outcome == "WIN":
            pnl = risk_amt * RR_TARGET # +$90
        elif outcome == "LOSS":
            pnl = -risk_amt # -$30
        else:
            # Floating PnL
            if sig == 1:
                dist = current_price - entry_price
                sl_gap = entry_price - sl
                if sl_gap > 0:
                    r_value = dist / sl_gap
                    pnl = r_value * risk_amt
                else: pnl = 0
            else:
                dist = entry_price - current_price
                sl_gap = sl - entry_price
                if sl_gap > 0:
                    r_value = dist / sl_gap
                    pnl = r_value * risk_amt
                else: pnl = 0
        
        total_pnl += pnl
        
        time_str = str(ts)[5:16] # MM-DD HH:MM
        type_str = "BUY" if sig==1 else "SELL"
        print(f"{symbol:<10} | {time_str:<16} | {type_str:<4} | {entry_price:<10.5f} | {current_price:<10.5f} | ${pnl:<10.2f} ({outcome})")

print("-" * 80)
print(f"💰 ESTIMATED TOTAL PnL: ${total_pnl:.2f}")
print(f"📈 ACCOUNT BALANCE:     ${INITIAL_CAPITAL + total_pnl:.2f}")
print("-" * 80)
