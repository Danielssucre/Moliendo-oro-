import sys
import os
import pandas as pd

# Setup Paths
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)
sys.path.insert(0, _PROJECT_ROOT)

from src.nanobot.exchanges.binance_client import BinanceClient
from src.analysis.indicators import IndicatorAnalyzer
from src.nanobot.strategies.forex_infantry import ForexInfantry

def test_neme_on_binance():
    client = BinanceClient()
    engine = ForexInfantry()
    
    symbol = "BTCUSDT"
    print(f"🔍 Fetching H1 data for {symbol}...")
    klines = client.get_klines(symbol, interval="1h", limit=300)
    df = pd.DataFrame(klines, columns=['time','open','high','low','close','volume','ct','qv','tr','tb','tq','i'])
    df[['open','high','low','close','volume']] = df[['open','high','low','close','volume']].apply(pd.to_numeric)
    
    analyzer = IndicatorAnalyzer(df)
    inds = analyzer.get_latest_values()
    
    print(f"📊 Indicators: RSI={inds.get('rsi'):.2f}, ADX={inds.get('adx'):.2f}")
    
    neme_sig, strat = engine.get_nemesis_signal_with_strategy(analyzer.df)
    
    print(f"🧠 NEME Signal: {neme_sig} | Strategy: {strat}")
    if neme_sig == 1:
        print("✅ SUCCESS: LONG REVERSION SIGNAL DETECTED (SPOT ELIGIBLE)")
    elif neme_sig == -1:
        print("⚠️ SHORT REVERSION SIGNAL (SPOT INELIGIBLE)")
    else:
        print("⏳ NO SIGNAL (NEUTRAL)")

if __name__ == "__main__":
    test_neme_on_binance()
