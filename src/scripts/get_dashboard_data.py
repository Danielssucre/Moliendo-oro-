import os
import sys
import pandas as pd
import numpy as np
import json
from datetime import datetime, timedelta, timezone

# Add project root to path
sys.path.append('/Users/danielsuarezsucre/TRADING/trading_agent')
from siliconmetatrader5 import MetaTrader5

def get_dashboard_data():
    mt5 = MetaTrader5(port=18812)
    if not mt5.initialize():
        return {"error": "MT5 Connection Failed"}
    
    # 1. Account Info
    acc = mt5.account_info()
    if not acc:
        mt5.shutdown()
        return {"error": "Could not get account info"}
    
    balance = acc.balance
    equity = acc.equity
    margin_free = acc.margin_free
    
    # 2. Open Positions
    positions = mt5.positions_get()
    open_trades = []
    if positions:
        for p in positions:
            open_trades.append({
                "ticket": p.ticket,
                "symbol": p.symbol,
                "type": "BUY" if p.type == 0 else "SELL",
                "profit": p.profit,
                "comment": p.comment,
                "volume": p.volume
            })
            
    # 3. Performance Audit (Last 7 Days)
    from_date = datetime.now() - timedelta(days=7)
    deals = mt5.history_deals_get(from_date, datetime.now())
    
    performance = {
        "KAIDO": {"pips": 0, "profit": 0, "win": 0, "loss": 0, "count": 0},
        "POLIMATA": {"pips": 0, "profit": 0, "win": 0, "loss": 0, "count": 0},
        "CHAM": {"pips": 0, "profit": 0, "win": 0, "loss": 0, "count": 0},
        "ALFA": {"pips": 0, "profit": 0, "win": 0, "loss": 0, "count": 0},
        "NEME": {"pips": 0, "profit": 0, "win": 0, "loss": 0, "count": 0}
    }
    
    if deals:
        pos_ids = {}
        for d in deals:
            pid = d.position_id
            if pid not in pos_ids: pos_ids[pid] = []
            pos_ids[pid].append(d)
        
        for pid, d_list in pos_ids.items():
            entry = sorted(d_list, key=lambda x: x.time)[0]
            comment = entry.comment.upper() if entry.comment else ""
            
            # Identify Strategy
            strat = None
            if "KAIDO" in comment: strat = "KAIDO"
            elif "POLIMATA" in comment: strat = "POLIMATA"
            elif "CHAM" in comment: strat = "CHAM"
            elif "ALFA" in comment: strat = "ALFA"
            elif "NEME" in comment: strat = "NEME"
            
            if strat:
                pnl = sum(d.profit + d.swap + d.commission for d in d_list)
                performance[strat]["profit"] += pnl
                performance[strat]["count"] += 1
                if pnl > 0: performance[strat]["win"] += 1
                else: performance[strat]["loss"] += 1

    # 4. Symbol Rankings (Last 24h)
    symbol_pnl = {}
    last_24h = datetime.now() - timedelta(hours=24)
    deals_24h = mt5.history_deals_get(last_24h, datetime.now())
    if deals_24h:
        for d in deals_24h:
            symbol_pnl[d.symbol] = symbol_pnl.get(d.symbol, 0) + d.profit

    mt5.shutdown()
    
    return {
        "account": {
            "balance": balance,
            "equity": equity,
            "margin_free": margin_free,
            "drawdown_pct": (1 - equity/balance)*100 if balance > 0 else 0
        },
        "open_trades": open_trades,
        "performance": performance,
        "symbol_rank": dict(sorted(symbol_pnl.items(), key=lambda x: x[1], reverse=True)[:5]),
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

if __name__ == "__main__":
    data = get_dashboard_data()
    print(json.dumps(data, indent=2))
