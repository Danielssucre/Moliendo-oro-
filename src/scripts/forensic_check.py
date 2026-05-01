import os
import sys
import time
from datetime import datetime
import pandas as pd
import json

sys.path.append("/Users/danielsuarezsucre/TRADING/trading_agent")
from siliconmetatrader5 import MetaTrader5

def get_creds():
    try:
        with open("/Users/danielsuarezsucre/TRADING/trading_agent/config/credentials.json", 'r') as f:
            data = json.load(f)
            return data.get("mt5")
    except: return None

def main():
    mt5 = MetaTrader5(port=18812)
    creds = get_creds()
    c_login = int(creds.get("account", 0)) if creds else 1521200226
    c_pass = creds.get("password", "Y9*VlN1c$9f*I?") if creds else "Y9*VlN1c$9f*I?"
    c_server = creds.get("server", "FTMO-Demo2") if creds else "FTMO-Demo2"

    path = 'C:\\Program Files\\MetaTrader 5\\terminal64.exe'
    mt5.initialize(path=path, portable=True, login=c_login, password=c_pass, server=c_server) or mt5.initialize(login=c_login, password=c_pass, server=c_server)

    pairs = ['EURUSD', 'EURGBP', 'AUDNZD', 'AUDJPY', 'CADCHF', 'GBPCAD']
    
    print("=== FORENSIC PORTFOLIO AUDIT ===")
    
    for pair in pairs:
        tick = mt5.symbol_info_tick(pair)
        info = mt5.symbol_info(pair)
        if tick and info:
            spread_pips = (tick.ask - tick.bid) / (info.point * 10 if info.digits in [3, 5] else info.point)
            print(f"[{pair}] Spread: {spread_pips:.1f} pips | Trade Mode: {info.trade_mode}")
        else:
            # TRY WITH SUFFIX .a or c or whatever
            print(f"[{pair}] SILENT FAILURE: mt5.symbol_info_tick() returned None. Symbol may not exist in Market Watch or requires suffix!")
            
    mt5.shutdown()

if __name__ == "__main__":
    main()
